"""Service orchestration layer for the agent workflow."""

from __future__ import annotations

import json
import time
from typing import Any

from app.core.llm_gateway import LLMGateway
from app.services.retrieval import RetrievalService


class OrchestrationService:
    """Concrete implementation of the cross-domain review / rewrite / translation loop."""

    def __init__(self) -> None:
        self.gateway = LLMGateway()
        self.retrieval = RetrievalService()

    def _trace(
        self,
        step: str,
        message: str,
        *,
        task: str | None = None,
        cached: bool = False,
        attempt: int = 1,
        ms: int | None = None,
        corpus: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "type": "trace",
            "step": step,
            "message": message,
            "ts": int(time.time()),
        }
        meta: dict[str, Any] = {"task": task or step, "cached": cached, "attempt": attempt}
        if ms is not None:
            meta["ms"] = ms
        if corpus is not None:
            meta["corpus"] = corpus
        event["meta"] = meta
        return event

    @staticmethod
    def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for candidate in candidates:
            item_id = str(candidate.get("id") or candidate.get("title") or candidate.get("source_passage") or "unknown")
            if item_id in seen:
                continue
            seen.add(item_id)
            deduped.append(candidate)
        return deduped

    @staticmethod
    def _leak_check(abstraction: dict[str, Any]) -> list[str]:
        leak_terms = ["jamming", "granular", "grasp", "gripper", "end effector", "robotic gripper"]
        leaks: list[str] = []
        for field in ("functional_problem", "mechanism"):
            value = str(abstraction.get(field, "")).lower()
            for term in leak_terms:
                if term in value:
                    leaks.append(f"{field}: '{term}'")
        return leaks

    @staticmethod
    def _derive_heresy(structural_score: float, scores: list[float]) -> str:
        if not scores:
            return "medium"
        ordered = sorted(scores)
        if not ordered:
            return "medium"
        low_cut = ordered[max(0, len(ordered) // 3 - 1)] if len(ordered) > 1 else ordered[0]
        high_cut = ordered[min(len(ordered) - 1, 2 * len(ordered) // 3)]
        if structural_score <= low_cut:
            return "high"
        if structural_score <= high_cut:
            return "medium"
        return "low"

    async def _rewrite_query(self, text: str, candidate: dict[str, Any], critique: dict[str, Any], loop_index: int) -> list[str]:
        if loop_index >= 2:
            return []
        rewrite = await self.gateway.arun(
            "decomposer",
            {
                "text": text,
                "candidate": candidate.get("title", candidate.get("source_passage", "")),
                "review": json.dumps(critique, sort_keys=True),
            },
            cache_id=f"rewrite:{candidate.get('id', 'unknown')}:{loop_index}",
        )
        queries = rewrite.data.get("queries", []) if isinstance(rewrite.data, dict) else []
        rewritten: list[str] = []
        for entry in queries:
            query = entry.get("query") if isinstance(entry, dict) else None
            if isinstance(query, str) and query.strip():
                rewritten.append(query.strip())
        return rewritten

    async def arun(self, text: str, home_fields: list[str], chaos: float) -> dict[str, Any]:
        trace: list[dict[str, Any]] = [
            self._trace("abstracting", "Stripping domain terms...", task="abstractor"),
        ]

        abstraction = await self.gateway.arun(
            "abstractor",
            {"text": text},
            cache_id=f"abstractor:{text[:80]}",
        )
        leaks = self._leak_check(abstraction.data if isinstance(abstraction.data, dict) else {})
        leak_note = f" Leak check: {', '.join(leaks)}." if leaks else " Leak check: clean."
        trace.append(
            self._trace(
                "abstracting",
                "Abstracting the problem into a cross-domain functional description." + leak_note,
                task="abstractor",
                cached=abstraction.cached,
                attempt=abstraction.attempts,
                ms=abstraction.latency_ms,
            )
        )

        decomposition = await self.gateway.arun(
            "decomposer",
            {"text": text},
            cache_id=f"decomposer:{text[:80]}",
        )
        trace.append(
            self._trace(
                "decomposing",
                "Breaking the problem into structural queries.",
                task="decomposer",
                cached=decomposition.cached,
                attempt=decomposition.attempts,
                ms=decomposition.latency_ms,
            )
        )

        search_queries: list[str] = []
        for item in decomposition.data.get("queries", []) if isinstance(decomposition.data, dict) else []:
            if isinstance(item, dict):
                query = item.get("query")
                if isinstance(query, str) and query.strip():
                    search_queries.append(query.strip())
        if not search_queries:
            search_queries = [text]

        candidate_pool: list[dict[str, Any]] = []
        for query in search_queries:
            candidate_pool.extend(self.retrieval.search(query, abstraction.data, home_fields=home_fields))
        candidate_pool = self._dedupe_candidates(candidate_pool)

        corpus_kind = "index"
        trace.append(
            self._trace(
                "retrieving",
                f"Retrieved {len(candidate_pool)} candidate analogs from the ChromaDB index.",
                task="retrieval",
                cached=False,
                attempt=1,
                corpus=corpus_kind,
            )
        )

        reviewed_candidates: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []

        reviewed_ids: set[str] = set()
        for loop_index in range(3):
            # Only candidates that have not been through the reviewer yet. Without this the
            # same paper is reviewed once per loop and appears several times in the results.
            round_candidates = [
                candidate
                for candidate in self._dedupe_candidates(candidate_pool)
                if str(candidate.get("id", candidate.get("title", ""))) not in reviewed_ids
            ]
            if not round_candidates:
                break
            for candidate in round_candidates:
                reviewed_ids.add(str(candidate.get("id", candidate.get("title", ""))))
                review = await self.gateway.arun(
                    "skeptic",
                    {
                        "text": text,
                        "candidate": candidate.get("title", candidate.get("source_passage", "")),
                    },
                    cache_id=f"skeptic:{candidate.get('id', candidate.get('title', 'unknown'))}:{loop_index}",
                )
                trace.append(
                    self._trace(
                        "reviewing",
                        "Assessing whether the candidate survives skeptical review.",
                        task="skeptic",
                        cached=review.cached,
                        attempt=review.attempts,
                        ms=review.latency_ms,
                    )
                )

                candidate_entry = {**candidate, "review": review.data}
                reviewed_candidates.append(candidate_entry)

                if review.data.get("accepted"):
                    translation = await self.gateway.arun(
                        "translator",
                        {
                            "text": text,
                            "source_concept": candidate.get("title", "source concept"),
                            "candidate": candidate.get("abstract", candidate.get("source_passage", "")),
                        },
                        cache_id=f"translator:{candidate.get('id', candidate.get('title', 'unknown'))}:{loop_index}",
                    )
                    trace.append(
                        self._trace(
                            "translating",
                            "Translating the surviving analogy into the user's home domain.",
                            task="translator",
                            cached=translation.cached,
                            attempt=translation.attempts,
                            ms=translation.latency_ms,
                        )
                    )
                    candidate_entry["translation"] = translation.data
                    payload = translation.data if isinstance(translation.data, dict) else {}
                    # Honesty rule: the source passage must come from the retrieved
                    # paper, never from the model. The translator only supplies the
                    # hypothesis, the mapping and the reviewer note.
                    passage = str(candidate.get("abstract") or candidate.get("source_passage") or "").strip()
                    mapping = payload.get("mapping") or []
                    # Drop rule: no passage or no mapping means the candidate is never shown.
                    if passage and mapping:
                        result = {
                            "id": candidate.get("id", f"candidate_{len(results) + 1}"),
                            "title": candidate.get("title", "Candidate"),
                            "source_field": candidate.get("source_field", "unknown"),
                            "structural_score": float(candidate.get("structural_score", 0.0)),
                            "matched_on": candidate.get("matched_on", "problem"),
                            "heresy": "medium",
                            "hypothesis": payload.get("hypothesis", candidate.get("hypothesis", "")),
                            "source_passage": passage,
                            "mapping": mapping,
                            "reviewer_note": payload.get("reviewer_note", ""),
                        }
                        for optional in ("year", "venue", "doi"):
                            value = candidate.get(optional)
                            if value is not None:
                                result[optional] = value
                        results.append(result)
                    else:
                        dropped.append(
                            {
                                "id": candidate.get("id", "unknown"),
                                "title": candidate.get("title", ""),
                                "reason": "no source passage" if not passage else "no mapping",
                            }
                        )
                        trace.append(
                            self._trace(
                                "reviewing",
                                f"Dropped {candidate.get('title', 'a candidate')}: no grounded passage and mapping.",
                                task="drop_rule",
                                cached=False,
                                attempt=1,
                            )
                        )
                else:
                    rewritten = await self._rewrite_query(text, candidate, review.data, loop_index)
                    if rewritten and loop_index < 2:
                        trace.append(
                            self._trace(
                                "rewriting",
                                "Weak candidate. Reframing the query and re-running retrieval for a stronger analog.",
                                task="decomposer",
                                cached=False,
                                attempt=loop_index + 1,
                            )
                        )
                        for query in rewritten:
                            candidate_pool.extend(self.retrieval.search(query, abstraction.data, home_fields=home_fields))
                        candidate_pool = self._dedupe_candidates(candidate_pool)
                        break

        if results:
            scores = [float(item["structural_score"]) for item in results]
            for item in results:
                item["heresy"] = self._derive_heresy(float(item["structural_score"]), scores)
            results.sort(key=lambda item: item["structural_score"], reverse=True)
            trace.append(
                self._trace(
                    "ranking",
                    f"Ranked {len(results)} grounded results by structural fit. {len(dropped)} dropped for missing provenance.",
                    task="ranking",
                    cached=False,
                    attempt=1,
                )
            )
        else:
            trace.append(
                self._trace(
                    "ranking",
                    "No grounded candidates survived the provenance drop rule.",
                    task="ranking",
                    cached=False,
                    attempt=1,
                )
            )

        trace.append(
            self._trace(
                "done",
                "Completed decomposition, retrieval, review, rewrite, and translation loop.",
                task="abstractor",
                cached=abstraction.cached,
                attempt=abstraction.attempts,
                ms=abstraction.latency_ms,
            )
        )

        return {
            "text": text,
            "home_fields": home_fields,
            "chaos": chaos,
            "status": "completed",
            "abstraction": abstraction.data,
            "decomposition": decomposition.data,
            "candidates": candidate_pool,
            "reviewed_candidates": reviewed_candidates,
            "translations": [
                {
                    "candidate_id": item["id"],
                    "hypothesis": item["hypothesis"],
                    "source_passage": item["source_passage"],
                    "mapping": item["mapping"],
                    "reviewer_note": item["reviewer_note"],
                }
                for item in results
            ],
            "results": results,
            "dropped": dropped,
            "trace": trace,
        }

    def run(self, text: str, home_fields: list[str], chaos: float) -> dict[str, Any]:
        return __import__("asyncio").run(self.arun(text, home_fields, chaos))
