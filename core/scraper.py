"""LinkedIn Job Ingestion Scraper.

Fetches real-time public job listings from LinkedIn using high-speed
async HTTP requests with randomized user-agents, canonical URL cleansing,
and polite backoff.
"""

import asyncio
import logging
import random
import re
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from core.models import JobListing

logger = logging.getLogger("sentinel.scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


class LinkedInScraper:
    """Async scraper for public LinkedIn job listings."""

    GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(
        self,
        timeout: float = 15.0,
        delay_min: float = 1.5,
        delay_max: float = 3.5,
    ):
        self.timeout = timeout
        self.delay_min = delay_min
        self.delay_max = delay_max

    def _get_headers(self) -> dict:
        """Generates realistic browser headers for guest queries."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.linkedin.com/jobs",
            "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }

    @staticmethod
    def _clean_job_url(raw_url: str, job_id: str) -> str:
        """Produces a clean canonical job URL without referral/tracking queries."""
        if job_id and job_id.isdigit():
            return f"https://www.linkedin.com/jobs/view/{job_id}"
        # Fallback: strip query string
        return raw_url.split("?")[0] if "?" in raw_url else raw_url

    async def fetch_jobs(
        self,
        keyword: str,
        location: str = "Remote",
        max_results: int = 25,
    ) -> List[JobListing]:
        """Scrapes LinkedIn for the given keyword and location.

        Paginates in chunks of 10-25 until max_results is reached or
        no further listings are returned.
        """
        results: List[JobListing] = []
        start = 0
        batch_size = 10  # LinkedIn default per guest page

        logger.info(
            f"Scanning LinkedIn: keyword='{keyword}', location='{location}', max={max_results}"
        )

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            while len(results) < max_results:
                params = {
                    "keywords": keyword,
                    "location": location,
                    "start": str(start),
                }

                try:
                    # Randomized delay to prevent rate-limiting
                    delay = random.uniform(self.delay_min, self.delay_max)
                    await asyncio.sleep(delay)

                    response = await client.get(
                        self.GUEST_SEARCH_URL,
                        params=params,
                        headers=self._get_headers(),
                    )

                    if response.status_code == 429:
                        logger.warning("LinkedIn rate limit (429) hit. Pausing scraper.")
                        break

                    if response.status_code != 200 or not response.text.strip():
                        logger.debug(
                            f"No more cards or non-200 status ({response.status_code}) at start={start}"
                        )
                        break

                    parsed_batch = self._parse_html(response.text)
                    if not parsed_batch:
                        logger.info(f"Reached end of listings at offset {start}.")
                        break

                    for job in parsed_batch:
                        if len(results) >= max_results:
                            break
                        results.append(job)

                    start += batch_size

                except Exception as exc:
                    logger.error(f"Error fetching LinkedIn jobs at offset {start}: {exc}")
                    break

        logger.info(
            f"Scan completed: found {len(results)} total listings for '{keyword}' in '{location}'."
        )
        return results

    def _parse_html(self, html_content: str) -> List[JobListing]:
        """Parses raw HTML cards into validated JobListing models."""
        soup = BeautifulSoup(html_content, "html.parser")
        # Match only top-level job cards, ignoring nested __info or __metadata divs
        cards = soup.select("div.job-search-card")
        if not cards:
            cards = soup.find_all(
                "div", class_=lambda c: c and ("job-search-card" in c or "base-card" in c) and "__" not in c
            )
        listings: List[JobListing] = []

        for card in cards:
            # 1. Extract URN / Job ID
            entity_urn = card.get("data-entity-urn", "")
            job_id_match = re.search(r"urn:li:jobPosting:(\d+)", entity_urn)
            job_id = job_id_match.group(1) if job_id_match else ""

            # 2. Title
            title_tag = card.find(["h3", "span"], class_=re.compile(r"base-search-card__title"))
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"

            # 3. Company
            company_tag = card.find(
                ["h4", "a"], class_=re.compile(r"base-search-card__subtitle")
            )
            company = company_tag.get_text(strip=True) if company_tag else "Unknown Company"

            # 4. Location
            loc_tag = card.find("span", class_=re.compile(r"job-search-card__location"))
            location = loc_tag.get_text(strip=True) if loc_tag else "Remote"

            # 5. Link & Clean URL
            link_tag = card.find("a", class_=re.compile(r"base-card__full-link|base-search-card--link"))
            raw_url = link_tag.get("href", "") if link_tag else ""
            if not job_id and raw_url:
                # Try to extract ID from URL
                id_from_url = re.search(r"/view/(\d+)", raw_url)
                if id_from_url:
                    job_id = id_from_url.group(1)

            if not job_id:
                # Fallback synthetic ID if neither URN nor URL contains numbers
                job_id = f"gen_{abs(hash(f'{company}_{title}')) % 10000000}"

            clean_url = self._clean_job_url(raw_url, job_id)

            # 6. Posted Date
            time_tag = card.find("time", class_=re.compile(r"job-search-card__listdate"))
            posted_date = time_tag.get_text(strip=True) if time_tag else None

            listings.append(
                JobListing(
                    job_id=job_id,
                    title=title,
                    company=company,
                    location=location,
                    url=clean_url,
                    posted_date=posted_date,
                    source="linkedin",
                )
            )

        return listings
