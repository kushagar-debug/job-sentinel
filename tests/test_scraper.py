"""Unit tests for the LinkedIn HTML parser."""

import pytest
from core.scraper import LinkedInScraper

SAMPLE_HTML_PAYLOAD = """
<div class="base-card base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:4488990011">
    <div class="base-search-card__info">
        <h3 class="base-search-card__title">Site Reliability Engineering Intern</h3>
        <h4 class="base-search-card__subtitle"><a href="https://linkedin.com/company/stripe">Stripe</a></h4>
        <div class="base-search-card__metadata">
            <span class="job-search-card__location">San Francisco, CA</span>
            <time class="job-search-card__listdate">1 day ago</time>
        </div>
    </div>
    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/site-reliability-engineering-intern-at-stripe-4488990011?refId=xyz&position=1"></a>
</div>
"""


def test_scraper_parses_html_cards():
    """Verifies that LinkedIn HTML cards are accurately parsed into JobListing instances."""
    scraper = LinkedInScraper()
    jobs = scraper._parse_html(SAMPLE_HTML_PAYLOAD)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "4488990011"
    assert job.title == "Site Reliability Engineering Intern"
    assert job.company == "Stripe"
    assert job.location == "San Francisco, CA"
    assert job.posted_date == "1 day ago"
    assert job.url == "https://www.linkedin.com/jobs/view/4488990011"
