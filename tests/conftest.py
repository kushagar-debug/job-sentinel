"""Pytest fixtures for Cloud Job Sentinel test suite."""

import pytest
from core.database import JobDatabase
from core.models import JobListing


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated JobDatabase instance in a temporary directory."""
    db_file = tmp_path / "test_sentinel.db"
    return JobDatabase(db_path=str(db_file))


@pytest.fixture
def sample_cloud_intern_job():
    """Returns a high-relevance cloud intern job listing."""
    return JobListing(
        job_id="9911223344",
        title="Cloud Engineering Intern - AWS / DevOps",
        company="Datadog",
        location="Remote",
        url="https://www.linkedin.com/jobs/view/9911223344?refId=123",
        posted_date="1 day ago",
        description_snippet="Join our platform engineering team to build CI/CD pipelines with Docker and Kubernetes.",
    )


@pytest.fixture
def sample_senior_architect_job():
    """Returns a senior role that must be penalized and filtered."""
    return JobListing(
        job_id="8822334455",
        title="Senior Principal Cloud Architect (10+ years exp)",
        company="Global Enterprise Corp",
        location="New York, NY",
        url="https://www.linkedin.com/jobs/view/8822334455",
        posted_date="3 hours ago",
        description_snippet="Lead the cloud architecture strategy for enterprise migration.",
    )
