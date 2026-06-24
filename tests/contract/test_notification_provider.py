import pytest
from src.adapters.base import NotificationProvider


def test_notification_provider_is_abstract():
    with pytest.raises(TypeError):
        NotificationProvider()  # type: ignore[abstract]


def test_notification_provider_requires_send_message():
    assert "send_message" in NotificationProvider.__abstractmethods__


@pytest.mark.asyncio
async def test_send_message_returns_bool_on_success():
    class ConcreteProvider(NotificationProvider):
        async def send_message(self, text: str) -> bool:
            return True

    provider = ConcreteProvider()
    result = await provider.send_message("test message")
    assert isinstance(result, bool)
    assert result is True


@pytest.mark.asyncio
async def test_send_message_returns_false_on_failure():
    class FailingProvider(NotificationProvider):
        async def send_message(self, text: str) -> bool:
            return False

    provider = FailingProvider()
    result = await provider.send_message("test")
    assert result is False
