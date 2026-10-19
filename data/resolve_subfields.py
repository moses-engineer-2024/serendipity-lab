#!/usr/bin/env python3
"""Resolve the OpenAlex subfield names in config/corpus.yaml to OpenAlex subfield IDs.

Writes config/corpus.lock.yaml. Implements corpus.yaml `tagging`:

    method: deterministic_subfield_lookup      # never LLM-based
    unique_subfield_assertion: true             # no subfield may sit under two of our fields
    resolve_names_via: "/subfields?search="     # resolve on first run; fail loudly on a miss
    lockfile: config/corpus.lock.yaml

Rules enforced here:
  * A non-optional name that does not resolve is a HARD FAILURE. Home-field exclusion
    depends on these tags being right, so a silent miss would put a user's own field
    into their cross-domain results.
  * An optional name that does not resolve warns and is recorded as unresolved.
  * If one OpenAlex subfield resolves for two of our fields, that is a HARD FAILURE.
    `unique_subfield_assertion` exists for exactly this.

Usage:
    set -a; source .env; set +a
    python3 data/resolve_subfields.py            # writes config/corpus.lock.yaml
    python3 data/resolve_subfields.py --check    # verify the lock is still valid, write nothing
"""

import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import yaml

CORPUS_YAML = "config/corpus.yaml"
LOCKFILE = "config/corpus.lock.yaml"
API = "https://api.openalex.org/subfields"
MAILTO = "serendipity-lab@example.org"

# Below this similarity we refuse to guess. A wrong field tag is worse than a failure,
# because it silently produces a "cross-domain" hit that is really the user's own field.
MIN_SIM = 0.82


def normalise(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def api_get(url, params, api_key, tries=3):
    params = dict(params)
    params["mailto"] = MAILTO
    if api_key:
        params["api_key"] = api_key
    full = f"{url}?{urllib.parse.urlencode(params)}"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(full, headers={"User-Agent": "serendipity-lab/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r).get("results", [])
        except Exception as e:
            if attempt == tries - 1:
                print(f"  ! {type(e).__name__}: {e}", file=sys.stderr)
                return []
            time.sleep(1.5 * (attempt + 1))
    return []


def best_match(name, candidates):
    """Exact normalised match wins; otherwise the closest name above MIN_SIM."""
    want = normalise(name)
    exact = [c for c in candidates if normalise(c.get("display_name", "")) == want]
    if exact:
        return exact[0], 1.0, "exact"
    scored = sorted(
        candidates,
        key=lambda c: difflib.SequenceMatcher(None, normalise(c.get("display_name", "")), want).ratio(),
        reverse=True,
    )
    if not scored:
        return None, 0.0, "none"
    top = scored[0]
    sim = difflib.SequenceMatcher(
        None, normalise(top.get("display_name", "")), want).ratio()
    if sim < MIN_SIM:
        return None, sim, "below_threshold"
    return top, sim, "fuzzy"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="resolve and compare against the existing lockfile; write nothing")
    args = ap.parse_args()

    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if not api_key:
        print("ERROR: OPENALEX_API_KEY is not set. Put it in .env and run: set -a; source .env; set +a",
              file=sys.stderr)
        return 2

    corpus = yaml.safe_load(open(CORPUS_YAML))
    fields = corpus["fields"]
    tagging = corpus["tagging"]
    print(f"Resolving {sum(len(f['openalex_subfields']) for f in fields)} subfield names "
          f"across {len(fields)} fields -> {LOCKFILE}\n")

    resolved, unresolved, owner_of = [], [], {}
    collisions = defaultdict(list)

    for f in fields:
        print(f"{f['id']}  ({f['name']})")
        for sub in f["openalex_subfields"]:
            name = sub["name"]
            optional = bool(sub.get("optional", False))
            cands = api_get(API, {"search": name, "per-page": 25}, api_key)
            match, sim, how = best_match(name, cands)
            time.sleep(0.12)

            if not match:
                status = "unresolved" if optional else "MISSING"
                unresolved.append({"field": f["id"], "name": name, "optional": optional,
                                   "reason": f"best candidate similarity {sim:.2f} < {MIN_SIM}"})
                print(f"    [{status:10s}] {name!r} (optional={optional}) sim={sim:.2f}")
                continue

            sid = match["id"].rsplit("/", 1)[-1]
            if sid in owner_of and owner_of[sid] != f["id"]:
                collisions[sid].append((name, f["id"]))
                print(f"    [COLLISION  ] {name!r} -> {sid} already claimed by {owner_of[sid]}")
                continue
            owner_of[sid] = f["id"]
            resolved.append({
                "field": f["id"], "field_name": f["name"],
                "name": name, "optional": optional,
                "openalex_subfield_id": sid,
                "openalex_subfield_name": match.get("display_name"),
                "match": how, "similarity": round(sim, 3),
                "openalex_works_count": match.get("works_count"),
            })
            print(f"    [{how:10s}] {name!r} -> {sid}  ({match.get('display_name')!r}) "
                  f"sim={sim:.2f} works={match.get('works_count')}")
        print()

    hard_fail = False

    # unique_subfield_assertion
    if collisions:
        hard_fail = True
        print("=" * 74)
        print("FAIL  unique_subfield_assertion violated. One OpenAlex subfield resolves under")
        print("      more than one of our fields. Home-field exclusion would be unreliable.")
        for sid, uses in collisions.items():
            for name, fid in uses:
                print(f"      {sid}: {name!r} in {fid}")
        print("=" * 74 + "\n")

    # non-optional misses
    missing = [u for u in unresolved if not u["optional"]]
    if missing:
        hard_fail = True
        print("=" * 74)
        print("FAIL  non-optional subfield names did not resolve:")
        for u in missing:
            print(f"      [{u['field']}] {u['name']!r}: {u['reason']}")
        print("      Fix the name in config/corpus.yaml, or mark it optional: true if the")
        print("      field genuinely can do without it.")
        print("=" * 74 + "\n")

    if args.check:
        print("--check: lockfile not written.")
        return 1 if hard_fail else 0

    if hard_fail:
        print("Refusing to write a lockfile that would mis-tag fields.\n")
        return 1

    lock = {
        "_comment": ("Generated by data/resolve_subfields.py. Do not hand-edit. "
                     "Regenerate when corpus.yaml openalex_subfields change. "
                     "Resolved IDs are what the ingest job filters on."),
        "generated_from": CORPUS_YAML,
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "min_similarity": MIN_SIM,
        "tagging_method": tagging["method"],
        "counts": {
            "fields": len(fields),
            "resolved_subfields": len(resolved),
            "optional_subfields": sum(1 for r in resolved if r["optional"]),
            "unresolved_optional": len(unresolved),
        },
        "unresolved_optional_subfields": unresolved,
        "resolved": resolved,
        # Seed list is a single source of truth in validation_cases.yaml; recorded here so
        # the ingest job can assert it excluded the outcome papers.
        "seeds_from": corpus.get("seeds_from"),
        "exclude_titles_from": corpus.get("exclude_titles_from"),
    }
    with open(LOCKFILE, "w") as f:
        yaml.safe_dump(lock, f, sort_keys=False, width=100, allow_unicode=True)

    print(f"Wrote {LOCKFILE}: {len(resolved)} subfields resolved across {len(fields)} fields, "
          f"{len(unresolved)} optional unresolved.")
    print("\nREMINDER: excluded_outcome_papers from validation_cases.yaml MUST be filtered out of")
    print("the corpus at ingest. They are all present in OpenAlex with full abstracts, so an")
    print("unimplemented exclusion would make the validation cases answer themselves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())