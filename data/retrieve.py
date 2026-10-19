#!/usr/bin/env python3
"""Structural retrieval over the abstraction index.

config/models.yaml `retrieval` is authoritative:
    structural_score: max(cos(q, v_problem), cos(q, v_mechanism)), maximized over all queries
    record_matched_on: true        -> 'problem' | 'mechanism', shown in the inspector
    queries_per_run: [2, 4]        # decomposer output, plus the original abstraction
    k_per_query: 30, candidates_to_review: 12, max_loops: 2, results_shown: 5
    drop_rule: no source_passage AND no mapping => dropped, never shown
    heresy: derived from topical distance, tertiles of the candidate pool
    home_field_filter: { field: { "$nin": "home_fields" } }

HOME-FIELD EXCLUSION IS THE POINT of the whole system, so it is a unit test, not an
eyeball check: `tests/test_retrieve.py::test_home_field_exclusion_returns_nothing` builds a
known set with papers in the user's own field and asserts zero of them come back. A
"cross-domain" result that is actually the user's own field is the failure mode that makes
the whole validation meaningless.

The scoring core (`score_candidates`) is pure numpy and takes no database handle, so it is
testable without an index and without a 50-minute embed run.

Usage:
    python3 -c "from data.retrieve import RetrievalIndex; ..."
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402


def load_yaml(p="config/models.yaml"):
    with open(p) as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------- scoring core

def score_candidates(problem_mat, mech_mat, query_mat):
    """structural_score = max cosine over BOTH vectors and ALL queries.

    Returns (scores, matched_on) as numpy arrays of length n_candidates.

    Embeddings are stored normalised, so cosine is a plain dot product. A paper's problem
    may match the user's problem (same abstract problem) or its mechanism may (a mechanism
    that offers what the user needs); taking the max of both is why D8 records two vectors.
    `matched_on` is what the inspector shows, so it has to be the argmax, not a guess.

    Ties resolve to "problem" so the label is deterministic across runs.
    """
    problem_mat = np.asarray(problem_mat, dtype=np.float32)
    mech_mat = np.asarray(mech_mat, dtype=np.float32)
    query_mat = np.asarray(query_mat, dtype=np.float32)
    if problem_mat.ndim == 1:
        problem_mat = problem_mat.reshape(1, -1)
    if mech_mat.ndim == 1:
        mech_mat = mech_mat.reshape(1, -1)
    if query_mat.ndim == 1:
        query_mat = query_mat.reshape(1, -1)
    if problem_mat.size == 0:
        return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=bool)

    # (candidates, queries) for each vector type
    sp = problem_mat @ query_mat.T          # noqa: E741
    sm = mech_mat @ query_mat.T
    best_p = sp.max(axis=1)
    best_m = sm.max(axis=1)
    use_problem = best_p >= best_m
    scores = np.where(use_problem, best_p, best_m).astype(np.float32)
    return scores, use_problem


def heresy_from_scores(scores):
    """Derived heresy: tertiles of the candidate pool. No extra model, no extra call.

    Tertiles rather than fixed cut-offs because the pool size varies per run, and absolute
    thresholds would make the label depend on how many candidates happened to survive.
    """
    scores = np.asarray(scores, dtype=np.float32)
    if scores.size == 0:
        return np.array([], dtype=object)
    hi = np.quantile(scores, 2 / 3)
    mid = np.quantile(scores, 1 / 3)
    return np.where(scores >= hi, "high", np.where(scores >= mid, "medium", "low"))


def passes_drop_rule(candidate):
    """drop_rule: no source_passage AND no mapping => dropped, never shown.

    Returns (keep, reason). `both absent` is the drop condition; having either one is
    enough to keep. This is the anti-hallucination rule and it is deliberately strict.
    """
    has_passage = bool((candidate.get("source_passage") or "").strip())
    has_mapping = bool(candidate.get("mapping"))
    if not has_passage and not has_mapping:
        return False, "no source_passage AND no mapping"
    return True, ""


# --------------------------------------------------------------------------- index

class RetrievalIndex:
    def __init__(self, chroma_path="data/chroma", cfg=None):
        import chromadb
        from chromadb.config import Settings
        self.cfg = cfg or load_yaml()
        r = self.cfg["retrieval"]
        self.k_per_query = int(r["k_per_query"])
        self.results_shown = int(r["results_shown"])
        self.client = chromadb.PersistentClient(path=chroma_path,
                                                settings=Settings(anonymized_telemetry=False))

    def _col(self, name):
        try:
            return self.client.get_collection(name)
        except Exception:
            return None

    def available(self):
        out = {}
        for n in ("abstractions_problem", "abstractions_mechanism", "raw_abstracts"):
            c = self._col(n)
            out[n] = c.count() if c is not None else 0
        return out

    def home_field_clause(self, home_fields):
        """The locked exclusion clause: field NOT IN home_fields.

        Applies identically to ours and to the baseline. A baseline without this filter
        drowns in home-field papers and the headline comparison becomes a strawman.
        """
        return {"field": {"$nin": list(home_fields)}}

    def query_ours(self, query_vecs, home_fields, k=None):
        """Retrieval over the two abstraction collections. Home field excluded."""
        pc = self._col("abstractions_problem")
        mc = self._col("abstractions_mechanism")
        if pc is None or mc is None:
            raise SystemExit(
                "abstractions_* collections are empty. Run data/abstract_corpus.py then\n"
                "  python3 data/build_index.py\n")
        k = k or self.k_per_query
        where = self.home_field_clause(home_fields)
        q = [np.asarray(v, dtype=np.float32).tolist() for v in query_vecs]
        n = pc.count()
        got_p = pc.query(query_embeddings=q, n_results=min(k, n), where=where,
                         include=["embeddings", "metadatas"])
        # Mechanisms may not exist for every paper, so query that side on its own key set.
        m_where = dict(where)
        got_m = mc.query(query_embeddings=q, n_results=min(k, mc.count() or 1),
                         where=m_where, include=["embeddings", "metadatas"])
        return self._merge(got_p, got_m)

    def _merge(self, got_p, got_m):
        """Union the two candidate lists by paper_id, keeping both vectors where available."""
        p_vec, p_meta, m_vec, m_meta = {}, {}, {}, {}
        for ids, embs, metas in ((got_p["ids"][0], got_p["embeddings"][0], got_p["metadatas"][0]),
                                 (got_m["ids"][0], got_m["embeddings"][0], got_m["metadatas"][0])):
            store_v, store_m = (p_vec, p_meta) if ids is got_p["ids"][0] else (m_vec, m_meta)
            for i, pid in enumerate(ids):
                store_v[pid] = np.asarray(embs[i], dtype=np.float32)
                store_m[pid] = metas[i]
        order, pv, mv, meta = [], [], [], {}
        for pid in list(p_vec) + [k for k in m_vec if k not in p_vec]:
            order.append(pid)
            pv.append(p_vec.get(pid, np.zeros(0, dtype=np.float32)))
            mv.append(m_vec.get(pid, np.zeros(0, dtype=np.float32)))
            meta[pid] = (p_meta.get(pid) or m_meta.get(pid))
        dim = next((v.shape[0] for v in list(p_vec.values()) + list(m_vec.values())
                    if v.size), 768)
        P = np.stack([v if v.size else np.zeros(dim, np.float32) for v in pv]) if pv else np.zeros((0, dim), np.float32)
        M = np.stack([v if v.size else np.zeros(dim, np.float32) for v in mv]) if mv else np.zeros((0, dim), np.float32)
        return {"order": order, "problem": P, "mechanism": M, "meta": meta}

    def rank(self, merged, query_vecs, top_n=None):
        scores, use_problem = score_candidates(merged["problem"], merged["mechanism"],
                                               np.stack(query_vecs))
        n = top_n or self.results_shown
        keep = np.argsort(-scores)[:n]
        out = []
        for i in keep:
            m = merged["meta"][merged["order"][i]] or {}
            out.append({
                "paper_id": merged["order"][i],
                "title": m.get("title"),
                "year": m.get("year"),
                "field": m.get("field"),
                "doi": m.get("doi"),
                "structural_score": round(float(scores[i]), 4),
                "matched_on": "problem" if use_problem[i] else "mechanism",
            })
        if out:
            h = heresy_from_scores(scores[keep])
            for r, hv in zip(out, h):
                r["heresy"] = str(hv)
        return out

    def query_baseline(self, raw_query_vec, home_fields, k=None):
        """The baseline: same corpus, same exclusion, raw text. Never re-tuned."""
        rc = self._col("raw_abstracts")
        if rc is None or rc.count() == 0:
            raise SystemExit("raw_abstracts is empty. Run data/ingest_corpus.py then "
                             "data/build_index.py --collections raw_abstracts")
        k = k or self.k_per_query
        where = self.home_field_clause(home_fields)
        got = rc.query(query_embeddings=[np.asarray(raw_query_vec, np.float32).tolist()],
                       n_results=min(k, rc.count()), where=where,
                       include=["metadatas", "distances"])
        out = []
        for i, pid in enumerate(got["ids"][0]):
            m = got["metadatas"][0][i] or {}
            # chroma cosine distance -> similarity
            out.append({"paper_id": pid, "title": m.get("title"), "year": m.get("year"),
                        "field": m.get("field"), "doi": m.get("doi"),
                        "structural_score": round(1.0 - float(got["distances"][0][i]), 4),
                        "matched_on": None})
        return out


if __name__ == "__main__":
    idx = RetrievalIndex()
    av = idx.available()
    print("collections:", json.dumps(av, indent=2))
    if not av["abstractions_problem"]:
        print("\nNothing to retrieve yet: the abstraction batch job has not run.")
        sys.exit(1)
    print("\nindex ready for retrieval")
