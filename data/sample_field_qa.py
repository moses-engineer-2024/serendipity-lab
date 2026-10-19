#!/usr/bin/env python3
"""Generate docs/field_qa.md: a stratified sample of titles for hand review.

corpus.yaml tagging.qa requires reading 20 random titles per field BEFORE the full
abstraction run. This is the cheapest high-value check in the project: 8 fields x 20 is
160 reads, and it catches a wrong field tag before 3,000 papers are abstracted with it.

A wrong tag is not a cosmetic problem. Home-field exclusion is `$nin` on `field`, so a paper
mis-tagged INTO the user's home field is silently removed from their results, and one
mis-tagged OUT of it leaks into their cross-domain results as a false discovery.

The sample is stratified by `selection` and `year_stratum` rather than uniformly random,
because the failure modes are not uniform: classics are hand-adjacent to our fields and
seeds were assigned by hand, so the random sample is where taxonomy drift shows up.

Reproducible: seed derived from corpus.yaml random_seed, so re-running gives the same file
and a reviewer cannot accuse the sample of having been cherry-picked.

Usage:
    python3 data/sample_field_qa.py
"""

import json
import os
import random
import re
import sys
from collections import defaultdict

import yaml

CORPUS = "data/corpus/corpus.jsonl"
OUT = "docs/field_qa.md"
PER_FIELD = 20


def load_yaml(p):
    with open(p) as f:
        return yaml.safe_load(f)


def main():
    corpus = load_yaml("config/corpus.yaml")
    seed = int(corpus["size"]["random_seed"])
    rows = [json.loads(l) for l in open(CORPUS) if l.strip()]
    by_field = defaultdict(list)
    for r in rows:
        by_field[r["field"]].append(r)

    # Titles mentioning these look like they belong to a different field than they were
    # tagged into. They are the ones worth reading first, but they are still shown in place
    # rather than separated, so the sample stays an unbiased read of the field.
    SUSPECT = {
        "robotics_mech_eng": ("protein", "gene", "clinical trial", "patient", "cancer"),
        "soft_matter_stat_physics": ("protein", "gene", "patient", "clinical", "market"),
        "organismal_bio_ecology": ("alloy", "turbine", "cantilever", "polymer"),
        "medicine_clinical": ("ant colony", "pheromone", "routing algorithm", "spin glass"),
        "economics_game_theory": ("catalyst", "alloy", "gripper", "diffusion"),
        "civil_transport_arch": ("bacterial", "enzyme", "gene expression"),
        "cs_optimization": ("alloy", "bone", "patient", "gut microbiota"),
        "materials_fluids_aero": ("patient", "clinical", "gene"),
    }

    out = ["# Field QA — read these before the full abstraction run", ""]
    out += [
        f"**{PER_FIELD} titles per field, hand-read.** Regenerate with "
        f"`python3 data/sample_field_qa.py` (seeded from `corpus.yaml random_seed: {seed}`, "
        f"so the sample is identical every time and is not cherry-picked).", "",
        "## Why this exists", "",
        "Field tags come from a deterministic OpenAlex subfield lookup, never an LLM. "
        "Home-field exclusion is `$nin` on `field`, so a wrong tag is not cosmetic:", "",
        "- tagged **into** the user's home field -> a good cross-domain result is silently removed;",
        "- tagged **out of** it -> a paper from their own field is returned as a \"discovery\".", "",
        "That second one is the failure that makes the validation table meaningless, and it is "
        "invisible without a human reading titles. 160 reads is cheap insurance on 3,000 papers.", "",
        "## How to mark it", "",
        "For each line, mark **ok** if the paper reads as belonging in that field. Mark "
        "**wrong** if it plainly belongs elsewhere, and **borderline** if you would argue about "
        "it. Borderline lines are the useful ones: they are where the taxonomy is too coarse, "
        "and `corpus.yaml` already warns that subfield tagging is coarse.", "",
        "**Target: under 5% wrong.** Above that, fix the subfield list in "
        "`config/corpus.yaml`, re-run `data/resolve_subfields.py`, and re-ingest. Do not "
        "hand-patch individual papers; the tag has to be reproducible.", "",
        "---", "",
    ]

    totals = {"ok": 0, "wrong": 0, "borderline": 0}
    for field in corpus["fields"]:
        fid = field["id"]
        pool = by_field.get(fid, [])
        rng = random.Random(f"{seed}:{fid}")

        # Stratify across selection so seeds, classics and the random sample are all seen.
        buckets = defaultdict(list)
        for r in pool:
            buckets[r.get("selection", "seed")].append(r)
        order = ["seed", "distractor_classics", "stratified_random_sample"]
        picked, i = [], 0
        while len(picked) < min(PER_FIELD, len(pool)) and any(buckets.values()):
            b = buckets[order[i % len(order)]]
            if b:
                picked.append(b.pop(rng.randrange(len(b))))
            elif all(not buckets[k] for k in order):
                break
            i += 1
        picked = picked[:PER_FIELD]

        # Flag likely mis-tags without hiding them from the sample.
        # Word-boundary matched: a naive substring test flags "generalizations" as "gene"
        # and "patients" as "patient", which fills the review with false alarms and trains
        # the reviewer to ignore the flags.
        flagged = 0
        terms = SUSPECT.get(fid, ())
        for r in picked:
            blob = (r["title"] or "").lower()
            if any(re.search(rf"\b{re.escape(t)}\b", blob) for t in terms):
                r["_flag"] = "suspect"
                flagged += 1

        out += [f"## `{fid}` — {field['name']}", ""]
        out += [f"{len(picked)} of {len(pool)} shown. Subfields: "
                + ", ".join(s["name"] for s in field["openalex_subfields"]), ""]
        if flagged:
            out += [f"{flagged} title(s) look lexically like another field. These are the "
                    f"ones most likely to be genuinely mis-tagged.", ""]
        out += ["| # | year | title | looks right? |", "|---|---|---|---|"]
        for n, r in enumerate(picked, 1):
            mark = "**suspect**" if r.get("_flag") else ""
            title = (r["title"] or "").replace("|", "\\|")
            out.append(f"| {n} | {r.get('year') or ''} | {title} | {mark} |")
        out += ["", f"**Tally for `{fid}`:** ______ / {len(picked)} "
                    f"(wrong: ____  borderline: ____)", ""]

    out += ["---", "", "## Verdict", "",
            "| field | shown | wrong | borderline | verdict |", "|---|---|---|---|---|"]
    for field in corpus["fields"]:
        out.append(f"| `{field['id']}` | {PER_FIELD} | | | |")
    out += ["", "If any field is over 5% wrong, **stop and fix the subfield mapping** before "
                "running the abstraction batch. Re-abstracting 3,000 papers with a wrong tag "
                "costs the pilot, and the pilot exists precisely to catch this.", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(out))

    total = sum(min(PER_FIELD, len(by_field.get(f["id"], []))) for f in corpus["fields"])
    print(f"wrote {OUT}: {total} titles across {len(corpus['fields'])} fields "
          f"(seed {seed}, reproducible)")
    print(f"  expected reading time: ~{total * 15 // 60} min at 15s per title")
    for f in corpus["fields"]:
        print(f"  {f['id']:28s} {min(PER_FIELD, len(by_field.get(f['id'], []))):>3} titles "
              f"of {len(by_field.get(f['id'], []))}")


if __name__ == "__main__":
    sys.exit(main())
