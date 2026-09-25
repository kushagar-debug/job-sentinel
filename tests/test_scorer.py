"""Unit tests for the keyword scoring engine."""

import pytest
from core.models import JobListing
from core.scorer import JobScorer


def test_scorer_awards_high_score_to_intern_cloud_role(sample_cloud_intern_job):
    """Verifies that Cloud/DevOps Intern postings receive high match scores."""
    scorer = JobScorer(min_score_threshold=40)
    result = scorer.evaluate(sample_cloud_intern_job)

    assert result.passed_threshold is True
    assert result.score >= 70
    assert result.priority == "HIGH"
    assert "intern" in result.matched_keywords
    assert "cloud" in result.matched_keywords
    assert "aws" in result.matched_keywords
    assert len(result.penalized_keywords) == 0


def test_scorer_penalizes_senior_architect_roles(sample_senior_architect_job):
    """Verifies that senior and executive roles get penalized and fail the intern threshold."""
    scorer = JobScorer(min_score_threshold=40)
    result = scorer.evaluate(sample_senior_architect_job)

    assert result.passed_threshold is False
    assert result.score < 40
    assert "senior" in result.penalized_keywords or "principal" in result.penalized_keywords
    assert result.priority == "LOW"


def test_scorer_word_boundary_matching():
    """Ensures substrings do not falsely match (e.g. 'internal' should not match 'intern')."""
    scorer = JobScorer(min_score_threshold=40)
    job = JobListing(
        job_id="111",
        title="Internal Audit Lead",
        company="Banking Group",
        location="Remote",
        url="https://linkedin.com/jobs/view/111",
    )
    result = scorer.evaluate(job)
    assert "intern" not in result.matched_keywords
    assert result.passed_threshold is False
