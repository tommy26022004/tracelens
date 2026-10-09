"""Qdrant vector store wrapper.

Owns the collection lifecycle and upsert/search semantics for ingestion.
Agent retrieval (Phase 3) will go through the same `semantic_search` so
that citations always flow back through the metadata stored here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import settings
from app.core.embeddings import EmbeddingsProvider, get_embeddings
from app.ingestion.chunker import Chunk

COLLECTION_NAME = "loan_documents"


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    kind: str
    text: str
    page: int | None
    score: float
    source_metadata: dict[str, Any]


class VectorStore:
    def __init__(
        self,
        client: QdrantClient | None = None,
        embeddings: EmbeddingsProvider | None = None,
    ) -> None:
        self._client = client or QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        self._embeddings = embeddings or get_embeddings()

    @property
    def embedding_space(self) -> str:
        return getattr(
            self._embeddings,
            "space_id",
            f"{type(self._embeddings).__name__}:{self._embeddings.dimension}",
        )

    def ensure_collection(self) -> None:
        """Create the collection if it doesn't already exist."""
        if self._client.collection_exists(COLLECTION_NAME):
            return
        self._client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=qmodels.VectorParams(
                size=self._embeddings.dimension,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def upsert_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        self.ensure_collection()
        vectors = self._embeddings.embed_documents([c.text for c in chunks])
        points = [
            qmodels.PointStruct(
                id=_stable_point_id(chunk.chunk_id),
                vector=vector,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "kind": chunk.kind,
                    "text": chunk.text,
                    "page": chunk.page,
                    "source_metadata": chunk.source_metadata,
                    "embedding_space": self.embedding_space,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
        return len(points)

    def semantic_search(
        self,
        query: str,
        *,
        limit: int = 5,
        document_id: str | None = None,
        kind: str | None = None,
        application_id: str | None = None,
        document_kinds: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[RetrievalHit]:
        self.ensure_collection()
        vector = self._embeddings.embed_query(query)

        must: list[qmodels.FieldCondition] = [
            qmodels.FieldCondition(
                key="embedding_space", match=qmodels.MatchValue(value=self.embedding_space)
            )
        ]
        if application_id is not None:
            if not application_id.strip():
                raise ValueError("application_id cannot be empty")
            must.append(
                qmodels.FieldCondition(
                    key="source_metadata.application_id",
                    match=qmodels.MatchValue(value=application_id),
                )
            )
        if document_kinds is not None:
            if not document_kinds:
                return []
            must.append(
                qmodels.FieldCondition(
                    key="source_metadata.document_kind", match=qmodels.MatchAny(any=document_kinds)
                )
            )
        if document_id is not None:
            must.append(
                qmodels.FieldCondition(
                    key="document_id", match=qmodels.MatchValue(value=document_id)
                )
            )
        if kind is not None:
            must.append(qmodels.FieldCondition(key="kind", match=qmodels.MatchValue(value=kind)))
        query_filter = qmodels.Filter(must=must) if must else None

        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            score_threshold=score_threshold,
        ).points

        return [
            RetrievalHit(
                chunk_id=p.payload["chunk_id"],
                document_id=p.payload["document_id"],
                kind=p.payload["kind"],
                text=p.payload["text"],
                page=p.payload["page"],
                score=p.score,
                source_metadata=p.payload.get("source_metadata", {}),
            )
            for p in results
        ]

    def get_chunk(self, chunk_id: str, *, application_id: str | None = None) -> RetrievalHit | None:
        """Retrieve one citation chunk by its exact stable Qdrant point id."""
        self.ensure_collection()
        points = self._client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[_stable_point_id(chunk_id)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        payload = points[0].payload or {}
        if payload.get("chunk_id") != chunk_id:
            return None
        if application_id is not None and (
            not application_id.strip()
            or payload.get("source_metadata", {}).get("application_id") != application_id
        ):
            return None
        return RetrievalHit(
            chunk_id=payload["chunk_id"],
            document_id=payload["document_id"],
            kind=payload["kind"],
            text=payload["text"],
            page=payload["page"],
            score=1.0,
            source_metadata=payload.get("source_metadata", {}),
        )

    def delete_document(self, document_id: str) -> None:
        self._client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id",
                            match=qmodels.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )


def _stable_point_id(chunk_id: str) -> int:
    """Qdrant point ids must be int or UUID; hash the chunk_id to int64."""
    digest = hashlib.sha1(chunk_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False) & 0x7FFFFFFFFFFFFFFF
