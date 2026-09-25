"""Integration tests for the SentinelPipeline."""

from unittest.mock import AsyncMock
import pytest
from core.models import JobListing
from handlers.pipeline import SentinelPipeline


@pytest.mark.asyncio
async def test_pipeline_execution_flow(temp_db, sample_cloud_intern_job):
    """Tests the full pipeline cycle from scraping to scoring, deduplication, and alerting."""
    mock_scraper = AsyncMock()
    mock_scraper.fetch_jobs.return_value = [sample_cloud_intern_job]

    mock_dispatcher = AsyncMock()
    mock_dispatcher.dry_run = True
    mock_dispatcher.send_alert.return_value = True

    pipeline = SentinelPipeline(
        db=temp_db,
        scraper=mock_scraper,
        dispatcher=mock_dispatcher,
    )

    metrics = await pipeline.run(
        custom_keywords=["Cloud Intern"],
        custom_locations=["Remote"],
        max_results=5,
    )

    assert metrics.queries_run == 1
    assert metrics.scraped_listings == 1
    assert metrics.unique_new_jobs == 1
    assert metrics.alerts_dispatched == 1
    assert mock_dispatcher.send_alert.called

    # Second run with same job should deduplicate
    metrics2 = await pipeline.run(
        custom_keywords=["Cloud Intern"],
        custom_locations=["Remote"],
        max_results=5,
    )
    assert metrics2.scraped_listings == 1
    assert metrics2.unique_new_jobs == 0
    assert metrics2.duplicates_skipped == 1
    assert metrics2.alerts_dispatched == 0
