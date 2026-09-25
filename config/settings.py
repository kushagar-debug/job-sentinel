"""Configuration settings for Cloud Job Sentinel.

Loads configuration from environment variables and .env file
with typed validation using Pydantic Settings.
"""

from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema and defaults."""

    # Telegram Credentials
    telegram_bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token obtained from @BotFather",
    )
    telegram_chat_id: str = Field(
        default="",
        alias="TELEGRAM_CHAT_ID",
        description="Target Telegram chat ID or channel ID for alerts",
    )

    # Search Filters (stored as string or list, exposed cleanly as list)
    search_keywords_raw: Union[List[str], str] = Field(
        default="DevOps Intern, DevOps Trainee, Junior DevOps Engineer, Cloud DevOps Intern, Site Reliability Intern",
        alias="SEARCH_KEYWORDS",
    )
    search_locations_raw: Union[List[str], str] = Field(
        default="Chandigarh, India, Mohali, Punjab, India, Remote",
        alias="SEARCH_LOCATIONS",
    )

    # Matching & Limits
    min_match_score: int = Field(
        default=50,
        alias="MIN_MATCH_SCORE",
        ge=0,
        le=100,
        description="Minimum score threshold (0-100) to trigger an alert",
    )
    max_results_per_run: int = Field(
        default=10,
        alias="MAX_RESULTS_PER_RUN",
        ge=1,
        le=50,
        description="Max job cards to retrieve per search query",
    )
    max_alerts_per_run: int = Field(
        default=5,
        alias="MAX_ALERTS_PER_RUN",
        ge=1,
        le=20,
        description="Maximum Telegram alerts to send per cycle to prevent notification fatigue",
    )

    # Operational Flags
    dry_run: bool = Field(
        default=True,
        alias="DRY_RUN",
        description="If True, prints alerts to console without sending Telegram messages",
    )
    database_path: str = Field(
        default="data/sentinel.db",
        alias="DATABASE_PATH",
        description="Path to SQLite database for deduplication",
    )
    headless: bool = Field(
        default=True,
        alias="HEADLESS",
        description="Run browser in headless mode",
    )

    # Network Timeouts
    request_timeout: float = Field(default=15.0, alias="REQUEST_TIMEOUT")
    page_load_timeout: float = Field(default=30.0, alias="PAGE_LOAD_TIMEOUT")
    random_delay_min: float = Field(default=1.5, alias="RANDOM_DELAY_MIN")
    random_delay_max: float = Field(default=3.5, alias="RANDOM_DELAY_MAX")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def search_keywords(self) -> List[str]:
        """Returns search keywords as a normalized list."""
        if isinstance(self.search_keywords_raw, list):
            return self.search_keywords_raw
        return [k.strip() for k in str(self.search_keywords_raw).split(",") if k.strip()]

    @property
    def search_locations(self) -> List[str]:
        """Returns search locations as a normalized list."""
        if isinstance(self.search_locations_raw, list):
            return self.search_locations_raw
        return [loc.strip() for loc in str(self.search_locations_raw).split(",") if loc.strip()]


# Global singleton instance
settings = Settings()
