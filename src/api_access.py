from __future__ import annotations

import os


def _streamlit_api_key() -> str:
    """Read the deployment secret without failing outside Streamlit."""
    try:
        import streamlit as st

        return str(st.secrets.get("OPENAI_API_KEY", "")).strip()
    except (FileNotFoundError, KeyError, RuntimeError):
        return ""


def openai_api_key() -> str:
    """Return the server-side key from the environment or Streamlit Secrets."""
    key = os.getenv("OPENAI_API_KEY", "").strip() or _streamlit_api_key()
    if key and not os.getenv("OPENAI_API_KEY", "").strip():
        # The OpenAI SDK reads this server-process environment variable.
        os.environ["OPENAI_API_KEY"] = key
    return key


def api_calls_enabled() -> bool:
    """Return True when the server has an OpenAI API key configured."""
    return bool(openai_api_key())


def require_api_calls_enabled() -> None:
    if not api_calls_enabled():
        raise RuntimeError(
            "OpenAI API calls are unavailable. Set OPENAI_API_KEY on the server "
            "to enable them."
        )
