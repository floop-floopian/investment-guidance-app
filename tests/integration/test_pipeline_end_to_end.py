"""
End-to-end pipeline integration test with all external adapters mocked.
Verifies: state log written before Telegram, allocation sum ≤ capital,
all key NDJSON entries present.
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.models.macro_signal import MacroSignal, SourceType, SentimentLabel
from src.models.stock import Stock, BarbellClass, VolatilityTier
from src.models.allocation import Allocation, AllocationBand
from src.models.state_log import ActionType


MOCK_SIGNALS = [
    MacroSignal(
        id="sig-1",
        source_type=SourceType.REDDIT,
        source_id="investing",
        title="Markets looking bullish",
        ingested_at=datetime.now(timezone.utc),
        sentiment_score=0.7,
        sentiment_label=SentimentLabel.BULLISH,
        run_id="run-test",
    )
]

MOCK_STOCKS = [
    Stock(
        ticker="AAPL",
        company_name="Apple Inc.",
        price=180.0,
        beta=0.9,
        pe_ratio=28.0,
        market_cap=2_800_000_000_000.0,
        rsi_14=52.0,
        momentum_90d=8.0,
        barbell_class=BarbellClass.SAFE_CORE,
        risk_reward_score=0.75,
        reasoning="Strong fundamentals with moderate momentum.",
        analyzed_at=datetime.now(timezone.utc),
        run_id="run-test",
    )
]

MOCK_ALLOCATIONS = [
    Allocation(
        ticker="AAPL",
        band=AllocationBand.SAFE_CORE,
        amount_usd=6_000.0,
        percentage=60.0,
        rationale="Core allocation based on barbell strategy.",
        run_id="run-test",
    )
]


@pytest.mark.asyncio
async def test_pipeline_writes_state_log_before_telegram():
    """State log must be written before Telegram is called (Principle VI)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        call_order = []

        with (
            patch("src.config.settings.get_settings") as mock_settings,
            patch("src.state.log_writer.get_settings") as mock_lw_settings,
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase in test")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.AlphaVantageAdapter") as MockAV,
            patch("src.pipeline.orchestrator.TelegramAdapter") as MockTelegram,
            patch("src.services.sentiment_service.SentimentService._call_claude") as mock_claude,
            patch("src.services.shortlist_service.ShortlistService._call_claude_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_claude_rationale") as mock_rationale,
        ):
            s = MagicMock()
            s.state_log_path = log_path
            s.barbell_safe_core_ratio = 0.60
            s.capital_min_position_usd = 500.0
            s.barbell_safe_beta_max = 0.8
            s.barbell_safe_pe_max = 20.0
            s.barbell_safe_dividend_yield_min = 1.5
            s.barbell_safe_market_cap_min = 10_000_000_000.0
            s.barbell_satellite_momentum_min = 15.0
            s.barbell_satellite_rsi_min = 40.0
            s.barbell_satellite_rsi_max = 70.0
            s.barbell_satellite_analyst_min = 4.0
            s.sentiment_critical_delta = 0.3
            s.stock_tickers = ["AAPL"]
            s.reddit_subreddits = ["investing"]
            s.rss_feed_urls = []
            mock_settings.return_value = s
            mock_lw_settings.return_value = s

            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockAV.return_value.get_technicals = AsyncMock(return_value={})

            telegram_called_after_log = {"result": False}

            async def fake_telegram(text: str) -> bool:
                entries = []
                if log_path.exists():
                    with open(log_path) as f:
                        entries = [json.loads(line) for line in f if line.strip()]
                actions = [e["action"] for e in entries]
                if ActionType.ALLOCATION_GENERATED.value in actions:
                    telegram_called_after_log["result"] = True
                return True

            MockTelegram.return_value.send_message = fake_telegram
            mock_claude.return_value = {
                "items": [{"id": "sig-1", "score": 0.7, "label": "BULLISH"}],
                "aggregate": 0.7,
                "summary": "Bullish.",
            }
            mock_reason.return_value = "Strong fundamentals."
            mock_rationale.return_value = ("Core allocation.", "Overall solid portfolio.")

            from src.pipeline.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            await orch.run_on_demand(capital=10_000.0)

        assert telegram_called_after_log["result"], "Telegram was called before state log was written"


@pytest.mark.asyncio
async def test_allocation_sum_does_not_exceed_capital():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        capital = 10_000.0

        with (
            patch("src.config.settings.get_settings") as mock_settings,
            patch("src.state.log_writer.get_settings") as mock_lw_settings,
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.AlphaVantageAdapter") as MockAV,
            patch("src.pipeline.orchestrator.TelegramAdapter") as MockTelegram,
            patch("src.services.sentiment_service.SentimentService._call_claude") as mock_claude,
            patch("src.services.shortlist_service.ShortlistService._call_claude_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_claude_rationale") as mock_rationale,
        ):
            s = MagicMock()
            s.state_log_path = log_path
            s.barbell_safe_core_ratio = 0.60
            s.capital_min_position_usd = 500.0
            s.barbell_safe_beta_max = 0.8
            s.barbell_safe_pe_max = 20.0
            s.barbell_safe_dividend_yield_min = 1.5
            s.barbell_safe_market_cap_min = 10_000_000_000.0
            s.barbell_satellite_momentum_min = 15.0
            s.barbell_satellite_rsi_min = 40.0
            s.barbell_satellite_rsi_max = 70.0
            s.barbell_satellite_analyst_min = 4.0
            s.sentiment_critical_delta = 0.3
            s.stock_tickers = ["AAPL"]
            s.reddit_subreddits = ["investing"]
            s.rss_feed_urls = []
            mock_settings.return_value = s
            mock_lw_settings.return_value = s

            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockAV.return_value.get_technicals = AsyncMock(return_value={})
            MockTelegram.return_value.send_message = AsyncMock(return_value=True)
            mock_claude.return_value = {
                "items": [{"id": "sig-1", "score": 0.7, "label": "BULLISH"}],
                "aggregate": 0.7,
                "summary": "Bullish.",
            }
            mock_reason.return_value = "Good stock."
            mock_rationale.return_value = ("Allocation rationale.", "Overall rationale.")

            from src.pipeline.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            run = await orch.run_on_demand(capital=capital)

        # Read allocations from log
        total = 0.0
        if log_path.exists():
            with open(log_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if entry.get("action") == ActionType.ALLOCATION_GENERATED.value:
                        for alloc in entry.get("payload", {}).get("allocations", []):
                            total += alloc.get("amount_usd", 0.0)

        assert total <= capital + 0.01, f"Allocations {total} exceed capital {capital}"


@pytest.mark.asyncio
async def test_ndjson_contains_all_key_action_types():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        required_actions = {
            ActionType.PIPELINE_STARTED.value,
            ActionType.MACRO_INGESTION_COMPLETE.value,
            ActionType.SENTIMENT_SCORED.value,
            ActionType.ANALYSIS_COMPLETE.value,
            ActionType.BARBELL_CLASSIFIED.value,
            ActionType.ALLOCATION_GENERATED.value,
            ActionType.TELEGRAM_SENT.value,
            ActionType.PIPELINE_COMPLETED.value,
        }

        with (
            patch("src.config.settings.get_settings") as mock_settings,
            patch("src.state.log_writer.get_settings") as mock_lw_settings,
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.AlphaVantageAdapter") as MockAV,
            patch("src.pipeline.orchestrator.TelegramAdapter") as MockTelegram,
            patch("src.services.sentiment_service.SentimentService._call_claude") as mock_claude,
            patch("src.services.shortlist_service.ShortlistService._call_claude_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_claude_rationale") as mock_rationale,
        ):
            s = MagicMock()
            s.state_log_path = log_path
            s.barbell_safe_core_ratio = 0.60
            s.capital_min_position_usd = 0.0
            s.barbell_safe_beta_max = 0.8
            s.barbell_safe_pe_max = 20.0
            s.barbell_safe_dividend_yield_min = 1.5
            s.barbell_safe_market_cap_min = 10_000_000_000.0
            s.barbell_satellite_momentum_min = 15.0
            s.barbell_satellite_rsi_min = 40.0
            s.barbell_satellite_rsi_max = 70.0
            s.barbell_satellite_analyst_min = 4.0
            s.sentiment_critical_delta = 0.3
            s.stock_tickers = ["AAPL"]
            s.reddit_subreddits = ["investing"]
            s.rss_feed_urls = []
            mock_settings.return_value = s
            mock_lw_settings.return_value = s

            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockAV.return_value.get_technicals = AsyncMock(return_value={})
            MockTelegram.return_value.send_message = AsyncMock(return_value=True)
            mock_claude.return_value = {
                "items": [{"id": "sig-1", "score": 0.7, "label": "BULLISH"}],
                "aggregate": 0.7,
                "summary": "Bullish.",
            }
            mock_reason.return_value = "Good stock."
            mock_rationale.return_value = ("Allocation rationale.", "Overall rationale.")

            from src.pipeline.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            await orch.run_on_demand(capital=10_000.0)

        found_actions = set()
        with open(log_path) as f:
            for line in f:
                if line.strip():
                    found_actions.add(json.loads(line)["action"])

        missing = required_actions - found_actions
        assert not missing, f"Missing NDJSON action types: {missing}"
