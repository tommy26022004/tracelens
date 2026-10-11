"""Durable analysis-job state backed by Redis and PostgreSQL."""

from __future__ import annotations

import json
import logging
import threading
from typing import Protocol

import psycopg
from redis import Redis

from app.core.config import settings

LOGGER = logging.getLogger(__name__)
TABLE_NAME = "analysis_jobs"


class AnalysisJobStore(Protocol):
    def put(self, job_id: str, payload: str) -> None: ...

    def get(self, job_id: str) -> str | None: ...


class PersistentAnalysisJobStore:
    """Cache job state in Redis and retain a durable PostgreSQL copy."""

    def __init__(self) -> None:
        self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self._table_ready = False
        self._table_lock = threading.Lock()

    @staticmethod
    def _postgres_dsn() -> str:
        return settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    def _ensure_table(self) -> None:
        if self._table_ready:
            return
        with self._table_lock:
            if self._table_ready:
                return
            with psycopg.connect(self._postgres_dsn()) as connection:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                        job_id TEXT PRIMARY KEY,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
            self._table_ready = True

    def put(self, job_id: str, payload: str) -> None:
        saved = False
        try:
            self._redis.setex(
                f"analysis_job:{job_id}",
                settings.analysis_job_ttl_seconds,
                payload,
            )
            saved = True
        except Exception:
            LOGGER.exception("Could not cache analysis job %s in Redis", job_id)
        try:
            self._ensure_table()
            with psycopg.connect(self._postgres_dsn()) as connection:
                connection.execute(
                    f"""
                    INSERT INTO {TABLE_NAME} (job_id, payload, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (job_id) DO UPDATE
                    SET payload = EXCLUDED.payload, updated_at = NOW()
                    """,
                    (job_id, payload),
                )
            saved = True
        except Exception:
            LOGGER.exception("Could not persist analysis job %s in PostgreSQL", job_id)
        if not saved:
            raise RuntimeError("Analysis job storage is unavailable")

    def get(self, job_id: str) -> str | None:
        try:
            cached = self._redis.get(f"analysis_job:{job_id}")
            if cached is not None:
                return cached
        except Exception:
            LOGGER.exception("Could not read analysis job %s from Redis", job_id)
        try:
            self._ensure_table()
            with psycopg.connect(self._postgres_dsn()) as connection:
                row = connection.execute(
                    f"SELECT payload FROM {TABLE_NAME} WHERE job_id = %s",
                    (job_id,),
                ).fetchone()
            if row is None:
                return None
            payload = row[0] if isinstance(row[0], str) else json.dumps(row[0])
            try:
                self._redis.setex(
                    f"analysis_job:{job_id}",
                    settings.analysis_job_ttl_seconds,
                    payload,
                )
            except Exception:
                LOGGER.exception("Could not restore analysis job %s to Redis", job_id)
            return payload
        except Exception:
            LOGGER.exception("Could not read analysis job %s from PostgreSQL", job_id)
            raise RuntimeError("Analysis job storage is unavailable") from None
