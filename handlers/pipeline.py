"""Sentinel Pipeline Orchestrator.

Concurrently executes the ingestion, deduplication, scoring, and
notification pipeline with granular telemetry and execution reporting.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional
from rich.console import Console
from rich.table import Table

from config.settings import Settings, settings
from core.database import JobDatabase
from core.models import JobListing, MatchResult
from core.scorer import JobScorer
from core.scraper import LinkedInScraper
from dispatchers.telegram import TelegramDispatcher

logger = logging.getLogger("sentinel.pipeline")
console = Console()


@dataclass
class PipelineMetrics:
    """Telemetry captured during a pipeline execution cycle."""

    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    queries_run: int = 0
    scraped_listings: int = 0
    unique_new_jobs: int = 0
    duplicates_skipped: int = 0
    below_threshold_skipped: int = 0
    alerts_dispatched: int = 0

    @property
    def duration_seconds(self) -> float:
        """Returns elapsed run time in seconds."""
        finish = self.end_time if self.end_time > 0 else time.time()
        return round(finish - self.start_time, 2)


class SentinelPipeline:
    """Coordinates scraping, deduplication, scoring, and alerting."""

    def __init__(
        self,
        config: Optional[Settings] = None,
        db: Optional[JobDatabase] = None,
        scorer: Optional[JobScorer] = None,
        scraper: Optional[LinkedInScraper] = None,
        dispatcher: Optional[TelegramDispatcher] = None,
    ):
        self.config = config or settings
        self.db = db or JobDatabase(db_path=self.config.database_path)
        self.scorer = scorer or JobScorer(min_score_threshold=self.config.min_match_score)
        self.scraper = scraper or LinkedInScraper(
            timeout=self.config.request_timeout,
            delay_min=self.config.random_delay_min,
            delay_max=self.config.random_delay_max,
        )
        self.dispatcher = dispatcher or TelegramDispatcher(
            bot_token=self.config.telegram_bot_token,
            chat_id=self.config.telegram_chat_id,
            dry_run=self.config.dry_run,
        )

    async def run(
        self,
        custom_keywords: Optional[List[str]] = None,
        custom_locations: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> PipelineMetrics:
        """Executes a full ingestion and alerting cycle."""
        keywords = custom_keywords or self.config.search_keywords
        locations = custom_locations or self.config.search_locations
        limit = max_results or self.config.max_results_per_run

        metrics = PipelineMetrics()
        console.rule("[bold cyan]Cloud Job Sentinel Pipeline Starting[/bold cyan]")
        console.print(
            f"[dim]Keywords: {len(keywords)} | Locations: {len(locations)} | Dry Run: {self.dispatcher.dry_run}[/dim]\n"
        )

        qualifying_matches: List[MatchResult] = []

        for location in locations:
            for keyword in keywords:
                metrics.queries_run += 1
                try:
                    listings = await self.scraper.fetch_jobs(
                        keyword=keyword,
                        location=location,
                        max_results=limit,
                    )
                    metrics.scraped_listings += len(listings)

                    for job in listings:
                        match = self._evaluate_and_record(job, metrics)
                        if match and match.passed_threshold:
                            qualifying_matches.append(match)

                except Exception as exc:
                    logger.error(f"Error executing search for '{keyword}' in '{location}': {exc}")

        # Rank matches by score (highest relevance first) and limit to max_alerts_per_run
        qualifying_matches.sort(key=lambda m: m.score, reverse=True)
        max_alerts = getattr(self.config, "max_alerts_per_run", 5)
        top_alerts = qualifying_matches[:max_alerts]

        for match in top_alerts:
            success = await self.dispatcher.send_alert(match)
            if success:
                self.db.mark_notified(match.job.hash_id)
                metrics.alerts_dispatched += 1

        metrics.end_time = time.time()
        self._print_summary_table(metrics)
        return metrics

    def _evaluate_and_record(self, job: JobListing, metrics: PipelineMetrics) -> Optional[MatchResult]:
        """Evaluates a job listing and records it into SQLite."""
        # 1. Deduplication check
        if self.db.has_seen(job.hash_id):
            metrics.duplicates_skipped += 1
            return None

        metrics.unique_new_jobs += 1

        # 2. Score evaluation
        match = self.scorer.evaluate(job)

        # 3. Store record in database
        self.db.record_job(
            job=job,
            score=match.score,
            matched_keywords=match.matched_keywords,
        )

        if not match.passed_threshold:
            metrics.below_threshold_skipped += 1

        return match

    def _print_summary_table(self, metrics: PipelineMetrics) -> None:
        """Renders an execution summary table in the terminal."""
        table = Table(title="Sentinel Execution Summary", header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        db_stats = self.db.get_stats()

        table.add_row("Execution Duration", f"{metrics.duration_seconds}s")
        table.add_row("Search Queries Processed", str(metrics.queries_run))
        table.add_row("Total Listings Scraped", str(metrics.scraped_listings))
        table.add_row("Unique New Listings", str(metrics.unique_new_jobs))
        table.add_row("Duplicates Filtered (SHA-256)", str(metrics.duplicates_skipped))
        table.add_row("Below Score Threshold (<40)", str(metrics.below_threshold_skipped))
        table.add_row("Alerts Dispatched", str(metrics.alerts_dispatched))
        table.add_row("Total Jobs in SQLite DB", str(db_stats.get("total_jobs_seen", 0)))
        table.add_row("Lifetime Notified Jobs", str(db_stats.get("total_notified", 0)))

        console.print("\n")
        console.print(table)
        console.rule("[bold cyan]Pipeline Cycle Complete[/bold cyan]\n")
