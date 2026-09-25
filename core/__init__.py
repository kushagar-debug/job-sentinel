"""Core domain package for Cloud Job Sentinel."""

from core.database import JobDatabase
from core.models import JobListing, MatchResult
from core.scorer import JobScorer
from core.scraper import LinkedInScraper

__all__ = ["JobDatabase", "JobListing", "MatchResult", "JobScorer", "LinkedInScraper"]
