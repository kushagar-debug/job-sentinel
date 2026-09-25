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


def test_scorer_awards_top_priority_to_chandigarh_mohali_devops_intern():
    """Verifies that DevOps Intern postings in Chandigarh/Mohali get top priority."""
    scorer = JobScorer(min_score_threshold=40)
    job = JobListing(
        job_id="778899",
        title="DevOps Development Internship",
        company="Tricity Tech Solutions",
        location="Chandigarh, India",
        url="https://linkedin.com/jobs/view/778899",
    )
    result = scorer.evaluate(job)
    assert result.passed_threshold is True
    assert result.score >= 80
    assert "chandigarh_tricity" in result.matched_keywords
    assert "devops" in result.matched_keywords


def test_scorer_rejects_foreign_or_non_target_locations():
    """Verifies that jobs outside Chandigarh/Mohali and not remote are dropped."""
    scorer = JobScorer(min_score_threshold=40)
    job_hungary = JobListing(
        job_id="123",
        title="Cloud DevOps Intern",
        company="Euro Corp",
        location="Budapest, Hungary",
        url="https://linkedin.com/jobs/view/123",
    )
    result = scorer.evaluate(job_hungary)
    assert result.passed_threshold is False
    assert result.score == 0

    job_mumbai = JobListing(
        job_id="124",
        title="DevOps Intern",
        company="India Corp",
        location="Mumbai, Maharashtra, India",
        url="https://linkedin.com/jobs/view/124",
    )
    result_mumbai = scorer.evaluate(job_mumbai)
    # Non-remote, outside Chandigarh/Mohali -> dropped
    assert result_mumbai.passed_threshold is False
    assert result_mumbai.score == 0


def test_scorer_penalizes_senior_architect_roles(sample_senior_architect_job):
    """Verifies that senior and executive roles get penalized and fail the intern threshold."""
    scorer = JobScorer(min_score_threshold=40)
    result = scorer.evaluate(sample_senior_architect_job)

    assert result.passed_threshold is False
    assert result.score < 40


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
