"""
End-to-end pipeline integration test with all external adapters mocked.
Verifies: state log written before Discord, allocation sum ≤ capital,
all key NDJSON entries present.
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
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


def _configure_settings(mock_settings, log_path, capital_min_position_usd=500.0):
    mock_settings.state_log_path = log_path
    mock_settings.barbell_safe_core_ratio = 0.60
    mock_settings.capital_min_position_usd = capital_min_position_usd
    mock_settings.barbell_safe_beta_max = 0.8
    mock_settings.barbell_safe_pe_max = 20.0
    mock_settings.barbell_safe_dividend_yield_min = 1.5
    mock_settings.barbell_safe_market_cap_min = 10_000_000_000.0
    mock_settings.barbell_satellite_momentum_min = 15.0
    mock_settings.barbell_satellite_rsi_min = 40.0
    mock_settings.barbell_satellite_rsi_max = 70.0
    mock_settings.barbell_satellite_analyst_min = 4.0
    mock_settings.sentiment_critical_delta = 0.3
    mock_settings.stock_tickers = ["AAPL"]
    mock_settings.reddit_subreddits = ["investing"]
    mock_settings.rss_feed_urls = []


@pytest.mark.asyncio
async def test_pipeline_writes_state_log_before_telegram(mock_settings):
    """State log must be written before Discord is called (Principle VI)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        _configure_settings(mock_settings, log_path)

        with (
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase in test")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.YFinanceAdapter") as MockYFinance,
            patch("src.pipeline.orchestrator.DiscordAdapter") as MockDiscord,
            patch("src.services.sentiment_service.SentimentService._call_llm") as mock_llm,
            patch("src.services.shortlist_service.ShortlistService._call_llm_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_llm_rationale") as mock_rationale,
        ):
            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockYFinance.return_value.get_technicals = AsyncMock(return_value={})

            discord_called_after_log = {"result": False}

            async def fake_discord(text: str) -> bool:
                entries = []
                if log_path.exists():
                    with open(log_path) as f:
                        entries = [json.loads(line) for line in f if line.strip()]
                actions = [e["action"] for e in entries]
                if ActionType.ALLOCATION_GENERATED.value in actions:
                    discord_called_after_log["result"] = True
                return True

            MockDiscord.return_value.send_message = fake_discord
            mock_llm.return_value = {
                "items": [{"id": "sig-1", "score": 0.7, "label": "BULLISH"}],
                "aggregate": 0.7,
                "summary": "Bullish.",
            }
            mock_reason.return_value = "Strong fundamentals."
            mock_rationale.return_value = ("Core allocation.", "Overall solid portfolio.")

            from src.pipeline.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            await orch.run_on_demand(capital=10_000.0)

        assert discord_called_after_log["result"], "Discord was called before state log was written"


@pytest.mark.asyncio
async def test_allocation_sum_does_not_exceed_capital(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        capital = 10_000.0
        _configure_settings(mock_settings, log_path)

        with (
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.YFinanceAdapter") as MockYFinance,
            patch("src.pipeline.orchestrator.DiscordAdapter") as MockDiscord,
            patch("src.services.sentiment_service.SentimentService._call_llm") as mock_llm,
            patch("src.services.shortlist_service.ShortlistService._call_llm_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_llm_rationale") as mock_rationale,
        ):
            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockYFinance.return_value.get_technicals = AsyncMock(return_value={})
            MockDiscord.return_value.send_message = AsyncMock(return_value=True)
            mock_llm.return_value = {
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
async def test_ndjson_contains_all_key_action_types(mock_settings):
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "state.ndjson"
        required_actions = {
            ActionType.PIPELINE_STARTED.value,
            ActionType.MACRO_INGESTION_COMPLETE.value,
            ActionType.SENTIMENT_SCORED.value,
            ActionType.ANALYSIS_COMPLETE.value,
            ActionType.BARBELL_CLASSIFIED.value,
            ActionType.ALLOCATION_GENERATED.value,
            ActionType.DISCORD_SENT.value,
            ActionType.PIPELINE_COMPLETED.value,
        }
        _configure_settings(mock_settings, log_path, capital_min_position_usd=0.0)

        with (
            patch("src.state.supabase_store._client", side_effect=Exception("no supabase")),
            patch("src.pipeline.orchestrator.RedditAdapter") as MockReddit,
            patch("src.pipeline.orchestrator.RSSAdapter") as MockRSS,
            patch("src.pipeline.orchestrator.FinnhubAdapter") as MockFinnhub,
            patch("src.pipeline.orchestrator.YFinanceAdapter") as MockYFinance,
            patch("src.pipeline.orchestrator.DiscordAdapter") as MockDiscord,
            patch("src.services.sentiment_service.SentimentService._call_llm") as mock_llm,
            patch("src.services.shortlist_service.ShortlistService._call_llm_reasoning") as mock_reason,
            patch("src.services.allocation_service.AllocationService._call_llm_rationale") as mock_rationale,
        ):
            MockReddit.return_value.fetch_signals = AsyncMock(return_value=MOCK_SIGNALS)
            MockRSS.return_value.fetch_signals = AsyncMock(return_value=[])
            MockFinnhub.return_value.get_quote = AsyncMock(return_value={"price": 180.0})
            MockFinnhub.return_value.get_fundamentals = AsyncMock(return_value={"pe_ratio": 28.0, "market_cap": 2_800_000_000_000.0, "beta": 0.9})
            MockFinnhub.return_value.get_technicals = AsyncMock(return_value={"rsi_14": 52.0, "momentum_90d": 8.0})
            MockYFinance.return_value.get_technicals = AsyncMock(return_value={})
            MockDiscord.return_value.send_message = AsyncMock(return_value=True)
            mock_llm.return_value = {
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
