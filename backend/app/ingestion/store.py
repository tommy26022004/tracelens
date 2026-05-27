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
    page: int
    score: float
    source_metadata: dict[str, Any]


class VectorStore:
    def __init__(
        self,
        client: QdrantClient | None = None,
        embeddings: EmbeddingsProvider | None = None,
    ) -> None:
        self._client = client or QdrantClient(url=settings.qdrant_url)
        self._embeddings = embeddings or get_embeddings()

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
    ) -> list[RetrievalHit]:
        self.ensure_collection()
        vector = self._embeddings.embed_query(query)

        must: list[qmodels.FieldCondition] = []
        if document_id is not None:
            must.append(
                qmodels.FieldCondition(
                    key="document_id", match=qmodels.MatchValue(value=document_id)
                )
            )
        if kind is not None:
            must.append(
                qmodels.FieldCondition(key="kind", match=qmodels.MatchValue(value=kind))
            )
        query_filter = qmodels.Filter(must=must) if must else None

        results = self._client.query_points(
            collection_name=COLLECTION_NAME,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
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
