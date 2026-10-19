from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/serendipity-lab/bge-base-en-v1.5")


class RetrievalService:
    """Real retrieval over the ChromaDB index using the local bge model.

    The corpus was indexed with BAAI/bge-base-en-v1.5 (768-dim, normalized, cosine).
    Queries are embedded with the same model so they live in the same vector space.
    The abstraction collections were never built (batch job not run), so we query
    raw_abstracts: the query is structurally abstracted, the corpus side is raw.
    Home-field exclusion is applied as a metadata filter before ranking.
    """

    def __init__(
        self,
        chroma_path: str | Path | None = None,
        corpus_path: str | Path | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[3]
        self.chroma_path = Path(chroma_path) if chroma_path else (root / "data" / "chroma")
        self.corpus_path = Path(corpus_path) if corpus_path else (root / "data" / "corpus" / "corpus.jsonl")

        self._collection: Any = None
        self._embedder: Any = None
        self._paper_cache: dict[str, dict[str, Any]] = {}
        self._load_corpus_cache()

    def _load_corpus_cache(self) -> None:
        if not self.corpus_path.exists():
            return
        with self.corpus_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                paper = json.loads(line)
                paper_id = str(paper.get("paper_id", ""))
                if paper_id:
                    self._paper_cache[paper_id] = paper

    def _get_embedder(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        model_path = os.environ.get("SERENDIPITY_MODEL_PATH", DEFAULT_MODEL_PATH)
        if not os.path.isdir(model_path):
            return None
        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(model_path, device="cpu")
        except Exception:
            self._embedder = None
        return self._embedder

    def _get_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        try:
            import chromadb
            from chromadb.config import Settings

            client = chromadb.PersistentClient(
                path=str(self.chroma_path),
                settings=Settings(anonymized_telemetry=False),
            )
            collections = client.list_collections()
            if not collections:
                return None
            self._collection = client.get_collection(name=collections[0].name)
        except Exception:
            self._collection = None
        return self._collection

    def search(
        self,
        query: str,
        abstraction: dict[str, Any],
        *,
        home_fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        home_field_set: set[str] = set(home_fields or [])
        collection = self._get_collection()

        if collection is None:
            return self._fallback_search(query, abstraction, home_field_set)

        embedder = self._get_embedder()
        if embedder is None:
            return self._fallback_search(query, abstraction, home_field_set)

        try:
            query_embedding = embedder.encode(query, normalize_embeddings=True).tolist()
        except Exception:
            return self._fallback_search(query, abstraction, home_field_set)

        where_filter: dict[str, Any] | None = None
        if home_field_set:
            where_filter = {"field": {"$nin": list(home_field_set)}}

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(30, collection.count()),
                where=where_filter,
                include=["metadatas", "distances"],
            )
        except Exception:
            return self._fallback_search(query, abstraction, home_field_set)

        ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        matches: list[dict[str, Any]] = []
        for idx, (dist, meta) in enumerate(zip(distances, metadatas)):
            paper_id = str(meta.get("paper_id", ids[idx] if idx < len(ids) else ""))
            source_field = str(meta.get("field", "unknown"))
            if source_field in home_field_set:
                continue

            paper = self._paper_cache.get(paper_id, {})
            abstract = str(paper.get("abstract", meta.get("title", "")))
            similarity = 1.0 - float(dist)

            matches.append(
                {
                    "id": paper_id,
                    "title": str(meta.get("title", paper.get("title", "Unknown"))),
                    "source_field": source_field,
                    "structural_score": round(similarity, 4),
                    "matched_on": "problem",
                    "abstract": abstract,
                    "year": meta.get("year"),
                    "venue": paper.get("venue"),
                    "doi": str(meta.get("doi", paper.get("doi", ""))),
                    "corpus": "index",
                    "hypothesis": abstract,
                    "source_passage": abstract,
                    "mapping": [],
                    "reviewer_note": "",
                }
            )

        matches.sort(key=lambda item: item["structural_score"], reverse=True)
        return matches[:12]

    def _fallback_search(
        self,
        query: str,
        abstraction: dict[str, Any],
        home_field_set: set[str],
    ) -> list[dict[str, Any]]:
        query_tokens = self._tokenize(query)
        mechanism_tokens = self._tokenize(str(abstraction.get("mechanism", "")))

        matches: list[dict[str, Any]] = []
        for paper in self._paper_cache.values():
            source_field = str(paper.get("field", "unknown"))
            if source_field in home_field_set:
                continue

            abstract = str(paper.get("abstract", ""))
            title = str(paper.get("title", ""))
            abstract_tokens = self._tokenize(abstract + " " + title)

            if not query_tokens or not abstract_tokens:
                continue

            overlap = len(query_tokens & abstract_tokens)
            score = overlap / max(len(query_tokens | abstract_tokens), 1)
            if score <= 0:
                continue

            matches.append(
                {
                    "id": str(paper.get("paper_id", "")),
                    "title": title,
                    "source_field": source_field,
                    "structural_score": round(float(score), 4),
                    "matched_on": "problem",
                    "abstract": abstract,
                    "year": paper.get("year"),
                    "venue": paper.get("venue"),
                    "doi": paper.get("doi"),
                    "corpus": "index",
                    "hypothesis": abstract,
                    "source_passage": abstract,
                    "mapping": [],
                    "reviewer_note": "",
                }
            )

        matches.sort(key=lambda item: item["structural_score"], reverse=True)
        return matches[:12]

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {token.lower() for token in value.replace("-", " ").split() if token.strip()}
