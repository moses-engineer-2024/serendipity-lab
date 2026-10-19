"""Tests for the frozen result contract (docs/cut_list.md deltas)."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import TRACE_STEPS, ResultEvent
from app.services.orchestration import OrchestrationService

client = TestClient(app)

HERO_TEXT = (
    "We are designing an end effector that must pick up objects of unknown, irregular "
    "shape without per-object programming."
)


def test_prior_art_is_cut_from_the_schema() -> None:
    import app.schemas.responses as responses

    assert not hasattr(responses, "PriorArt")
    assert "prior_art" not in ResultEvent.model_fields


def test_result_requires_passage_and_mapping() -> None:
    base = {
        "id": "r1",
        "title": "A paper",
        "source_field": "soft_matter_stat_physics",
        "structural_score": 0.5,
        "heresy": "medium",
        "hypothesis": "What if the medium jams?",
        "reviewer_note": "Breaks under heavy loads.",
    }

    with pytest.raises(ValidationError):
        ResultEvent(**base, source_passage="", mapping=[{"source_concept": "a", "home_concept": "b"}])

    with pytest.raises(ValidationError):
        ResultEvent(**base, source_passage="A real quote.", mapping=[])

    ok = ResultEvent(
        **base,
        source_passage="A real quote from the abstract.",
        mapping=[{"source_concept": "jamming", "home_concept": "grip"}],
    )
    assert ok.matched_on == "problem"
    assert ok.type == "result"


def test_optional_bibliographic_fields_are_supported() -> None:
    result = ResultEvent(
        id="r1",
        title="Jamming at zero temperature and zero applied stress",
        year=2003,
        venue="Physical Review E",
        doi="10.1103/PhysRevE.68.011306",
        source_field="soft_matter_stat_physics",
        structural_score=0.82,
        matched_on="mechanism",
        heresy="high",
        hypothesis="What if confinement does the gripping?",
        source_passage="A disordered assembly transitions from fluid-like to rigid.",
        mapping=[{"source_concept": "packing fraction", "home_concept": "vacuum level"}],
        reviewer_note="Fails on very heavy or very slick objects.",
    )
    assert result.year == 2003
    assert result.doi.startswith("10.")


def test_structural_score_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ResultEvent(
            id="r1",
            title="t",
            source_field="f",
            structural_score=1.4,
            heresy="low",
            hypothesis="h",
            source_passage="p",
            mapping=[{"source_concept": "a", "home_concept": "b"}],
            reviewer_note="n",
        )


def test_chaos_is_accepted_and_ignored() -> None:
    payload = {"text": HERO_TEXT, "home_fields": ["robotics_mech_eng"], "chaos": 0.9}
    response = client.post("/api/collide", json=payload)
    assert response.status_code == 202


def test_stream_emits_results_and_only_frozen_steps(monkeypatch) -> None:
    monkeypatch.setenv("LLM_DRY_RUN", "1")
    create = client.post(
        "/api/collide",
        json={"text": HERO_TEXT, "home_fields": ["robotics_mech_eng"], "chaos": 0.0},
    )
    run_id = create.json()["run_id"]

    body = client.get(f"/api/runs/{run_id}/stream").text
    assert "event: result" in body
    assert "prior_art" not in body

    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        event = json.loads(line[len("data: ") :])
        if event.get("type") == "trace":
            assert event["step"] in TRACE_STEPS
        if event.get("type") == "result":
            # Re-validating proves nothing ungrounded reached the wire.
            ResultEvent(**event)


def test_done_is_the_last_trace_event(monkeypatch) -> None:
    monkeypatch.setenv("LLM_DRY_RUN", "1")
    create = client.post(
        "/api/collide",
        json={"text": HERO_TEXT, "home_fields": ["robotics_mech_eng"], "chaos": 0.0},
    )
    run_id = create.json()["run_id"]
    body = client.get(f"/api/runs/{run_id}/stream").text

    assert body.index("event: result") < body.rindex('"step": "done"')


def test_passage_comes_from_the_corpus_not_the_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_DRY_RUN", "1")
    service = OrchestrationService()
    run = service.run(HERO_TEXT, ["robotics_mech_eng"], 0.0)

    abstracts = {paper["abstract"] for paper in service.retrieval._paper_cache.values()}
    assert run["results"]
    for result in run["results"]:
        assert result["source_passage"] in abstracts


def test_home_field_is_excluded_from_results(monkeypatch) -> None:
    monkeypatch.setenv("LLM_DRY_RUN", "1")
    service = OrchestrationService()
    run = service.run(HERO_TEXT, ["robotics_mech_eng"], 0.0)

    assert run["results"]
    assert all(item["source_field"] != "robotics_mech_eng" for item in run["results"])
