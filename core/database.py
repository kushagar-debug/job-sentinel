"""SQLite Deduplication Database for Cloud Job Sentinel.

Maintains an indexed audit trail of previously parsed and alerted jobs
using SHA-256 fingerprints to ensure zero duplicate notifications.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.models import JobListing

logger = logging.getLogger("sentinel.database")


class JobDatabase:
    """Manages SQLite persistence and hash indexing for job deduplication."""

    def __init__(self, db_path: str = "data/sentinel.db"):
        self.db_path = db_path
        self._ensure_directory()
        self._init_schema()

    def _ensure_directory(self) -> None:
        """Creates parent directory if it does not exist."""
        dirname = os.path.dirname(self.db_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a configured SQLite database connection with row factory."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initializes tables and indexes for deduplication and telemetry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    hash_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    matched_keywords TEXT NOT NULL DEFAULT '[]',
                    detected_at TIMESTAMP NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0,
                    notified_at TIMESTAMP
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_notified ON jobs(notified);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_detected_at ON jobs(detected_at DESC);
                """
            )
            conn.commit()

    def has_seen(self, hash_id: str) -> bool:
        """Checks if a job hash has already been recorded."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM jobs WHERE hash_id = ? LIMIT 1;", (hash_id,))
            return cursor.fetchone() is not None

    def record_job(
        self,
        job: JobListing,
        score: int = 0,
        matched_keywords: Optional[List[str]] = None,
    ) -> bool:
        """Records a new job listing. Returns True if inserted, False if duplicate."""
        if self.has_seen(job.hash_id):
            return False

        keywords_json = json.dumps(matched_keywords or [])
        detected_iso = job.detected_at.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    hash_id, job_id, title, company, location, url,
                    score, matched_keywords, detected_at, notified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0);
                """,
                (
                    job.hash_id,
                    job.job_id,
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    score,
                    keywords_json,
                    detected_iso,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def mark_notified(self, hash_id: str) -> None:
        """Marks a job record as notified with an audit timestamp."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE jobs 
                SET notified = 1, notified_at = ?
                WHERE hash_id = ?;
                """,
                (now_iso, hash_id),
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Returns operational metrics from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs;")
            total_seen = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE notified = 1;")
            total_notified = cursor.fetchone()[0]

            cursor.execute("SELECT AVG(score) FROM jobs WHERE score > 0;")
            avg_score_row = cursor.fetchone()[0]
            avg_score = round(avg_score_row, 1) if avg_score_row else 0.0

            return {
                "total_jobs_seen": total_seen,
                "total_notified": total_notified,
                "average_score": avg_score,
            }

    def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves recent jobs for telemetry and verification."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT hash_id, job_id, title, company, location, score, notified, detected_at
                FROM jobs
                ORDER BY detected_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
