"""Shared brain for provider-backed simulators.

Supports two providers controlled by LLM_PROVIDER:
  - "anthropic" (default)
  - "openai"

The active model defaults to the provider's recommended model but can be
overridden with SWARM_MODEL. get_llm() returns the matching LangChain chat
model for LangGraph implementations.
"""
from __future__ import annotations

import os

PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()

_DEFAULTS = {"anthropic": "claude-sonnet-4-5-20250929", "openai": "gpt-4o"}
MODEL = os.environ.get("SWARM_MODEL") or _DEFAULTS.get(PROVIDER, "gpt-4o")

_anthropic_client = None
_openai_client = None


def _require_supported_provider() -> None:
    if PROVIDER not in _DEFAULTS:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER: {PROVIDER}. Supported providers: anthropic, openai."
        )


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Add it to .env or export it first."
            )
        from anthropic import Anthropic
        _anthropic_client = Anthropic()
    return _anthropic_client


def _get_openai():
    global _openai_client
    if _openai_client is None:
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env or export it first."
            )
        from openai import OpenAI
        _openai_client = OpenAI()
    return _openai_client


def think(system_prompt: str, user_text: str, max_tokens: int = 800) -> str:
    """Run one LLM turn and return plain text."""
    _require_supported_provider()
    if PROVIDER == "openai":
        client = _get_openai()
        resp = client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    client = _get_anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_text}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def get_llm():
    """Return the appropriate LangChain chat model for the configured provider."""
    _require_supported_provider()
    if PROVIDER == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=MODEL)

    from langchain_anthropic import ChatAnthropic
    return ChatAnthropic(model=MODEL)
