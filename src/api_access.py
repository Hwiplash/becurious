from __future__ import annotations

import os


def api_calls_enabled() -> bool:
    """Return True when the server has an OpenAI API key configured."""
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def require_api_calls_enabled() -> None:
    if not api_calls_enabled():
        raise RuntimeError(
            "OpenAI API calls are unavailable. Set OPENAI_API_KEY on the server "
            "to enable them."
        )
