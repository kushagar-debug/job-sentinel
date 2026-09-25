"""Unit tests for SQLite database deduplication."""

import pytest
from core.models import JobListing


def test_database_records_and_deduplicates_jobs(temp_db, sample_cloud_intern_job):
    """Verifies that duplicate jobs are detected and skipped via SHA-256 fingerprinting."""
    # First insertion must succeed
    inserted = temp_db.record_job(
        job=sample_cloud_intern_job,
        score=85,
        matched_keywords=["intern", "cloud", "aws"],
    )
    assert inserted is True
    assert temp_db.has_seen(sample_cloud_intern_job.hash_id) is True

    # Duplicate insertion of identical listing must return False
    duplicate_inserted = temp_db.record_job(
        job=sample_cloud_intern_job,
        score=85,
        matched_keywords=["intern", "cloud", "aws"],
    )
    assert duplicate_inserted is False

    # Stats check
    stats = temp_db.get_stats()
    assert stats["total_jobs_seen"] == 1
    assert stats["total_notified"] == 0


def test_database_mark_notified(temp_db, sample_cloud_intern_job):
    """Verifies marking jobs as notified updates state and timestamp."""
    temp_db.record_job(sample_cloud_intern_job, score=85)
    temp_db.mark_notified(sample_cloud_intern_job.hash_id)

    stats = temp_db.get_stats()
    assert stats["total_notified"] == 1

    recent = temp_db.get_recent_jobs(limit=1)
    assert len(recent) == 1
    assert recent[0]["notified"] == 1
