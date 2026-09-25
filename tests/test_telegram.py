"""Unit tests for Telegram Dispatcher formatting and behavior."""

import pytest
from core.models import MatchResult
from dispatchers.telegram import TelegramDispatcher


def test_telegram_html_formatting(sample_cloud_intern_job):
    """Verifies that the generated HTML payload contains escaped characters and link tags."""
    match = MatchResult(
        job=sample_cloud_intern_job,
        score=90,
        matched_keywords=["intern", "cloud", "aws"],
        passed_threshold=True,
    )
    dispatcher = TelegramDispatcher(bot_token="test_token", chat_id="12345")
    html_msg = dispatcher.format_html_message(match)

    assert "Sentinel Match [HIGH PRIORITY]" in html_msg
    assert "Datadog" in html_msg
    assert "Cloud Engineering Intern - AWS / DevOps" in html_msg
    assert "<code>90%</code>" in html_msg
    assert "#cloud" in html_msg
    assert sample_cloud_intern_job.url in html_msg


@pytest.mark.asyncio
async def test_telegram_dry_run_dispatch(sample_cloud_intern_job):
    """Verifies that dry-run mode returns True without throwing network calls."""
    match = MatchResult(
        job=sample_cloud_intern_job,
        score=85,
        matched_keywords=["intern", "devops"],
        passed_threshold=True,
    )
    dispatcher = TelegramDispatcher(dry_run=True)
    success = await dispatcher.send_alert(match)
    assert success is True
