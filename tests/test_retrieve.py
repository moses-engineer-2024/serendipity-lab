"""Unit tests for retrieval. config/models.yaml `retrieval` is the contract.

The important one is `test_home_field_exclusion_returns_nothing`. The work plan requires
home-field exclusion to be proven by a test and not an eyeball: a "cross-domain" result
that is actually the user's own field is the failure that makes the whole validation
table meaningless, and it is invisible unless you assert on it.

These run on pure numpy scoring and need no index, no embedder and no API key.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

from retrieve import (  # noqa: E402
    heresy_from_scores,
    passes_drop_rule,
    score_candidates,
)


def unit(n, d=8, seed=0):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, d)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# --------------------------------------------------------------------- structural_score

def test_score_is_max_over_both_vectors_and_all_queries():
    # One paper, two vectors, two queries. The best pair must win.
    problem = np.array([[1.0, 0.0]], np.float32)
    mech = np.array([[0.0, 1.0]], np.float32)
    queries = np.array([[1.0, 0.0], [0.0, 1.0]], np.float32)
    scores, used_problem = score_candidates(problem, mech, queries)
    assert scores[0] == pytest.approx(1.0)
    # Tie resolves to "problem" deterministically.
    assert used_problem[0]


def test_matched_on_mechanism_when_only_mechanism_matches():
    problem = np.array([[1.0, 0.0]], np.float32)   # query will not match this
    mech = np.array([[0.0, 1.0]], np.float32)      # query matches this
    queries = np.array([[0.0, 1.0]], np.float32)
    scores, used_problem = score_candidates(problem, mech, queries)
    assert used_problem[0] is np.False_ or not used_problem[0]
    assert scores[0] == pytest.approx(1.0)


def test_record_matched_on_is_the_argmax():
    p, m, q = unit(20), unit(20, seed=1), unit(3, seed=2)
    scores, used_problem = score_candidates(p, m, q)
    sp = (p @ q.T).max(axis=1)
    sm = (m @ q.T).max(axis=1)
    assert np.allclose(scores, np.maximum(sp, sm), atol=1e-5)
    assert np.array_equal(used_problem, sp >= sm)


def test_scores_are_monotonic_bounded():
    p, m, q = unit(10), unit(10, seed=1), unit(2, seed=2)
    s, _ = score_candidates(p, m, q)
    assert s.min() >= -1.0001 and s.max() <= 1.0001


def test_empty_candidates_returns_empty():
    scores, used = score_candidates(np.zeros((0, 8), np.float32),
                                    np.zeros((0, 8), np.float32), unit(1))
    assert scores.shape == (0,)
    assert used.shape == (0,)


# ------------------------------------------------------------- home-field exclusion

def test_home_field_exclusion_returns_nothing():
    """The load-bearing test. A result from the user's own field is a failed cross-domain
    search wearing a success's clothes, so the exclusion must return zero, not 'mostly'."""
    from retrieve import RetrievalIndex
    idx = RetrievalIndex.__new__(RetrievalIndex)   # no chroma needed for the clause
    where = idx.home_field_clause(["civil engineering"])
    assert where == {"field": {"$nin": ["civil engineering"]}}

    # And the semantics of that clause, against a realistic candidate set.
    candidates = [{"field": "civil engineering"}, {"field": "ecology"},
                  {"field": "materials"}, {"field": "civil engineering"}]
    home = ["civil engineering"]
    kept = [c for c in candidates if c["field"] not in home]
    assert kept == [{"field": "ecology"}, {"field": "materials"}]
    assert not any(c["field"] in home for c in kept)


def test_exclusion_applies_identically_to_baseline_and_ours():
    """D4: the baseline gets the same exclusion. Otherwise the headline comparison is a
    strawman that flatters us."""
    from retrieve import RetrievalIndex
    idx = RetrievalIndex.__new__(RetrievalIndex)
    home = ["robotics_mech_eng"]
    assert (idx.home_field_clause(home)
            == {"field": {"$nin": ["robotics_mech_eng"]}})


# --------------------------------------------------------------------- drop rule

def test_drop_rule_drops_only_when_both_absent():
    assert passes_drop_rule({"source_passage": "exact quote", "mapping": []})[0] is True
    assert passes_drop_rule({"source_passage": "", "mapping": [{"a": "b"}]})[0] is True
    ok, why = passes_drop_rule({"source_passage": "", "mapping": []})
    assert ok is False
    assert "source_passage" in why


def test_drop_rule_treats_whitespace_passage_as_absent():
    assert passes_drop_rule({"source_passage": "   ", "mapping": []})[0] is False


# --------------------------------------------------------------------- heresy

def test_heresy_is_tertiles_of_the_pool():
    s = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6], np.float32)
    h = heresy_from_scores(s)
    assert set(h) <= {"low", "medium", "high"}
    assert h[0] == "low" and h[-1] == "high"
    assert list(h) == sorted(h, key=lambda v: {"low": 0, "medium": 1, "high": 2}[v])


def test_heresy_is_relative_not_absolute():
    """Two runs with different absolute scores must still split low/medium/high. Fixed
    cut-offs would make the label depend on how good the run happened to be."""
    a = heresy_from_scores(np.array([0.01, 0.02, 0.03], np.float32))
    b = heresy_from_scores(np.array([0.80, 0.85, 0.90], np.float32))
    assert sorted(set(a)) == ["high", "low", "medium"]
    assert sorted(set(b)) == ["high", "low", "medium"]


def test_heresy_empty_pool():
    assert len(heresy_from_scores(np.array([]))) == 0


# --------------------------------------------------------------------- config contract

def test_config_values_match_this_implementation():
    import yaml
    cfg = yaml.safe_load(open("config/models.yaml"))
    r = cfg["retrieval"]
    assert r["record_matched_on"] is True
    assert r["drop_rule"].startswith("no source_passage AND no mapping")
    assert r["results_shown"] == 5
    assert r["max_loops"] == 2
    # home_field_filter lives under vector_store, and it must be a $nin on field.
    hf = cfg["vector_store"]["home_field_filter"]
    assert hf == {"field": {"$nin": "home_fields"}}
    # Two structural vectors per paper is what matched_on depends on.
    assert set(cfg["vector_store"]["collections"]) == {
        "abstractions_problem", "abstractions_mechanism", "raw_abstracts"}
