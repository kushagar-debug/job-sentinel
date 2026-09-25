"""Smart Keyword Scoring Engine for Cloud Job Sentinel.

Evaluates job postings against targeted Cloud/DevOps/Backend Intern profiles,
rewarding junior & relevant keywords while aggressively penalizing senior roles.
"""

import re
from typing import Dict, List, Tuple
from core.models import JobListing, MatchResult


class JobScorer:
    """Calculates relevance scores for job listings."""

    # Positive scoring weights
    ROLE_TIER_WEIGHTS: Dict[str, int] = {
        "intern": 40,
        "internship": 40,
        "graduate engineer trainee": 40,
        "graduate trainee": 35,
        "get": 35,
        "co-op": 35,
        "trainee": 30,
        "apprentice": 30,
        "junior": 30,
        "entry level": 30,
        "fresher": 30,
        "graduate": 25,
        "campus": 25,
        "associate software engineer": 20,
        "associate engineer": 20,
        "associate": 15,
    }

    TECH_SKILL_WEIGHTS: Dict[str, int] = {
        "cloud": 20,
        "aws": 20,
        "azure": 18,
        "gcp": 18,
        "devops": 20,
        "sre": 20,
        "site reliability": 20,
        "platform engineer": 20,
        "docker": 18,
        "kubernetes": 18,
        "k8s": 18,
        "linux": 15,
        "terraform": 18,
        "ci/cd": 15,
        "github actions": 15,
        "python": 18,
        "backend": 15,
        "rest api": 10,
        "fastapi": 12,
        "automation": 12,
        "bash": 10,
        "shell": 10,
    }

    # Negative penalty weights (to filter out senior roles)
    PENALTY_WEIGHTS: Dict[str, int] = {
        "senior": 60,
        "sr.": 60,
        "lead": 50,
        "principal": 70,
        "staff": 60,
        "architect": 60,
        "director": 80,
        "head of": 80,
        "vp": 90,
        "manager": 40,
        "10+ years": 80,
        "8+ years": 70,
        "5+ years": 50,
        "phd required": 50,
    }

    def __init__(self, min_score_threshold: int = 40):
        self.min_score_threshold = min_score_threshold

    def evaluate(self, job: JobListing) -> MatchResult:
        """Scores a job listing and returns a MatchResult with diagnostics."""
        search_corpus = f"{job.title} {job.description_snippet or ''}".lower()
        title_only = job.title.lower()

        matched_keywords: List[str] = []
        penalized_keywords: List[str] = []
        raw_score = 0

        # 1. Evaluate Role Level in Title (highest weight)
        for term, weight in self.ROLE_TIER_WEIGHTS.items():
            if self._contains_word(term, search_corpus):
                matched_keywords.append(term)
                # Boost if present directly in the title
                if self._contains_word(term, title_only):
                    raw_score += weight
                else:
                    raw_score += int(weight * 0.6)

        # 2. Evaluate Technical Keywords
        for tech, weight in self.TECH_SKILL_WEIGHTS.items():
            if self._contains_word(tech, search_corpus):
                matched_keywords.append(tech)
                if self._contains_word(tech, title_only):
                    raw_score += weight
                else:
                    raw_score += int(weight * 0.5)

        # 3. Apply Seniority / Experience Penalties
        for penalty_term, penalty in self.PENALTY_WEIGHTS.items():
            if self._contains_word(penalty_term, search_corpus):
                penalized_keywords.append(penalty_term)
                raw_score -= penalty

        # Normalize score between 0 and 100
        final_score = max(0, min(100, raw_score))
        passed = final_score >= self.min_score_threshold

        return MatchResult(
            job=job,
            score=final_score,
            matched_keywords=list(set(matched_keywords)),
            penalized_keywords=list(set(penalized_keywords)),
            passed_threshold=passed,
        )

    @staticmethod
    def _contains_word(word: str, text: str) -> bool:
        """Checks if a term or multi-word phrase exists as whole tokens."""
        pattern = r"\b" + re.escape(word) + r"\b"
        return bool(re.search(pattern, text, re.IGNORECASE))
