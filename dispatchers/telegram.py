"""Telegram Notification Dispatcher for Cloud Job Sentinel.

Dispatches high-priority alert cards to a designated Telegram chat/channel
with interactive 'Apply Now' buttons and score telemetry.
Falls back cleanly to terminal/dry-run logging when credentials are unset.
"""

import html
import logging
from typing import Optional
import httpx
from rich.console import Console
from rich.panel import Panel

from core.models import MatchResult

logger = logging.getLogger("sentinel.dispatcher")
console = Console()


class TelegramDispatcher:
    """Sends job alert notifications via Telegram Bot API."""

    BASE_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        dry_run: bool = True,
        timeout: float = 10.0,
    ):
        self.bot_token = bot_token or ""
        self.chat_id = chat_id or ""
        self.dry_run = dry_run or not (self.bot_token and self.chat_id)
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Checks if active Telegram credentials are provided."""
        return bool(self.bot_token and self.chat_id)

    def format_html_message(self, match: MatchResult) -> str:
        """Builds an HTML formatted Telegram message payload."""
        job = match.job
        priority_emoji = "🔥" if match.priority == "HIGH" else "⚡"
        
        # Safe HTML escape for dynamic web text
        title = html.escape(job.title)
        company = html.escape(job.company)
        location = html.escape(job.location)
        posted = html.escape(job.posted_date or "Recently")
        
        tags = " ".join([f"#{kw.replace(' ', '_').replace('/', '_')}" for kw in match.matched_keywords])
        if not tags:
            tags = "#intern #cloud"

        message = (
            f"<b>{priority_emoji} Sentinel Match [{match.priority} PRIORITY]</b>\n\n"
            f"💼 <b>Role:</b> {title}\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"📍 <b>Location:</b> {location}\n"
            f"🕒 <b>Posted:</b> {posted}\n"
            f"📊 <b>Score:</b> <code>{match.score}%</code>\n"
            f"🏷️ <b>Tags:</b> <i>{tags}</i>\n\n"
            f"🔗 <a href=\"{job.url}\">Click to View on LinkedIn</a>"
        )
        return message

    def _render_console_card(self, match: MatchResult) -> None:
        """Renders an attractive rich panel for dry-run inspection."""
        job = match.job
        color = "green" if match.priority == "HIGH" else "yellow"
        
        content = (
            f"[bold {color}]Relevance Score: {match.score}% ({match.priority})[/bold {color}]\n"
            f"[bold white]Role:[/bold white] {job.title}\n"
            f"[bold white]Company:[/bold white] {job.company}\n"
            f"[bold white]Location:[/bold white] {job.location}\n"
            f"[bold white]Posted:[/bold white] {job.posted_date or 'Recent'}\n"
            f"[bold white]Matched:[/bold white] {', '.join(match.matched_keywords)}\n"
            f"[bold cyan]URL:[/bold cyan] {job.url}"
        )
        
        console.print(
            Panel(
                content,
                title=f"[bold]SENTINEL ALERT — {job.company}[/bold]",
                border_style=color,
            )
        )

    async def send_alert(self, match: MatchResult) -> bool:
        """Dispatches an alert for a matched job.

        Returns True if successfully alerted or simulated in dry-run.
        """
        if self.dry_run:
            self._render_console_card(match)
            return True

        url = self.BASE_API_URL.format(token=self.bot_token)
        text = self.format_html_message(match)
        
        # Construct inline keyboard with direct apply button
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "reply_markup": {
                "inline_keyboard": [
                    [{"text": "🚀 Apply on LinkedIn", "url": match.job.url}]
                ]
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    logger.info(f"Telegram alert sent successfully for: {match.job.title}")
                    return True
                else:
                    logger.error(
                        f"Telegram API error ({response.status_code}): {response.text}"
                    )
                    return False
        except Exception as exc:
            logger.error(f"Failed to communicate with Telegram API: {exc}")
            return False

    async def send_test_ping(self) -> bool:
        """Sends a verification ping to confirm bot token and chat ID."""
        if not self.is_configured:
            console.print("[yellow]Telegram credentials not configured in .env[/yellow]")
            return False

        url = self.BASE_API_URL.format(token=self.bot_token)
        payload = {
            "chat_id": self.chat_id,
            "text": "🟢 <b>Cloud Job Sentinel</b>: Connection verified successfully!",
            "parse_mode": "HTML",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                return response.status_code == 200
        except Exception as exc:
            logger.error(f"Test ping failed: {exc}")
            return False
