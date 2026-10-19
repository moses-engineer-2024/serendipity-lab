#!/usr/bin/env python3
"""Live check: does prompts/abstractor.md actually stop the leak?

The work plan calls the few-shots "the single highest-leverage artifact in this project",
and gateway rule 17 treats a leak as a failure rather than a warning. Neither claim is
worth anything untested, so this runs the real prompt against the real model on the three
cases that matter most:

  1. the hero user input   - must be leak-free AND `mechanism` must be null (D14)
  2. a jamming seed paper  - must be leak-free AND `mechanism` must be present (required
                             for corpus papers)
  3. the gecko dev case    - must not name the answer (van der Waals, silicone, PDMS)

It also exercises the schema translation from gateway rule 14, because Gemini's
responseSchema rejects `additionalProperties` and union types, and that translation is
itself a thing that can silently break.

Usage:
    set -a; source .env; set +a
    python3 data/check_abstractor_prompt.py
"""

import importlib.util
import json
import os
import sys
import time
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = load("ac", "abstract_corpus.py")

PROMPT = open(os.path.join(HERE, "..", "prompts", "abstractor.md")).read()
SCHEMA = json.load(open(os.path.join(HERE, "..", "config", "schemas", "abstraction.schema.json")))
CASES = yaml.safe_load(open(os.path.join(HERE, "..", "config", "validation_cases.yaml")))["cases"]

# Terms that would mean the answer leaked. Per-case, because "gripper" leaking into a
# robotics query is a leak while "gripper" inside domain_tags is required.
LEAK_TERMS = ac.GENERIC_LEAK_TERMS + [
    "van der waals", "setae", "pdm s", "pdms", "silicone", "elastomer",
]

TYPE_MAP = {"string": "STRING", "array": "ARRAY", "object": "OBJECT",
            "number": "NUMBER", "boolean": "BOOLEAN"}


def translate(node, drop_from_required=()):
    """JSON Schema -> Gemini responseSchema, per gateway rule 14.

    Drops additionalProperties, minLength/maxLength/minItems/maxItems and union types,
    which Gemini rejects with HTTP 400. Enforcement of those moves to post-validation.

    `drop_from_required` implements rule 15. Measured: because Gemini cannot express
    `["string","null"]`, a nullable field listed in `required` is forced to STRING, and the
    model then satisfies it with the literal text "null" instead of omitting the key. That
    turns a null into the string "null", which is truthy downstream and would be indexed as
    a real mechanism. So a nullable field is omitted from `required` for calls that allow
    null, and absence is mapped back to None after validation.
    """
    t = node.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), "STRING")
    out = {"type": TYPE_MAP.get(t, "STRING")}
    if "items" in node:
        out["items"] = translate(node["items"], drop_from_required)
    if "properties" in node:
        out["properties"] = {k: translate(v, drop_from_required)
                             for k, v in node["properties"].items()}
    req = [r for r in node.get("required", []) if r not in drop_from_required]
    if req:
        out["required"] = req
    if "description" in node:
        out["description"] = node["description"]
    return out


def call(text, nullable=(), tries=3):
    system = PROMPT.split("## SYSTEM")[1].split("## USER")[0]
    body = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT.replace("{{text}}", text)}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {
            "temperature": 0, "maxOutputTokens": 1400,
            "responseMimeType": "application/json",
            "responseSchema": translate(SCHEMA, drop_from_required=nullable),
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-3.8-flash:generateContent?key=" + os.environ["GEMINI_API_KEY"])
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    for attempt in range(tries):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=180))
            raw = "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"]
                          if not p.get("thought"))
            parsed = json.loads(raw)
            # Rule 15: absence means null. Also normalise the literal text "null", which is
            # what a model returns when a STRING-typed key is required but the answer is none.
            for k in nullable:
                v = parsed.get(k)
                if isinstance(v, str) and v.strip().lower() in ("null", "none", "n/a", ""):
                    parsed[k] = None
            return parsed, None
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:80]}"
            if attempt < tries - 1:
                print(f"    retry {attempt + 1}/{tries}: {err}", flush=True)
                time.sleep(6 * (attempt + 1))
    return None, err


def corpus_seed_containing(word):
    p = os.path.join(HERE, "corpus", "corpus.jsonl")
    for line in open(p):
        r = json.loads(line)
        if r.get("is_seed") and word in (r["title"] or "").lower():
            return f"Title: {r['title']}\n\n{r['abstract']}"
    return None


def main():
    jamming = corpus_seed_containing("jamming at zero temperature")
    tests = [
        {"name": "hero user input (robotics -> physics)",
         "text": CASES[0]["input_text"].strip(),
         "expect_mechanism": False,          # D14: user input states no approach
         "banned": ["granular", "jamming", "vacuum", "particle", "coffee"]},
        {"name": "gecko dev case (materials -> biology)",
         "text": CASES[1]["input_text"].strip(),
         "expect_mechanism": False,
         "banned": ["van der waals", "silicone", "pdms", "elastomer", "setae", "gecko "]},
        {"name": "jamming seed PAPER (corpus)",
         "text": jamming,
         "expect_mechanism": True,           # required for corpus papers
         "banned": []},
    ]

    results = []
    for t in tests:
        print(f"\n{'=' * 74}\n{t['name']}")
        if not t["text"]:
            print("  SKIP: no input text")
            results.append(False)
            continue
        nullable = () if t["expect_mechanism"] else ("mechanism",)
        out, err = call(t["text"], nullable=nullable)
        if not out:
            print(f"  FAILED: {err}")
            results.append(False)
            continue
        schema_err = ac.validate(out, SCHEMA)
        leak = ac.check_leak(out, LEAK_TERMS)
        mech = out.get("mechanism")
        has_mech = bool(mech and str(mech).strip())
        fp = out.get("functional_problem", "")
        # functional_problem must not name the INPUT's own field either: that is what the
        # abstraction exists to remove.
        banned_fp = [b for b in t["banned"] if b in fp.lower()]
        mech_ok = has_mech == t["expect_mechanism"]

        print(f"  schema valid      : {'OK' if not schema_err else schema_err}")
        print(f"  leak (solution)   : {leak or 'none'}")
        print(f"  leak in func_prob : {banned_fp or 'none'}")
        print(f"  mechanism         : {'present' if has_mech else 'null'} "
              f"(expected {'present' if t['expect_mechanism'] else 'null'}) -> "
              f"{'OK' if mech_ok else 'MISMATCH'}")
        print(f"  functional_problem: {fp}")
        print(f"  mechanism         : {str(mech)[:120]}")
        print(f"  domain_tags       : {out.get('domain_tags')}")
        good = not schema_err and not leak and not banned_fp and mech_ok
        results.append(good)
        print(f"  => {'PASS' if good else 'FAIL'}")

    n = sum(1 for r in results if r)
    print(f"\n{'=' * 74}\n{n}/{len(results)} passed")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())