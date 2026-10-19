#!/usr/bin/env python3
"""Abstract the corpus. Resumable batch job over Person B's LLM gateway.

Design notes that matter:

  * **Resumable.** Completed papers are skipped on restart, so a kill mid-run loses
    nothing. The corpus is 3,000 calls; that job must survive being interrupted.
  * **Prompt-versioned cache.** The gateway cache key is
    (task, cache_id, prompt_sha256, model, schema_sha256), so editing prompts/abstractor.md
    invalidates every cached result. Forgetting to bump `version` therefore cannot return a
    stale abstraction.
  * **Failures go to a retry file**, never silently dropped.
  * **mechanism is required for corpus papers.** User input may leave it null; a corpus
    paper may not, and a null is written to the retry file rather than indexed.
  * **Leak check.** Gateway rule 17: if the abstraction names the solution, the call is
    rejected and not cached, because a leak puts the answer in the query and makes
    retrieval self-fulfilling.

Requires B's gateway (`backend/`) and `prompts/abstractor.md`. Until both exist this runs in
--dry-run mode, which exercises the whole job except the API call, so the plumbing can be
reviewed now instead of at Hour 6.

Usage:
    set -a; source .env; set +a
    python3 data/abstract_corpus.py --dry-run --limit 20     # no gateway needed
    python3 data/abstract_corpus.py --limit 600              # the pilot
    python3 data/abstract_corpus.py                          # full 3,000
    python3 data/abstract_corpus.py --retry-failed           # after a failure
"""

import argparse
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

CORPUS = "data/corpus/corpus.jsonl"
OUT = "data/corpus/abstractions.jsonl"
RETRY = "data/corpus/abstract_retry.jsonl"
PROMPT = "prompts/abstractor.md"
SCHEMA = "config/schemas/abstraction.schema.json"

# Vocabulary that would mean the abstractor read its own answer. Terms are per-domain and
# are supplied with the job; these are the generic ones that apply to every case.
GENERIC_LEAK_TERMS = [
    "jamming", "granular", "particle", "packing fraction", "vacuum",
    "spin glass", "matching procedure", "stable marriage",
]


def load_yaml(p):
    with open(p) as f:
        return yaml.safe_load(f)


def read_jsonl(p):
    if not os.path.exists(p):
        return []
    out = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # a torn final line from a kill is expected; skip it
    return out


def leak_terms(args):
    terms = list(GENERIC_LEAK_TERMS)
    if args.leak_terms:
        terms += [t.strip().lower() for t in args.leak_terms.split(",") if t.strip()]
    return terms


def check_leak(abstraction, terms):
    """Gateway rule 17. Return the offending term, or None.

    Scoped to functional_problem and mechanism only. domain_tags is SUPPOSED to hold the
    input's own field vocabulary, so a domain noun there is correct, not a leak; a solution
    noun in those two fields is what makes retrieval self-fulfilling.
    """
    scoped = " ".join(str(abstraction.get(k) or "")
                      for k in ("functional_problem", "mechanism")).lower()
    for t in terms:
        if t in scoped:
            return t
    return None


def validate(abstraction, schema):
    """Post-validate against the FULL untranslated schema, as gateway rule 16 requires.

    Gateway rule 14 explains why this cannot be skipped: Gemini's responseSchema rejects
    additionalProperties and union types, so minLength/maxLength/nullable are dropped
    before sending, and this is the only place they are enforced.
    """
    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    req = schema.get("required", [])
    missing = [k for k in req if k not in abstraction]
    if missing:
        return f"missing required: {missing}"
    if jsonschema is not None:
        try:
            jsonschema.validate(abstraction, schema)
        except jsonschema.ValidationError as e:
            return f"schema: {e.message[:120]}"
        return None
    # Fallback checks when jsonschema is absent.
    for k, spec in schema.get("properties", {}).items():
        v = abstraction.get(k)
        if v is None:
            continue
        if spec.get("type") == "string":
            if not isinstance(v, str):
                return f"{k} must be string"
            if "minLength" in spec and len(v) < spec["minLength"]:
                return f"{k} shorter than minLength {spec['minLength']}"
            if "maxLength" in spec and len(v) > spec["maxLength"]:
                return f"{k} longer than maxLength {spec['maxLength']}"
        if spec.get("type") == "array":
            if not isinstance(v, list):
                return f"{k} must be array"
            if "maxItems" in spec and len(v) > spec["maxItems"]:
                return f"{k} more than maxItems {spec['maxItems']}"
    return None


def build_prompt_inputs(rec):
    """One placeholder, {{text}}, for both corpus papers and user input.

    prompts/abstractor.md references a single `{{text}}`, so this must not introduce
    `{{title}}`/`{{abstract}}`: the gateway spec says a missing placeholder raises, and the
    same prompt file has to work for the live user-input path too.
    """
    return {"text": f"Title: {rec['title']}\n\n{rec['abstract']}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="exercise everything except the API call")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retry-failed", action="store_true",
                    help="also retry papers listed in the retry file")
    ap.add_argument("--leak-terms", default="", help="extra comma-separated domain terms")
    ap.add_argument("--pilot", action="store_true", help="600 papers, per corpus.yaml")
    args = ap.parse_args()

    cfg = load_yaml("config/models.yaml")
    task = cfg["llm"]["tasks"]["abstractor"]
    schema = load_yaml(SCHEMA) if SCHEMA.endswith(".json") else json.load(open(SCHEMA))

    corpus = read_jsonl(CORPUS)
    if not corpus:
        print(f"no corpus at {CORPUS}. Run data/ingest_corpus.py first.")
        return 1
    done = {r["paper_id"] for r in read_jsonl(OUT)}
    if args.retry_failed:
        for r in read_jsonl(RETRY):
            done.discard(r["paper_id"])

    todo = [r for r in corpus if r["paper_id"] not in done]
    if args.pilot:
        todo = todo[: int(cfg and yaml.safe_load(open("config/corpus.yaml"))["size"]["pilot_total"])]
    if args.limit:
        todo = todo[: args.limit]

    print(f"corpus            : {len(corpus)}")
    print(f"already abstracted: {len(done)}")
    print(f"to do             : {len(todo)}")
    print(f"task              : {task['model']} temp={task['temperature']} "
          f"thinking={cfg['llm'].get('thinking', {}).get('budget', 'unset')}")
    print(f"prompt file       : {task['prompt_file']} "
          f"{'PRESENT' if os.path.exists(task['prompt_file']) else 'MISSING'}")
    print(f"schema file       : {task['schema_file']} "
          f"{'PRESENT' if os.path.exists(task['schema_file']) else 'MISSING'}")

    have_prompt = os.path.exists(task["prompt_file"])
    if not have_prompt:
        print("\nWARNING: prompts/abstractor.md does not exist yet. A real run will fail or,"
              "\n         worse, silently use the wrong prompt. --dry-run is safe; a live run"
              "\n         should not start until the prompt and its few-shots are written.")

    if args.dry_run:
        terms = leak_terms(args)
        good = {"functional_problem": "Conform to an arbitrary contour and immobilise it "
                                      "under one global control signal.",
                "constraints": ["must work without per-object programming",
                                "must hold without continuous sensing"],
                "mechanism": "Reversible transition between a compliant state and a "
                             "load-bearing state on command.",
                "domain_tags": ["gripper", "end effector"]}
        leaky = {"functional_problem": "Switch rigid on command via granular jamming.",
                 "constraints": [], "mechanism": "Jamming of particles under vacuum.",
                 "domain_tags": ["gripper"]}
        print(f"\n--dry-run: {len(todo)} papers, no API calls.")
        print(f"leak terms armed  : {len(terms)}  {terms}")
        print(f"valid fixture     -> {validate(good, schema) or 'OK (validates against the full schema)'}")
        print(f"leaky fixture     -> {check_leak(leaky, terms) or 'MISSED!'} (must name a term)")
        print(f"null-mechanism    -> {validate({**good, 'mechanism': None}, schema) or 'OK (nullable, allowed)'}")
        print("\nnext 3 papers that would be processed:")
        for r in todo[:3]:
            print(f"  {r['paper_id']}  {r['field']:26s} {r['title'][:44]}")
        print("\nDry run complete. No files written.")
        return 0

    if not have_prompt:
        print("\nRefusing a live run without prompts/abstractor.md.", file=sys.stderr)
        return 1

    # Live path: hand off to Person B's gateway. Import lazily so --dry-run needs none of it.
    try:
        from gateway import LLMGateway, LLMFailure  # type: ignore
    except ImportError:
        for cand in ("backend/app/gateway.py", "backend/gateway.py"):
            sys.path.insert(0, os.path.dirname(os.path.abspath(cand)))
        try:
            from gateway import LLMGateway, LLMFailure  # type: ignore
        except ImportError:
            print("B's gateway not importable yet. Expected backend/app/gateway.py with\n"
                  "  LLMGateway.arun(task, inputs, cache_id=...) and LLMResult\n"
                  "per docs/llm_gateway_spec.md. Re-run with --dry-run until then.",
                  file=sys.stderr)
            return 1

    trace = None
    gw = LLMGateway(models_cfg="config/models.yaml", trace=trace)
    terms = leak_terms(args)
    stats = Counter()
    t0 = time.time()

    with open(OUT, "a") as fout, open(RETRY, "a") as fret:
        for i, rec in enumerate(todo, 1):
            try:
                res = gw.run("abstractor", build_prompt_inputs(rec),
                             cache_id=rec["paper_id"])
                ab = res.data
                err = validate(ab, schema)
                if err:
                    raise LLMFailure("validation", err)
                leaked = check_leak(ab, terms)
                if leaked:
                    stats["leak_rejected"] += 1
                    raise LLMFailure("validation", f"leak_check: named '{leaked}'")
                if not (ab.get("mechanism") or "").strip():
                    # Required for corpus papers: the batch job retries on null.
                    raise LLMFailure("validation", "mechanism is null; required for corpus papers")
                fout.write(json.dumps({"paper_id": rec["paper_id"], "abstraction": ab,
                                       "cached": res.cached, "model": res.model,
                                       "latency_ms": res.latency_ms}, ensure_ascii=False) + "\n")
                fout.flush()
                stats["ok" if not res.cached else "ok_cached"] += 1
            except Exception as e:  # noqa: BLE001
                reason = getattr(e, "reason", type(e).__name__)
                fret.write(json.dumps({"paper_id": rec["paper_id"],
                                       "field": rec["field"], "title": rec["title"],
                                       "reason": reason,
                                       "detail": str(getattr(e, "detail", e))[:300]},
                                      ensure_ascii=False) + "\n")
                fret.flush()
                stats[f"fail:{reason}"] += 1
            if i % 25 == 0 or i == len(todo):
                rate = i / max(time.time() - t0, 1e-9)
                print(f"  {i}/{len(todo)}  {rate:.2f}/s  "
                      f"eta {(len(todo)-i)/max(rate,1e-9):.0f}s  "
                      f"{dict(stats)}", flush=True)

    print(f"\nwrote {OUT}   failures -> {RETRY}")
    for k, v in sorted(stats.items()):
        print(f"  {k:24s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())