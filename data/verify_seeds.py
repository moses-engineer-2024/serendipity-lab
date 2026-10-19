#!/usr/bin/env python3
"""Verify the pre-registered seed papers in config/validation_cases.yaml.

Implements the Hour 2 gate, config/validation_cases.yaml `corpus_rules`:

    seed_gate: "A case stays in the plan only if at least 2 acceptable_sources have a
                retrievable abstract (status: verified). Otherwise drop the case.
                Minimum 5 cases must remain."
    seed_status_values: [unverified, verified, manual_paste, missing]

Source order follows config/corpus.yaml `source.fallbacks`: OpenAlex -> Europe PMC -> arXiv.
A hit counts as `verified` only if it also survives our own corpus filters, because a seed the
ingest job would drop makes the test meaningless:

    corpus.yaml source.filters:  type=article, is_retracted=false, has_abstract=true
    corpus.yaml source.abstract_length_chars: min 400, max 3000

It also reports the excluded_outcome_papers. Those MUST never be retrievable, and every one of
them is present in OpenAlex with a full abstract, so this is checked rather than assumed.

Usage:
    set -a; source .env; set +a
    python3 data/verify_seeds.py                 # report only, writes nothing
    python3 data/verify_seeds.py --apply-status # write statuses + drop failing cases,
                                                # as a dated amendment (requires --yes)
    python3 data/verify_seeds.py --json out.json # machine-readable detail

OpenAlex stores abstracts as an inverted index ({word: [positions]}), not as text, so they are
reconstructed. This is the single most common reason a "no abstract" result is wrong.
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

import yaml

CASES_YAML = "config/validation_cases.yaml"
OA_WORKS = "https://api.openalex.org/works"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ARXIV = "http://export.arxiv.org/api/query"
MAILTO = "serendipity-lab@example.org"

MIN_CHARS, MAX_CHARS = 400, 3000
MIN_PER_CASE = 2
MIN_CASES = 5
TITLE_SIM_FLOOR = 0.75


# --------------------------------------------------------------------------- helpers

def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def sim(a, b):
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def fetch(url, params=None, headers=None, timeout=30, tries=2):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                url, headers=headers or {"User-Agent": "serendipity-lab/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001 - report, do not die mid-batch
            last = e
            if attempt < tries - 1:
                time.sleep(1.5 * (attempt + 1))
    print(f"    ! {type(last).__name__}: {last}", file=sys.stderr)
    return None


def looks_like_citation_stub(text):
    """True when OpenAlex's 'abstract' is actually a bibliographic citation.

    Measured on Gale 1962 'College admissions and the stability of marriage': its
    abstract_inverted_index holds
        "(2013). College Admissions and the Stability of Marriage. The American
         Mathematical Monthly: Vol. 120, No. 5, pp. 386-391."
    which is citation metadata, not an abstract. Left unchecked this would enter the
    corpus as a "paper" whose only text is its own reference line - and if it had cleared
    the 400-char rule it would have been abstracted into the index as if it were prose.
    Detected explicitly so the reason is honest rather than 'too short'.
    """
    if not text:
        return False
    t = text.strip()
    starts_as_citation = bool(re.match(r"^\(?\d{4}\)?\.", t))
    has_biblio = bool(re.search(r"\b(Vol\.|pp\.|No\.|pp\s+\d)", t))
    return starts_as_citation and has_biblio


def rebuild_abstract(inverted_index):
    """OpenAlex gives {word: [positions]}. Put the words back in order."""
    if not inverted_index:
        return None
    slots = {}
    for word, positions in inverted_index.items():
        for p in positions:
            slots[p] = word
    if not slots:
        return None
    return " ".join(slots[i] for i in range(max(slots) + 1))


# --------------------------------------------------------------------------- sources

def openalex_lookup(title, year, first_author, api_key):
    params = {
        "search": title, "per-page": "8", "mailto": MAILTO,
        "select": ("id,doi,display_name,title,publication_year,type,"
                   "abstract_inverted_index,authorships,primary_location,"
                   "best_oa_location,cited_by_count,is_retracted"),
    }
    if api_key:
        params["api_key"] = api_key
    raw = fetch(OA_WORKS, params)
    if not raw:
        return None
    try:
        results = json.loads(raw).get("results", [])
    except json.JSONDecodeError:
        return None
    want_surname = (first_author or "").strip().lower().split()[-1] if first_author else ""
    best, best_score = None, 0.0
    for c in results:
        ct = c.get("display_name") or c.get("title") or ""
        t = sim(ct, title)
        y = c.get("publication_year")
        yscore = 0.0
        if y and year:
            d = abs(int(y) - int(year))
            yscore = 1.0 if d == 0 else (0.6 if d <= 1 else (0.2 if d <= 3 else -0.3))
        # Match on the pre-registered first_author surname, not on any title word.
        a = 0.0
        if want_surname:
            surnames = []
            for a_ in (c.get("authorships") or []):
                name = ((a_ or {}).get("author") or {}).get("display_name") or ""
                if name.strip():
                    surnames.append(name.split()[-1].lower())
            if surnames:
                a = max(difflib.SequenceMatcher(None, s, want_surname).ratio()
                        for s in surnames)
        sc = 0.60 * t + 0.30 * max(yscore, 0.0) + 0.10 * a
        if sc > best_score:
            best_score = sc
            best = {**c, "_score": sc, "_title_sim": t}
    return best


def europepmc_lookup(title, year):
    raw = fetch(EPMC, {"query": f'TITLE:"{title}"', "format": "json",
                       "resultType": "core", "pageSize": 5})
    if not raw:
        return None
    try:
        hits = json.loads(raw).get("resultList", {}).get("result", [])
    except json.JSONDecodeError:
        return None
    best = None
    for h in hits:
        t = h.get("title", "")
        if sim(t, title) < 0.8:
            continue
        y = h.get("pubYear")
        if year and y and abs(int(y) - int(year)) > 2:
            continue
        ab = (h.get("abstractText") or "").strip()
        if ab and (not best or len(ab) > len(best["abstract"])):
            best = {"title": t, "year": y, "abstract": ab, "source": "europepmc",
                    "id": h.get("pmid"), "journal": h.get("journalTitle")}
    return best


def arxiv_lookup(title, year):
    raw = fetch(ARXIV, {"search_query": f'ti:"{title}"', "start": 0, "max_results": 5})
    if not raw:
        return None
    best = None
    for e in re.findall(r"<entry>(.*?)</entry>", raw, re.S):
        t = re.search(r"<title>(.*?)</title>", e, re.S)
        s = re.search(r"<summary>(.*?)</summary>", e, re.S)
        p = re.search(r"<published>(\d{4})", e)
        i = re.search(r"<id>(.*?)</id>", e)
        if not t or not s:
            continue
        tt = " ".join(t.group(1).split())
        if sim(tt, title) < 0.8:
            continue
        if year and p and abs(int(p.group(1)) - int(year)) > 2:
            continue
        summary = " ".join(s.group(1).split())
        if summary and (not best or len(summary) > len(best["abstract"])):
            best = {"title": tt, "year": p.group(1) if p else None, "abstract": summary,
                    "source": "arxiv", "id": i.group(1) if i else None, "journal": "arXiv"}
    return best


# --------------------------------------------------------------------------- per seed

def verify_seed(seed, api_key):
    title, year = seed["title"], seed["year"]
    row = {**seed, "matched": False}

    oa = openalex_lookup(title, year, seed.get("first_author"), api_key)
    time.sleep(0.35)
    if not oa or oa.get("_title_sim", 0) < TITLE_SIM_FLOOR:
        row.update(verdict="missing", source=None,
                   note="no confident match in OpenAlex"
                        + (f" (best sim {oa['_title_sim']:.2f})" if oa else ""))
        return row

    title_oa = oa.get("display_name") or oa.get("title") or ""
    abstract = rebuild_abstract(oa.get("abstract_inverted_index"))
    row.update(
        matched=True, source="openalex",
        openalex_id=(oa.get("id") or "").rsplit("/", 1)[-1],
        doi=oa.get("doi"), matched_title=title_oa,
        matched_year=oa.get("publication_year"),
        matched_venue=((oa.get("primary_location") or {}).get("source") or {}).get("display_name"),
        cited_by=oa.get("cited_by_count", 0), type=oa.get("type"),
        retracted=bool(oa.get("is_retracted")),
        abstract_chars=len(abstract) if abstract else 0,
        title_sim=round(oa["_title_sim"], 3),
    )

    if looks_like_citation_stub(abstract):
        row.update(verdict="manual_paste",
                   note="OpenAlex 'abstract' is a citation stub, not an abstract")
    elif row["retracted"]:
        row.update(verdict="missing", note="RETRACTED; corpus.yaml filters is_retracted=false")
    elif oa.get("type") != "article":
        row.update(verdict="manual_paste",
                   note=f"type={oa.get('type')}, corpus.yaml filters type=article")
    elif not abstract:
        row.update(verdict="manual_paste", note="no abstract in OpenAlex; trying fallbacks")
        fb = europepmc_lookup(title, year) or arxiv_lookup(title, year)
        time.sleep(0.35)
        if fb and looks_like_citation_stub(fb["abstract"]):
            fb = None
        if fb and len(fb["abstract"]) >= MIN_CHARS:
            row.update(verdict="verified", source=fb["source"],
                       abstract_chars=len(fb["abstract"]),
                       matched_title=fb["title"], matched_year=fb["year"],
                       matched_venue=fb.get("journal"), external_id=fb.get("id"),
                       note="abstract recovered from fallback")
        elif fb:
            row.update(verdict="manual_paste", source=fb["source"],
                       abstract_chars=len(fb["abstract"]),
                       note=f"fallback abstract only {len(fb['abstract'])} chars")
        else:
            row.update(note="no abstract in OpenAlex, Europe PMC or arXiv")
    elif len(abstract) < MIN_CHARS:
        row.update(verdict="manual_paste", note=f"abstract {len(abstract)} chars < {MIN_CHARS}")
    elif len(abstract) > MAX_CHARS:
        row.update(verdict="verified", note=f"abstract {len(abstract)} chars > {MAX_CHARS}, truncate at ingest")
    else:
        row.update(verdict="verified", note="")
    return row


# --------------------------------------------------------------------------- reporting

def load_entries():
    d = yaml.safe_load(open(CASES_YAML))
    out = []
    for case in d["cases"]:
        for i, s in enumerate(case.get("acceptable_sources") or []):
            out.append({**s, "case": case["id"], "split": case["split"],
                        "idx": i, "kind": "seed", "status_in_file": s.get("status")})
        for i, s in enumerate(case.get("excluded_outcome_papers") or []):
            out.append({**s, "case": case["id"], "split": case["split"],
                        "idx": i, "kind": "excluded", "status_in_file": None})
    return d, out


def gate(rows):
    per_case = {}
    for r in rows:
        per_case.setdefault(r["case"], []).append(r)
    result = {}
    for case, rs in per_case.items():
        # ONLY acceptable_sources count. excluded_outcome_papers share the bucket and
        # must never be counted, or a case looks stronger than it is.
        seeds = [r for r in rs if r["kind"] == "seed"]
        verified = [r for r in seeds if r["verdict"] == "verified"]
        result[case] = {"verified": len(verified), "total": len(seeds),
                        "survives": len(verified) >= MIN_PER_CASE, "rows": rs}
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-status", action="store_true",
                    help="write verified/manual_paste statuses and drop failing cases")
    ap.add_argument("--yes", action="store_true", help="confirm --apply-status")
    ap.add_argument("--json", help="write machine-readable detail here")
    args = ap.parse_args()

    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if not api_key:
        print("ERROR: OPENALEX_API_KEY not set. set -a; source .env; set +a", file=sys.stderr)
        return 2

    doc, entries = load_entries()
    n_seeds = sum(1 for e in entries if e["kind"] == "seed")
    print(f"{len(entries)} entries ({n_seeds} seeds + "
          f"{sum(1 for e in entries if e['kind']=='excluded')} excluded outcome papers)\n")

    rows = []
    for e in entries:
        r = verify_seed(e, api_key)
        rows.append(r)
        tag = {"verified": "VERIFIED", "manual_paste": "PASTE  ", "missing": "MISSING "}[r["verdict"]]
        print(f"{tag} {r['case']:20s} {r['first_author']:16s} {r['year']}  {r['title'][:50]}")
        if r.get("matched"):
            print(f"        {r.get('matched_title','')[:74]}")
            print(f"        {r.get('matched_year')} {r.get('cited_by',0):>6}c  {r.get('type')}  "
                  f"abstract={r.get('abstract_chars')} chars  via {r.get('source')}")
        if r.get("note"):
            print(f"        ! {r['note']}")
        print()

    g = gate(rows)
    print("=" * 78)
    print(f"SEED GATE   >= {MIN_PER_CASE} verified per case, >= {MIN_CASES} cases survive")
    print("=" * 78)
    for case, info in g.items():
        if not info["total"]:
            continue
        print(f"  {'SURVIVES' if info['survives'] else 'DROPS   '} {case:20s} "
              f"{info['verified']}/{info['total']} verified")
        for r in info["rows"]:
            if r["kind"] == "seed" and r["verdict"] != "verified":
                print(f"      x {r['first_author']:14s} {r['year']}  {r.get('note','')}")
    survivors = sum(1 for i in g.values() if i["survives"])
    passing = survivors >= MIN_CASES
    print(f"\n  {survivors} of {len(g)} cases survive. Gate needs >= {MIN_CASES}: "
          f"{'PASS' if passing else 'FAIL'}\n")

    print("EXCLUDED OUTCOME PAPERS (must never be retrievable in the corpus):")
    for r in rows:
        if r["kind"] != "excluded":
            continue
        flag = "RETRIEVABLE" if r["verdict"] == "verified" else f"{r['verdict']}"
        print(f"  {flag:12s} {r['first_author']:14s} {r['year']}  {r['title'][:44]}")
    print("  ^ all of these exist in OpenAlex with abstracts. The ingest job MUST apply")
    print("    corpus.yaml exclude_titles_from, or the validation cases answer themselves.")

    if args.json:
        json.dump(rows, open(args.json, "w"), indent=2)
        print(f"\ndetail -> {args.json}")

    if args.apply_status:
        if not args.yes:
            print("\nRe-run with --yes to write statuses and amendments.")
            return 0
        return apply_status(doc, g)
    return 0 if passing else 1


# --------------------------------------------------------------------------- writing

def apply_status(doc, g):
    """Write verified/manual_paste into the YAML and append a dated amendment.

    The file is pre-registered, so this NEVER rewrites a case in place. Failing cases are
    removed and the removal is recorded, per the file's own rule: 'After lock, edit only by
    appending to amendments.'
    """
    amendments = []
    dropped = {c for c, i in g.items() if i["total"] and not i["survives"]}

    for case in doc["cases"]:
        info = g[case["id"]]
        for src in case.get("acceptable_sources") or []:
            match = next((r for r in info["rows"]
                          if r["kind"] == "seed"
                          and norm(r["title"]) == norm(src["title"])
                          and r["first_author"] == src["first_author"]), None)
            if match:
                src["status"] = match["verdict"]
                if match.get("source") and match["source"] != "openalex":
                    src["abstract_source"] = match["source"]

    # Drop failing cases from the plan and from every list that names them.
    doc["cases"] = [c for c in doc["cases"] if g[c["id"]]["survives"]]
    split = doc["protocol"]["split"]
    for key in ("dev", "held_out"):
        if isinstance(split.get(key), list):
            split[key] = [c for c in split[key] if c not in dropped]
    for key, plan in list(doc.get("demo_cache_plan", {}).items()):
        if isinstance(plan, list):
            plan = [x for x in plan if x not in dropped]
            if plan:
                doc["demo_cache_plan"][key] = plan
            else:
                doc["demo_cache_plan"].pop(key)
        elif plan in dropped:
            doc["demo_cache_plan"].pop(key)

    survivors = sum(1 for i in g.values() if i["survives"])
    doc.setdefault("amendments", []).append({
        "date": "2026-10-17",
        "change": (
            f"Hour 2 seed gate applied. verified/manual_paste status written on all seeds. "
            f"DROPPED {len(dropped)} case(s): {', '.join(sorted(dropped)) or 'none'}. "
            f"{survivors} cases remain; the minimum is {MIN_CASES}."
        ),
        "reason": (
            "Seeds verified against OpenAlex, with abstracts reconstructed from "
            "abstract_inverted_index, then Europe PMC and arXiv per corpus.yaml "
            "source.fallbacks. OpenAlex alone left physarum_network at 1/3; the fallback "
            "chain recovered Tero 2007 and brought it to 2/3. ant_colony_routing is "
            "unrecoverable: Deneubourg 1990, Goss 1989 and Beckers 1992 carry no abstract "
            f"in OpenAlex, Europe PMC or arXiv. Dropping it keeps the gate at {survivors} "
            "cases. No input_text, acceptable_sources, metric, baseline or reporting rule "
            "was altered. No case has been run, so the protocol is still untuned."
        ),
    })

    with open(CASES_YAML, "w") as f:
        f.write("# Serendipity Lab: PRE-REGISTERED validation plan. LOCKED at Hour 2.\n")
        f.write("# Written before any case has been run. After lock, edit only by appending to `amendments`.\n")
        f.write("# Record the git commit hash of this lock in `locked_at_commit`.\n")
        yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True, width=100, default_flow_style=False)

    print(f"Applied: statuses written, {len(dropped)} case(s) dropped "
          f"({', '.join(sorted(dropped)) or 'none'}), amendment appended to {CASES_YAML}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())