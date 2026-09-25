"""Smart Keyword Scoring Engine for Cloud Job Sentinel.

Strictly filters and scores job postings prioritizing DevOps/Cloud internships
and freshers in the Chandigarh/Mohali/Panchkula Tricity region or India-eligible Remote roles.
"""

import re
from typing import Dict, List, Tuple
from core.models import JobListing, MatchResult


class JobScorer:
    """Calculates relevance scores with strict geographic and role filtering."""

    # Chandigarh Tricity & Surrounding Tech Region
    CHANDIGARH_REGION_TERMS: List[str] = [
        "chandigarh",
        "mohali",
        "panchkula",
        "sahibzada ajit singh nagar",
        "tricity",
        "punjab",
        "haryana",
        "kharar",
        "zirakpur",
        "derabassi",
    ]

    # Remote work indicators
    REMOTE_TERMS: List[str] = [
        "remote",
        "work from home",
        "wfh",
        "anywhere",
        "telecommute",
    ]

    # Foreign non-eligible country indicators to filter out global noise
    FOREIGN_LOCATIONS: List[str] = [
        "united states",
        "usa",
        "united kingdom",
        "uk",
        "germany",
        "france",
        "hungary",
        "poland",
        "brazil",
        "canada",
        "netherlands",
        "australia",
        "spain",
        "italy",
        "romania",
        "switzerland",
    ]

    # Positive scoring weights for Fresher & Intern roles
    ROLE_TIER_WEIGHTS: Dict[str, int] = {
        "intern": 40,
        "internship": 40,
        "graduate engineer trainee": 40,
        "graduate trainee": 35,
        "get": 35,
        "fresher": 35,
        "trainee": 30,
        "apprentice": 30,
        "junior": 30,
        "entry level": 30,
        "associate software engineer": 25,
        "associate engineer": 25,
        "associate": 20,
        "campus": 25,
        "co-op": 30,
    }

    # Technical DevOps & Cloud Skills
    TECH_SKILL_WEIGHTS: Dict[str, int] = {
        "devops": 30,
        "cloud": 20,
        "sre": 25,
        "site reliability": 25,
        "platform engineer": 20,
        "docker": 18,
        "kubernetes": 20,
        "k8s": 20,
        "linux": 18,
        "ci/cd": 18,
        "terraform": 18,
        "github actions": 15,
        "python": 15,
        "automation": 15,
        "bash": 12,
        "aws": 18,
        "azure": 15,
        "gcp": 15,
        "backend": 12,
    }

    # Negative penalty weights (to filter out senior roles)
    PENALTY_WEIGHTS: Dict[str, int] = {
        "senior": 70,
        "sr.": 70,
        "lead": 60,
        "principal": 80,
        "staff": 70,
        "architect": 70,
        "director": 90,
        "head of": 90,
        "vp": 95,
        "manager": 50,
        "10+ years": 90,
        "8+ years": 80,
        "5+ years": 60,
        "3+ years": 40,
        "phd required": 60,
    }

    def __init__(self, min_score_threshold: int = 40):
        self.min_score_threshold = min_score_threshold

    def evaluate(self, job: JobListing) -> MatchResult:
        """Scores a job listing with strict geographic and role relevance gates."""
        search_corpus = f"{job.title} {job.description_snippet or ''}".lower()
        title_only = job.title.lower()
        location_lower = job.location.lower()

        # -------------------------------------------------------------
        # GATE 1: STRICT LOCATION FILTER
        # Must be Chandigarh/Mohali/Panchkula OR Valid Remote
        # -------------------------------------------------------------
        is_chandigarh = any(term in location_lower for term in self.CHANDIGARH_REGION_TERMS)
        is_remote = any(
            term in location_lower or term in title_only for term in self.REMOTE_TERMS
        )

        # Check if it is a foreign country listing (unless explicitly in India or global remote)
        is_foreign = any(country in location_lower for country in self.FOREIGN_LOCATIONS)
        has_india = "india" in location_lower or is_chandigarh

        if is_foreign and not has_india:
            # Drop foreign non-India jobs
            return MatchResult(
                job=job,
                score=0,
                matched_keywords=[],
                penalized_keywords=["foreign_location"],
                passed_threshold=False,
            )

        if not (is_chandigarh or is_remote):
            # Drop any role outside Chandigarh region that is not remote
            return MatchResult(
                job=job,
                score=0,
                matched_keywords=[],
                penalized_keywords=["outside_target_location"],
                passed_threshold=False,
            )

        matched_keywords: List[str] = []
        penalized_keywords: List[str] = []
        raw_score = 0

        # -------------------------------------------------------------
        # GATE 2: LOCATION PRIORITY BOOST
        # -------------------------------------------------------------
        if is_chandigarh:
            raw_score += 35
            matched_keywords.append("chandigarh_tricity")
        elif is_remote:
            raw_score += 15
            matched_keywords.append("remote")

        # -------------------------------------------------------------
        # GATE 3: ROLE TIER EVALUATION (Must be Fresher / Intern / Trainee)
        # -------------------------------------------------------------
        has_role_tier = False
        for term, weight in self.ROLE_TIER_WEIGHTS.items():
            if self._contains_word(term, search_corpus):
                matched_keywords.append(term)
                has_role_tier = True
                if self._contains_word(term, title_only):
                    raw_score += weight
                else:
                    raw_score += int(weight * 0.6)

        # -------------------------------------------------------------
        # GATE 4: TECHNICAL SKILL EVALUATION (DevOps / Cloud focus)
        # -------------------------------------------------------------
        has_tech_skill = False
        for tech, weight in self.TECH_SKILL_WEIGHTS.items():
            if self._contains_word(tech, search_corpus):
                matched_keywords.append(tech)
                has_tech_skill = True
                if self._contains_word(tech, title_only):
                    raw_score += weight
                else:
                    raw_score += int(weight * 0.5)

        # Must have at least ONE relevant tech skill (e.g. devops, cloud, linux, ci/cd)
        if not has_tech_skill:
            return MatchResult(
                job=job,
                score=0,
                matched_keywords=[],
                penalized_keywords=["no_devops_or_cloud_keyword"],
                passed_threshold=False,
            )

        # Must have at least ONE fresher / entry indicator
        if not has_role_tier:
            return MatchResult(
                job=job,
                score=0,
                matched_keywords=[],
                penalized_keywords=["not_fresher_or_intern"],
                passed_threshold=False,
            )

        # -------------------------------------------------------------
        # GATE 5: SENIORITY / EXPERIENCE PENALTIES
        # -------------------------------------------------------------
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
