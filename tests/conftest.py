"""Shared test configuration: mock settings so no real API keys are needed."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def mock_settings(tmp_path):
    """Provide minimal mock settings for all tests."""
    s = MagicMock()
    s.anthropic_api_key = "test-anthropic-key"
    s.finnhub_api_key = "test-finnhub-key"
    s.alpha_vantage_api_key = "test-av-key"
    s.reddit_client_id = "test-reddit-id"
    s.reddit_client_secret = "test-reddit-secret"
    s.reddit_user_agent = "test-agent"
    s.reddit_subreddits = ["investing"]
    s.reddit_hot_post_limit = 5
    s.telegram_bot_token = "test-bot-token"
    s.telegram_chat_id = "test-chat-id"
    s.supabase_url = "https://test.supabase.co"
    s.supabase_key = "test-supabase-key"
    s.state_log_path = tmp_path / "state.ndjson"
    s.capital_min_position_usd = 500.0
    s.barbell_safe_core_ratio = 0.60
    s.barbell_safe_beta_max = 0.8
    s.barbell_safe_pe_max = 20.0
    s.barbell_safe_dividend_yield_min = 1.5
    s.barbell_safe_market_cap_min = 10_000_000_000.0
    s.barbell_satellite_beta_min = 1.2
    s.barbell_satellite_momentum_min = 15.0
    s.barbell_satellite_rsi_min = 40.0
    s.barbell_satellite_rsi_max = 70.0
    s.barbell_satellite_analyst_min = 4.0
    s.sentiment_critical_delta = 0.3
    s.monitor_interval_high_vol_minutes = 15
    s.monitor_interval_med_vol_minutes = 30
    s.monitor_interval_low_vol_minutes = 60
    s.stock_tickers = ["AAPL"]
    s.rss_feed_urls = []

    with patch("src.config.settings.get_settings", return_value=s):
        yield s
