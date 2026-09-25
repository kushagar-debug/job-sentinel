"""Data models for Cloud Job Sentinel.

Defines schemas for parsed job postings, scoring evaluations, and telemetry.
"""

import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class JobListing(BaseModel):
    """Represents an ingested job listing from LinkedIn."""

    job_id: str = Field(description="Unique job identifier or reference slug")
    title: str = Field(description="Title of the job posting")
    company: str = Field(description="Hiring company name")
    location: str = Field(default="Remote", description="Location or remote indicator")
    url: str = Field(description="Direct URL to the job listing")
    posted_date: Optional[str] = Field(default=None, description="Human or ISO posted time")
    source: str = Field(default="linkedin", description="Ingestion source platform")
    description_snippet: Optional[str] = Field(
        default="", description="Snippet or brief description of the role"
    )
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the sentinel ingested this listing",
    )

    @property
    def hash_id(self) -> str:
        """Computes a deterministic SHA-256 fingerprint for deduplication.

        Normalizes company, title, and location to detect duplicates even if
        URLs differ or job IDs get re-assigned.
        """
        fingerprint = f"{self.company.strip().lower()}::{self.title.strip().lower()}::{self.location.strip().lower()}"
        return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


class MatchResult(BaseModel):
    """Evaluation result produced by the keyword scoring engine."""

    job: JobListing
    score: int = Field(ge=0, le=100, description="Calculated relevance score")
    matched_keywords: List[str] = Field(
        default_factory=list, description="Keywords positively matched"
    )
    penalized_keywords: List[str] = Field(
        default_factory=list, description="Keywords negatively matched"
    )
    passed_threshold: bool = Field(
        default=False, description="Whether this score meets or exceeds min threshold"
    )

    @property
    def priority(self) -> str:
        """Determines alert priority badge."""
        if self.score >= 75:
            return "HIGH"
        if self.score >= 50:
            return "MEDIUM"
        return "LOW"
