#!/usr/bin/env python3
"""Build the ChromaDB index. One command, resumable, rebuilds from scratch.

config/models.yaml vector_store section is authoritative:
    engine: chromadb, path: data/chroma
    collections: abstractions_problem, abstractions_mechanism, raw_abstracts
    metadata_fields: [paper_id, title, year, field, source, doi]
    home_field_filter: { field: { "$nin": "home_fields" } }

`assert_at_load` is enforced here: every collection stores the embedder fingerprint in its
metadata and a rebuild against a different model refuses rather than silently mixing
vector spaces. That matters because the baseline (raw_abstracts) and ours (abstractions_*)
must be comparable, and a mid-project model swap would make the whole validation table
meaningless while still looking plausible.

Two inputs, two states:
    data/corpus/corpus.jsonl        -> raw_abstracts          (available now)
    data/corpus/abstractions.jsonl   -> abstractions_*          (needs the batch job)

Usage:
    set -a; source .env; set +a
    python3 data/build_index.py                 # build what inputs allow
    python3 data/build_index.py --force         # drop and rebuild everything
    python3 data/build_index.py --collections raw_abstracts
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402
from embedder import Embedder  # noqa: E402

CORPUS = "data/corpus/corpus.jsonl"
ABSTRACTIONS = "data/corpus/abstractions.jsonl"
CHROMA_PATH = "data/chroma"


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
                out.append(json.loads(line))
    return out


def meta_of(rec):
    return {"paper_id": rec["paper_id"], "title": rec["title"],
            "year": int(rec["year"]) if rec.get("year") else 0,
            "field": rec["field"], "source": rec.get("source", "openalex"),
            "doi": rec.get("doi") or ""}


def build(embedder, cfg, names, force):
    import chromadb
    from chromadb.config import Settings

    os.makedirs(CHROMA_PATH, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_PATH,
                                       settings=Settings(anonymized_telemetry=False))
    fp = embedder.fingerprint()
    built, skipped = [], []

    # ---- raw_abstracts: the baseline collection -------------------------------
    if "raw_abstracts" in names:
        rows = read_jsonl(CORPUS)
        if not rows:
            print("raw_abstracts: skipped, no corpus.jsonl "
                  "(run data/ingest_corpus.py first)")
            skipped.append("raw_abstracts")
        else:
            col = get_or_create(client, "raw_abstracts", fp, force)
            have = col.count()
            if have >= len(rows) and not force:
                print(f"raw_abstracts: {have} rows already indexed, skipping")
            else:
                if force:
                    client.delete_collection("raw_abstracts")
                    col = get_or_create(client, "raw_abstracts", fp, True)
                texts = [f"{r['title']}\n\n{r['abstract']}" for r in rows]
                t0 = time.time()
                step = 256
                for i in range(0, len(texts), step):
                    chunk = texts[i:i + step]
                    embs = embedder.encode(chunk).tolist()
                    col.upsert(ids=[r["paper_id"] for r in rows[i:i + step]],
                               embeddings=embs,
                               metadatas=[meta_of(r) for r in rows[i:i + step]])
                    if (i // step) % 4 == 0:
                        print(f"    raw_abstracts {i+len(chunk)}/{len(texts)} "
                              f"({time.time()-t0:.0f}s)", flush=True)
                print(f"raw_abstracts: {col.count()} rows in {time.time()-t0:.0f}s")
            built.append("raw_abstracts")

    # ---- abstractions_problem / abstractions_mechanism -------------------------
    abs_rows = read_jsonl(ABSTRACTIONS)
    if "abstractions_problem" in names or "abstractions_mechanism" in names:
        if not abs_rows:
            print("abstractions_*: skipped, no abstractions.jsonl "
                  "(run data/abstract_corpus.py; needs the gateway and the prompts)")
            skipped += ["abstractions_problem", "abstractions_mechanism"]
        else:
            usable = [r for r in abs_rows if r.get("abstraction")]
            # A corpus paper's mechanism is REQUIRED (config/models.yaml + schema), so a
            # missing one means the batch job left it unresolved. It is skipped here and
            # the count is reported, never silently indexed as an empty string.
            for name, part in (("abstractions_problem", ("functional_problem", "constraints")),
                               ("abstractions_mechanism", ("mechanism",))):
                if name not in names:
                    continue
                rows = [r for r in usable
                        if all(str(r["abstraction"].get(k) or "").strip() for k in part)]
                if name == "abstractions_mechanism":
                    rows = [r for r in rows if r["abstraction"].get("mechanism")]
                if not rows:
                    print(f"{name}: skipped, no usable rows")
                    skipped.append(name)
                    continue
                col = get_or_create(client, name, fp, force)
                if col.count() >= len(rows) and not force:
                    print(f"{name}: {col.count()} rows already indexed, skipping")
                    built.append(name)
                    continue
                if force:
                    client.delete_collection(name)
                    col = get_or_create(client, name, fp, True)
                texts = []
                for r in rows:
                    a = r["abstraction"]
                    if name == "abstractions_problem":
                        c = a.get("constraints") or []
                        texts.append(f"{a.get('functional_problem','')}. "
                                     f"Constraints: {'; '.join(str(x) for x in c)}".strip())
                    else:
                        texts.append(str(a.get("mechanism", "")))
                t0 = time.time()
                step = 256
                for i in range(0, len(texts), step):
                    embs = embedder.encode(texts[i:i + step]).tolist()
                    col.upsert(ids=[r["paper_id"] for r in rows[i:i + step]],
                               embeddings=embbs,
                               metadatas=[meta_of(r) for r in rows[i:i + step]])
                print(f"{name}: {col.count()} rows in {time.time()-t0:.0f}s "
                      f"({len(usable)-len(rows)} skipped for missing fields)")
                built.append(name)
    return built, skipped, client, fp


def get_or_create(client, name, fp, force):
    """Create the collection, or refuse if an existing one was built with another model."""
    try:
        col = client.get_collection(name)
        got = dict(col.metadata or {})
        if got and any(got.get(k) != v for k, v in fp.items()):
            raise SystemExit(
                f"assert_at_load: collection {name!r} was built with "
                f"{ {k: got.get(k) for k in fp} } but the current embedder is {fp}.\n"
                f"Refusing to mix vector spaces. Rebuild deliberately:\n"
                f"  python3 data/build_index.py --force --collections {name}")
        return col
    except Exception:
        return client.create_collection(
            name=name, metadata=fp,
            configuration={"hnsw": {"space": "cosine"}})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="drop and rebuild")
    ap.add_argument("--collections", default="raw_abstracts,abstractions_problem,abstractions_mechanism")
    args = ap.parse_args()

    cfg = load_yaml("config/models.yaml")
    names = [n.strip() for n in args.collections.split(",") if n.strip()]
    print("embedding:", cfg["embedding"]["model"], "dim", cfg["embedding"]["dim"])
    e = Embedder(cfg["embedding"])
    print("fingerprint:", e.fingerprint())
    print("path:", CHROMA_PATH, "\n")

    built, skipped, client, fp = build(e, cfg, names, args.force)

    print("\n" + "=" * 68)
    print("INDEX SUMMARY")
    print("=" * 68)
    for n in names:
        try:
            c = client.get_collection(n)
            print(f"  {n:26s} {c.count():>6} rows")
        except Exception:
            state = "not built" if n in skipped else "missing"
            print(f"  {n:26s}     -  ({state})")
    print(f"\n  built  : {', '.join(built) or 'none'}")
    print(f"  skipped: {', '.join(skipped) or 'none'}")
    if skipped:
        print("\n  A retrieval run needs at least one abstraction collection. Until the batch")
        print("  job has run, only the baseline (raw_abstracts) is queryable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())