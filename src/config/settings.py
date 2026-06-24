from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str

    # Financial data
    finnhub_api_key: str
    alpha_vantage_api_key: str

    # Reddit
    reddit_client_id: str
    reddit_client_secret: str
    reddit_user_agent: str = "investment-guidance-app/0.1"
    reddit_subreddits: list[str] = ["investing", "stocks", "economics"]
    reddit_hot_post_limit: int = 25

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Supabase
    supabase_url: str
    supabase_key: str

    # State log
    state_log_path: Path = Path.home() / ".investment-guidance" / "state.ndjson"

    # Capital allocation
    capital_min_position_usd: float = 500.0
    barbell_safe_core_ratio: float = 0.60  # 60% safe-core / 40% satellite

    # Barbell classification thresholds
    barbell_safe_beta_max: float = 0.8
    barbell_safe_pe_max: float = 20.0
    barbell_safe_dividend_yield_min: float = 1.5
    barbell_safe_market_cap_min: float = 10_000_000_000.0  # $10B
    barbell_satellite_beta_min: float = 1.2
    barbell_satellite_momentum_min: float = 15.0
    barbell_satellite_rsi_min: float = 40.0
    barbell_satellite_rsi_max: float = 70.0
    barbell_satellite_analyst_min: float = 4.0

    # Sentiment
    sentiment_critical_delta: float = 0.3

    # Monitor intervals (minutes) per volatility tier
    monitor_interval_high_vol_minutes: int = 15
    monitor_interval_med_vol_minutes: int = 30
    monitor_interval_low_vol_minutes: int = 60

    # Stock universe (tickers to analyse)
    stock_tickers: list[str] = []

    # RSS feeds
    rss_feed_urls: list[str] = []


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
