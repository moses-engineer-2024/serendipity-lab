#!/usr/bin/env python3
"""Build the Serendipity Lab corpus: 3,000 abstracts, 8 fields, reproducible.

Implements config/corpus.yaml end to end:

  size            3,000 total, 375 per field, 600-pilot mode, 25 classics per field, seed 42
  source          OpenAlex, year-stratified sampling, abstract 400-3000 chars, dedupe on DOI
  filters         has_abstract, type=article, language=en, is_retracted=false
  seeds_from      config/validation_cases.yaml  (single source of truth for seed papers)
  exclude_titles_from  config/validation_cases.yaml  (excluded_outcome_papers)
  selection_order_per_field  seeds -> distractor_classics -> stratified_random_sample
  tagging         deterministic subfield lookup via config/corpus.lock.yaml, never an LLM
  conflict_policy drop        (a paper whose subfields map to >1 of our fields is dropped)
  known_biases    reported, not hidden

THE EXCLUSION IS THE POINT. `excluded_outcome_papers` are the breakthrough papers the whole
validation rests on. All of them exist in OpenAlex with full abstracts, so if this filter is
wrong the cases answer themselves and every number in the deck is meaningless. It is therefore
applied on every write path, verified after the run, and reported explicitly.

Resumable: re-running skips papers already written. Safe to interrupt.

Usage:
    set -a; source .env; set +a
    python3 data/ingest_corpus.py --pilot            # 600 papers, for the by-hand pilot
    python3 data/ingest_corpus.py                   # full 3,000
    python3 data/ingest_corpus.py --report-only     # verify an existing corpus
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

import yaml

CORPUS_YAML = "config/corpus.yaml"
LOCK_YAML = "config/corpus.lock.yaml"
CASES_YAML = "config/validation_cases.yaml"
OUT_DIR = "data/corpus"
OUT_JSONL = f"{OUT_DIR}/corpus.jsonl"
OUT_MANIFEST = f"{OUT_DIR}/manifest.json"
API = "https://api.openalex.org/works"
MAILTO = "serendipity-lab@example.org"


# --------------------------------------------------------------------------- http

def api_get(params, api_key, tries=4):
    params = dict(params)
    params["api_key"] = api_key
    params["mailto"] = MAILTO
    url = f"{API}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "serendipity-lab/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            wait = 2 ** attempt
            print(f"    ! {type(e).__name__}: {str(e)[:90]} (retry in {wait}s)", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"OpenAlex failed after {tries} tries: {last}")


SELECT = ("id,doi,display_name,publication_year,type,language,cited_by_count,is_retracted,"
          "abstract_inverted_index,authorships,primary_topic,primary_location")


def rebuild_abstract(inv):
    """OpenAlex gives {word: [positions]}. It does NOT give abstract text.

    The index has HOLES: measured on a 200-work page, some records skip positions, so
    indexing `range(max+1)` raises KeyError. Sort the pairs and join what is actually
    present, which preserves reading order and cannot crash.
    """
    if not inv:
        return None
    pairs = []
    for w, ps in inv.items():
        if not ps:
            continue
        for p in ps:
            pairs.append((p, w))
    if not pairs:
        return None
    pairs.sort(key=lambda x: x[0])
    return " ".join(w for _, w in pairs)


def safe_accept(flt, work, **kw):
    """accept() wrapped so one malformed record cannot abort a 3,000-paper run."""
    try:
        return flt.accept(work, **kw)
    except Exception as e:  # noqa: BLE001
        flt.stats["drop_record_error"] += 1
        print(f"    ! record error ({type(e).__name__}: {str(e)[:60]}) skipped",
              file=sys.stderr)
        return None, "record_error"


def norm_title(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def or_filter(ids):
    """OpenAlex ORs values inside one filter with `|`. A comma is AND and is rejected.

    Accepts a list of ids, or a string that is already pipe-joined. This matters: passing
    a joined string straight through used to iterate its CHARACTERS, turning "2207|2210"
    into "2|2|0|7||", which matches nothing and silently yields an empty corpus.
    """
    if isinstance(ids, str):
        return ids
    return "|".join(str(i) for i in ids)


# corpus.yaml source.filters, applied server-side so we do not fetch thousands of rows only
# to discard them locally. Kept in sync with Filter.accept, which re-checks defensively.
def source_filter(corpus):
    f = corpus["source"]["filters"]
    parts = []
    if f.get("has_abstract"):
        parts.append("has_abstract:true")
    if f.get("type"):
        parts.append(f"type:{f['type']}")
    if f.get("language"):
        parts.append(f"language:{f['language']}")
    if f.get("is_retracted") is False:
        parts.append("is_retracted:false")
    return ",".join(parts)


def epmc_abstract(title):
    """Europe PMC fallback, used for seeds OpenAlex has no abstract for.

    Returns (abstract_or_None, source_name). corpus.yaml source.fallbacks lists
    pubmed before arxiv; Europe PMC covers PubMed and PMC in one endpoint.
    """
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
           + urllib.parse.urlencode({"query": f'TITLE:"{title}"', "format": "json",
                                     "resultType": "core", "pageSize": 5}))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "serendipity-lab/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            hits = json.load(r).get("resultList", {}).get("result", [])
    except Exception:  # noqa: BLE001
        return None, "europepmc"
    best = ""
    for h in hits:
        t = (h.get("title") or "").rstrip(".")
        if norm_title(t) != norm_title(title):
            continue
        ab = (h.get("abstractText") or "").strip()
        if len(ab) > len(best):
            best = ab
    return (best or None), "europepmc"


# --------------------------------------------------------------------------- filtering

class Filter:
    """Applies every corpus.yaml rule at one place, so no write path can bypass it."""

    def __init__(self, corpus, cases):
        self.src = corpus["source"]
        self.len_min = self.src["abstract_length_chars"]["min"]
        self.len_max = self.src["abstract_length_chars"]["max"]
        self.dedupe_on = self.src.get("dedupe_on", "doi")
        f = self.src["filters"]
        self.want_type = f.get("type", "article")
        self.want_lang = f.get("language", "en")
        self.no_retracted = bool(f.get("is_retracted"))
        self.want_abstract = bool(f.get("has_abstract"))
        # subfield id -> our field id
        self.subfield_to_field = {}
        lock = yaml.safe_load(open(LOCK_YAML))
        for r in lock["resolved"]:
            self.subfield_to_field[str(r["openalex_subfield_id"])] = r["field"]
        self.claimed = {str(r["openalex_subfield_id"]) for r in lock["resolved"]}
        self.excluded_titles = set()
        self.excluded_authors = defaultdict(set)
        for case in cases["cases"]:
            for p in case.get("excluded_outcome_papers") or []:
                self.excluded_titles.add(norm_title(p["title"]))
                if p.get("first_author"):
                    self.excluded_authors[p["first_author"]].add(int(p["year"]))
        # Outcome papers of DROPPED cases stay excluded. Dropping ant_colony_routing must
        # not silently un-exclude Dorigo 1996 from the corpus: a breakthrough paper
        # cannot enter the corpus just because its validation case failed the seed gate.
        for p in cases.get("excluded_outcome_papers_dropped") or []:
            self.excluded_titles.add(norm_title(p["title"]))
            if p.get("first_author"):
                self.excluded_authors[p["first_author"]].add(int(p["year"]))
        self.stats = Counter()

    def tag_field(self, work, fetched_under):
        """Deterministic assignment. Returns (field, reason).

        The corpus is *defined* by OpenAlex primary-topic subfield: a paper is fetched
        under field F because its `primary_topic.subfield.id` is in F's locked subfield
        list, so F is its field. Assignment and fetch therefore use the same criterion and
        cannot disagree.

        Measured reason this matters: OpenAlex classifies O'Hern's 2003 jamming paper and
        Metropolis' 1953 paper under "Materials Chemistry" and "Biomedical Engineering"
        respectively, not physics. Reading `topics` instead of `primary_topic` finds the
        right subfield for those, but then genuinely interdisciplinary papers collide -
        the gecko-setae paper hits both materials and robotics, and "School Choice" hits both
        cs_optimization and economics_game_theory. Using primary_topic for both fetch and
        assignment keeps the rule deterministic and avoids that ambiguity.

        `primary_topic` is still re-checked defensively, so an API surprise drops the paper
        instead of silently mis-tagging it. A wrong field tag produces a "cross-domain"
        result that is really the user's own field, and home-field exclusion depends on
        this being right.
        """
        topic = work.get("primary_topic") or {}
        sf = (topic.get("subfield") or {}) if isinstance(topic, dict) else {}
        sid = str(sf.get("id", "")).rsplit("/", 1)[-1] if sf.get("id") else None
        if not sid:
            self.stats["drop_no_subfield"] += 1
            return None, "no_subfield"
        if sid not in self.claimed:
            self.stats["drop_subfield_unclaimed"] += 1
            return None, "subfield_unclaimed"
        expected = self.subfield_to_field.get(sid)
        if expected != fetched_under:
            # The fetch filter said one thing, primary_topic says another. Drop rather
            # than guess: this is exactly the case that breaks home-field exclusion.
            self.stats["drop_primary_subfield_conflict"] += 1
            return None, f"primary_subfield_conflict({sid}->{expected}!={fetched_under})"
        return fetched_under, "ok"

    def is_excluded_outcome(self, work):
        t = norm_title(work.get("display_name"))
        if t in self.excluded_titles:
            return True, "title"
        year = work.get("publication_year")
        auths = [((a or {}).get("author") or {}).get("display_name", "")
                 for a in (work.get("authorships") or [])]
        for a, years in self.excluded_authors.items():
            if year in years and any(a.lower() in x.lower() for x in auths):
                return True, f"author_year:{a}"
        return False, None

    def accept(self, work, target_field, is_seed=False, abstract_override=None):
        """Return (record, None) or (None, reason)."""
        if work.get("type") != self.want_type:
            self.stats["drop_type"] += 1
            return None, "type"
        if self.want_lang:
            # OpenAlex's `language` field is null for a large share of works, including
            # English ones. Re-checking it locally as a hard filter drops most of the
            # corpus. The server-side `filter=language:en` already did the work; here we
            # only reject a language that is present and is not English.
            lang = work.get("language")
            if lang and str(lang).lower() not in ("en", "english"):
                self.stats["drop_language"] += 1
                return None, "language"
        if self.no_retracted and work.get("is_retracted"):
            self.stats["drop_retracted"] += 1
            return None, "retracted"

        excluded, why = self.is_excluded_outcome(work)
        if excluded:
            self.stats["EXCLUDED_OUTCOME"] += 1
            return None, f"excluded_outcome({why})"

        abstract = abstract_override or rebuild_abstract(work.get("abstract_inverted_index"))
        if self.want_abstract and not abstract:
            self.stats["drop_no_abstract"] += 1
            return None, "no_abstract"
        if not abstract:
            return None, "no_abstract"
        truncated = False
        if len(abstract) > self.len_max:
            abstract = abstract[: self.len_max]
            truncated = True
        if len(abstract) < self.len_min and not is_seed:
            self.stats["drop_short_abstract"] += 1
            return None, "abstract_too_short"

        if is_seed:
            # corpus.yaml: tagging.seeds = assigned_by_hand. The seed's field is the one
            # pre-registered in validation_cases.yaml, not a re-derivation from OpenAlex,
            # which would disagree for interdisciplinary papers.
            field = target_field
            self.stats["seed_hand_assigned"] += 1
        else:
            field, why = self.tag_field(work, target_field)
            if field is None:
                return None, why

        venue = ((work.get("primary_location") or {}).get("source") or {})
        authors = [((a or {}).get("author") or {}).get("display_name")
                   for a in (work.get("authorships") or [])]
        rec = {
            "paper_id": str(work.get("id", "")).rsplit("/", 1)[-1],
            "title": work.get("display_name"),
            "abstract": abstract,
            "year": work.get("publication_year"),
            "field": field,
            "source": "openalex",
            "doi": work.get("doi"),
            "venue": venue.get("display_name"),
            "cited_by": work.get("cited_by_count", 0),
            "first_author": next((a for a in authors if a), None),
            "abstract_truncated": truncated,
            "is_seed": bool(is_seed),
        }
        return rec, None


# --------------------------------------------------------------------------- fetching

def fetch_seeds(cases, flt, api_key):
    """Seed papers by exact title, with the corpus.yaml fallback chain for abstracts.

    Seeds bypass the short-abstract rule: they are hand-picked and the Hour 2 gate already
    decided they matter. Their field is the pre-registered one, not a re-derivation.
    """
    out = []
    for case in cases["cases"]:
        for s in case.get("acceptable_sources") or []:
            if s.get("status") != "verified":
                continue
            d = api_get({"filter": f'title.search:"{s["title"]}"', "per-page": 5,
                         "select": SELECT}, api_key)
            cands = d.get("results", [])
            pick = None
            for c in cands:
                if c.get("publication_year") and abs(int(c["publication_year"]) - int(s["year"])) <= 1:
                    pick = c
                    break
            pick = pick or (cands[0] if cands else None)
            if not pick:
                print(f"    ! seed not found: {s['title'][:60]}", file=sys.stderr)
                continue
            # OpenAlex has no abstract for some pre-2005 seeds; the fallback chain
            # (corpus.yaml source.fallbacks) is how those were marked verified.
            override = None
            src = "openalex"
            if not rebuild_abstract(pick.get("abstract_inverted_index")):
                override, src = epmc_abstract(s["title"])
                if not override:
                    print(f"    ! seed has no abstract anywhere: {s['title'][:52]}", file=sys.stderr)
                    continue
                time.sleep(0.2)
            rec, why = flt.accept(pick, target_field=s["field"], is_seed=True,
                                  abstract_override=override)
            if rec is None:
                print(f"    ! seed rejected ({why}): {s['title'][:52]}", file=sys.stderr)
                continue
            rec["seed_for_case"] = case["id"]
            rec["seed_status"] = s["status"]
            rec["abstract_source"] = src
            out.append(rec)
    return out


def fetch_classics(field, lock_ids, flt, api_key, want, src_filter):
    # OR inside one filter is `|`. A comma means AND and is rejected by the API edge.
    d = api_get({"filter": f"primary_topic.subfield.id:{or_filter(lock_ids)},{src_filter}",
                 "per-page": 200, "sort": "cited_by_count:desc",
                 "select": SELECT}, api_key)
    out = []
    for w in d.get("results", []):
        rec, _ = safe_accept(flt, w, target_field=field)
        if rec:
            rec["selection"] = "distractor_classics"
            out.append(rec)
        if len(out) >= want:
            break
    return out


def fetch_strata(field, lock_ids, flt, api_key, want, seed, corpus, src_filter):
    """Year-stratified reproducible sample, filling the remainder after seeds + classics."""
    out = []
    strata = corpus["source"]["year_strata"]
    total_w = sum(float(s["weight"]) for s in strata)
    ors = or_filter(lock_ids)
    for s in strata:
        n = int(round(want * float(s["weight"]) / total_w))
        if n <= 0:
            continue
        lo, hi = s["years"].split("-")
        got, attempt = 0, 0
        # Measured acceptance is ~75% (the 400-char minimum rejects many abstracts), so
        # over-request and keep re-drawing with a fresh seed rather than under-filling a
        # stratum. A short stratum silently biases the corpus toward recent papers.
        while got < n and attempt < 8:
            d = api_get({"filter": (f"primary_topic.subfield.id:{ors},"
                                    f"from_publication_date:{lo}-01-01,"
                                    f"to_publication_date:{hi}-12-31,"
                                    f"{src_filter}"),
                         "sample": max(n * 3, 50), "seed": seed + attempt,
                         "select": SELECT}, api_key)
            attempt += 1
            for w in d.get("results", []):
                rec, _ = safe_accept(flt, w, target_field=field)
                if rec:
                    rec["selection"] = "stratified_random_sample"
                    rec["year_stratum"] = s["years"]
                    out.append(rec)
                    got += 1
                if got >= n:
                    break
            if not d.get("results"):
                time.sleep(1.0)
    return out


# --------------------------------------------------------------------------- main

def load_yaml(p):
    with open(p) as f:
        return yaml.safe_load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="600 papers instead of 3,000")
    ap.add_argument("--report-only", action="store_true", help="verify the existing corpus")
    ap.add_argument("--per-field", type=int, default=0, help="override papers per field")
    ap.add_argument("--fields", default="", help="comma-separated field ids to restrict to")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args()

    api_key = os.environ.get("OPENALEX_API_KEY", "")
    if not api_key:
        print("ERROR: OPENALEX_API_KEY not set.  set -a; source .env; set +a", file=sys.stderr)
        return 2

    corpus = load_yaml(CORPUS_YAML)
    cases = load_yaml(CASES_YAML)
    flt = Filter(corpus, cases)
    size = corpus["size"]
    per_field = args.per_field or (size["pilot_total"] // len(corpus["fields"])
                                   if args.pilot else size["per_field"])
    only = set(x for x in args.fields.split(",") if x)

    if args.report_only:
        return report(per_field)

    os.makedirs(OUT_DIR, exist_ok=True)
    seen_ids, seen_dois, existing = set(), set(), 0
    if not args.no_resume and os.path.exists(OUT_JSONL):
        with open(OUT_JSONL) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                seen_ids.add(r["paper_id"])
                if r.get("doi"):
                    seen_dois.add(r["doi"])
                existing += 1
        print(f"resuming: {existing} papers already written\n")

    print(f"Target {per_field} papers per field x {len(corpus['fields'])} fields "
          f"= {per_field * len(corpus['fields'])}\n")

    seeds = fetch_seeds(cases, flt, api_key)
    print(f"seeds: {len(seeds)} verified and retrievable "
          f"(excluded {sum(1 for c in cases['cases'] for s in (c.get('acceptable_sources') or []) if s.get('status') != 'verified')} "
          f"awaiting manual_paste)\n")
    by_field = defaultdict(list)
    for s in seeds:
        by_field[s["field"]].append(s)

    src_filter = source_filter(corpus)
    lock = load_yaml(LOCK_YAML)
    subfield_ids = defaultdict(list)
    for r in lock["resolved"]:
        subfield_ids[r["field"]].append(str(r["openalex_subfield_id"]))

    fh = open(OUT_JSONL, "a")
    wrote = {f["id"]: len(by_field[f["id"]]) for f in corpus["fields"]}

    def write(rec):
        if rec["paper_id"] in seen_ids:
            flt.stats["skip_duplicate_id"] += 1
            return False
        if rec.get("doi") and rec["doi"] in seen_dois:
            flt.stats["skip_duplicate_doi"] += 1
            return False
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        seen_ids.add(rec["paper_id"])
        if rec.get("doi"):
            seen_dois.add(rec["doi"])
        return True

    for rec in seeds:
        write(rec)

    for field in corpus["fields"]:
        fid = field["id"]
        if only and fid not in only:
            continue
        ids = [str(i) for i in subfield_ids[fid]]
        have = wrote[fid]
        need = max(0, per_field - have)

        classics_want = min(size["distractor_classics_per_field"], need)
        classics = fetch_classics(fid, ids, flt, api_key, classics_want, src_filter) if classics_want else []
        for rec in classics:
            rec["field"] = fid
            if write(rec):
                wrote[fid] += 1
        need = max(0, per_field - wrote[fid])

        sample = fetch_strata(fid, ids, flt, api_key, need, int(size["random_seed"]), corpus,
                              src_filter) if need else []
        for rec in sample:
            rec["field"] = fid
            if write(rec):
                wrote[fid] += 1

        print(f"  {fid:28s} {wrote[fid]:>4}/{per_field}  "
              f"(seeds {len(by_field[fid])}, "
              f"selection fills {wrote[fid]-len(by_field[fid])})")
    fh.close()

    total = existing + sum(wrote.values())
    manifest = {
        "generated_from": {"corpus": CORPUS_YAML, "lock": LOCK_YAML, "cases": CASES_YAML},
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "random_seed": size["random_seed"],
        "per_field_target": per_field,
        "pilot": bool(args.pilot),
        "counts": {"total_written_this_run": sum(wrote.values()),
                   "total_in_file": total,
                   "per_field": dict(wrote)},
        "filter_stats": dict(flt.stats),
        "excluded_outcome_titles": sorted(flt.excluded_titles),
        "drop_reasons_note": "EXCLUDED_OUTCOME counts papers removed because they are the "
                             "breakthrough papers the validation is built on.",
    }
    with open(OUT_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nwrote {OUT_JSONL}  ({total} papers total)")
    print(f"manifest -> {OUT_MANIFEST}")
    print("\ndrops:")
    for k, v in sorted(flt.stats.items(), key=lambda kv: -kv[1]):
        print(f"  {k:32s} {v}")
    return report(per_field)


def report(per_field):
    """Verify the written corpus against every rule that matters."""
    if not os.path.exists(OUT_JSONL):
        print(f"no corpus at {OUT_JSONL}")
        return 1
    corpus = load_yaml(CORPUS_YAML)
    cases = load_yaml(CASES_YAML)
    flt = Filter(corpus, cases)

    rows, bad = [], Counter()
    with open(OUT_JSONL) as f:
        for line in f:
            rows.append(json.loads(line))

    ids = Counter(r["paper_id"] for r in rows)
    dois = Counter(r["doi"] for r in rows if r.get("doi"))
    for r in rows:
        t = norm_title(r["title"])
        if t in flt.excluded_titles:
            bad["outcome_paper_present"] += 1
        if r.get("type") and r["type"] != "article":
            bad["wrong_type"] += 1
        if r["field"] not in {f["id"] for f in corpus["fields"]}:
            bad["unknown_field"] += 1
        if not r.get("abstract"):
            bad["empty_abstract"] += 1

    per_f = Counter(r["field"] for r in rows)
    seeds = [r for r in rows if r.get("is_seed")]

    print("\n" + "=" * 74)
    print("CORPUS VERIFICATION")
    print("=" * 74)
    print(f"total papers            : {len(rows)}")
    print(f"unique paper_id         : {len(ids)}  "
          f"{'OK' if max(ids.values(), default=1) == 1 else 'DUPLICATES'}")
    print(f"unique DOIs             : {len(dois)}  "
          f"{'OK' if max(dois.values(), default=1) == 1 else 'DUPLICATES'}")
    print(f"seeds present           : {len(seeds)}")
    print(f"outcome papers present  : {bad['outcome_paper_present']}  "
          f"{'OK - the validation cannot self-answer' if bad['outcome_paper_present'] == 0 else 'FAIL'}")
    print(f"non-article type        : {bad['wrong_type']}")
    print(f"unknown field tags      : {bad['unknown_field']}")
    print(f"empty abstracts         : {bad['empty_abstract']}")
    print(f"abstract chars          : min {min((len(r['abstract']) for r in rows), default=0)}, "
          f"max {max((len(r['abstract']) for r in rows), default=0)}")
    print("\nper field:")
    for f in corpus["fields"]:
        n = per_f.get(f["id"], 0)
        flag = "OK" if n >= per_field else f"short of {per_field}"
        print(f"  {f['id']:28s} {n:>5}  {flag}")
    sel = Counter(r.get("selection", "seed") for r in rows)
    print("\nby selection:")
    for k, v in sel.items():
        print(f"  {k:28s} {v:>5}")
    yc = Counter((r.get("year") or 0) // 20 * 20 for r in rows)
    print("\nby year:")
    for k in sorted(yc):
        print(f"  {k}-{k+19:<6d} {yc[k]:>5}")
    ok = (bad["outcome_paper_present"] == 0 and bad["wrong_type"] == 0
          and bad["unknown_field"] == 0 and bad["empty_abstract"] == 0
          and max(ids.values(), default=1) == 1)
    print("\n" + ("VERIFICATION PASSED" if ok else "VERIFICATION FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())