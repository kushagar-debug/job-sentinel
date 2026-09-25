"""CLI Entrypoint for Cloud Job Sentinel.

Provides CLI switches for manual scans, daemon continuous monitoring,
Telegram credential verification, and database telemetry auditing.
"""

import argparse
import asyncio
import logging
import sys
from rich.console import Console

from config.settings import settings
from core.database import JobDatabase
import os
from dispatchers.telegram import TelegramDispatcher
from handlers.pipeline import SentinelPipeline

# Ensure logs directory exists for FileHandler across fresh CI checkouts
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/sentinel.log", mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
# Silence verbose third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

console = Console()


def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Cloud Job Sentinel - Automated LinkedIn Ingestion & Telegram Notifier"
    )
    parser.add_argument(
        "--keyword",
        type=str,
        help="Target keyword to search (e.g. 'Cloud Engineer Intern')",
    )
    parser.add_argument(
        "--location",
        type=str,
        help="Target location to search (e.g. 'Remote' or 'India')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum listings to ingest per query",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Minimum match score threshold (0-100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Simulate alerts in the console without sending Telegram messages",
    )
    parser.add_argument(
        "--send-telegram",
        action="store_true",
        help="Force real Telegram message dispatching (disables dry-run)",
    )
    parser.add_argument(
        "--test-telegram",
        action="store_true",
        help="Send a test ping to Telegram to verify credentials",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print database deduplication and telemetry statistics",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously in background daemon mode with periodic intervals",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Interval in seconds between runs when in daemon mode (default: 3600)",
    )
    return parser.parse_args()


async def main():
    """CLI orchestrator execution routine."""
    args = parse_args()

    # 1. Check Stats Flag
    if args.stats:
        db = JobDatabase(db_path=settings.database_path)
        stats = db.get_stats()
        console.print("\n[bold cyan]=== Sentinel Database Statistics ===[/bold cyan]")
        console.print(f"Total Seen Jobs: [green]{stats['total_jobs_seen']}[/green]")
        console.print(f"Total Notified: [green]{stats['total_notified']}[/green]")
        console.print(f"Average Score: [green]{stats['average_score']}%[/green]\n")
        return

    # 2. Check Test Telegram Ping
    if args.test_telegram:
        dispatcher = TelegramDispatcher(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            dry_run=False,
        )
        console.print("[cyan]Testing Telegram bot credentials...[/cyan]")
        success = await dispatcher.send_test_ping()
        if success:
            console.print("[bold green]Success: Bot connection verified![/bold green]")
        else:
            console.print(
                "[bold red]Failed: Could not send ping. Verify TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env[/bold red]"
            )
        return

    # 3. Configure Dry-Run & Alert Flags
    if args.send_telegram:
        settings.dry_run = False
    elif args.dry_run is not None:
        settings.dry_run = args.dry_run

    if args.min_score is not None:
        settings.min_match_score = args.min_score

    pipeline = SentinelPipeline(config=settings)

    keywords = [args.keyword] if args.keyword else None
    locations = [args.location] if args.location else None

    # 4. Daemon vs Single Run
    if args.daemon:
        console.print(
            f"[bold green]Starting Sentinel Daemon (interval: {args.interval}s)...[/bold green]"
        )
        while True:
            await pipeline.run(
                custom_keywords=keywords,
                custom_locations=locations,
                max_results=args.limit,
            )
            console.print(f"[dim]Sleeping for {args.interval} seconds...[/dim]")
            await asyncio.sleep(args.interval)
    else:
        await pipeline.run(
            custom_keywords=keywords,
            custom_locations=locations,
            max_results=args.limit,
        )


if __name__ == "__main__":
    asyncio.run(main())
