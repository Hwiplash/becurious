from __future__ import annotations

import pytest

from src.api_access import api_calls_enabled, require_api_calls_enabled


def test_api_calls_are_enabled_by_server_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "server-only-test-key")
    monkeypatch.setenv("ENABLE_OPENAI_API", "false")

    assert api_calls_enabled() is True
    require_api_calls_enabled()


def test_api_calls_are_disabled_without_server_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert api_calls_enabled() is False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        require_api_calls_enabled()


def test_blank_server_key_does_not_enable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    assert api_calls_enabled() is False
