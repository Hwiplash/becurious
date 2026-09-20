from __future__ import annotations

import os


_TRUE_VALUES = {"1", "true", "yes", "on"}


def api_calls_enabled() -> bool:
    """Return True only when paid OpenAI calls were explicitly enabled."""
    return (
        os.getenv("ENABLE_OPENAI_API", "false").strip().lower() in _TRUE_VALUES
        and bool(os.getenv("OPENAI_API_KEY", "").strip())
    )


def require_api_calls_enabled() -> None:
    if not api_calls_enabled():
        raise RuntimeError(
            "OpenAI API calls are disabled. Set ENABLE_OPENAI_API=true and "
            "OPENAI_API_KEY to enable them."
        )
