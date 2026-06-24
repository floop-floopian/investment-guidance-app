from datetime import datetime, timezone
import pytest
from src.adapters.base import MacroSignalProvider
from src.models.macro_signal import MacroSignal, SourceType, SentimentLabel


def test_macro_provider_is_abstract():
    with pytest.raises(TypeError):
        MacroSignalProvider()  # type: ignore[abstract]


def test_macro_provider_requires_fetch_signals():
    assert "fetch_signals" in MacroSignalProvider.__abstractmethods__


@pytest.mark.asyncio
async def test_fetch_signals_returns_list_of_macro_signals():
    now = datetime.now(timezone.utc)

    class ConcreteProvider(MacroSignalProvider):
        async def fetch_signals(self) -> list[MacroSignal]:
            return [
                MacroSignal(
                    id="test-1",
                    source_type=SourceType.REDDIT,
                    source_id="investing",
                    title="Market outlook positive",
                    ingested_at=now,
                )
            ]

    provider = ConcreteProvider()
    result = await provider.fetch_signals()
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], MacroSignal)


@pytest.mark.asyncio
async def test_fetch_signals_can_return_empty_list():
    class EmptyProvider(MacroSignalProvider):
        async def fetch_signals(self) -> list[MacroSignal]:
            return []

    provider = EmptyProvider()
    result = await provider.fetch_signals()
    assert result == []
