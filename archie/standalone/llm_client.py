#!/usr/bin/env python3
"""Provider-agnostic LLM client for Archie's CI pipeline.

All standalone-script LLM traffic that hits an HTTP API (the CI path — no
coding-agent CLI on runners) goes through this module. Two wire protocols:

    openai     — POST {base_url}/chat/completions, Bearer auth. This is
                 OpenRouter, Vercel AI Gateway, LiteLLM, Groq, Ollama, OpenAI
                 itself: anything OpenAI-compatible.
    anthropic  — POST api.anthropic.com/v1/messages, x-api-key auth. Kept so
                 existing installs with only ANTHROPIC_API_KEY keep working.

Configuration (first match wins per field):
    1. env overrides: ARCHIE_LLM_PROVIDER / ARCHIE_LLM_BASE_URL /
       ARCHIE_LLM_API_KEY_ENV / ARCHIE_MODEL_{HAIKU,SONNET,OPUS}
    2. {project_root}/.archie/models.json
       {"provider": "openrouter"|"openai"|"anthropic", "base_url": ...,
        "api_key_env": ..., "models": {"haiku"|"sonnet"|"opus": id},
        "enabled": true}
    3. auto-detect: OPENROUTER_API_KEY → openrouter, else
       ANTHROPIC_API_KEY → anthropic, else no API path.

Callers speak model *tiers* ("haiku"/"sonnet"/"opus"); the tier→model mapping
is config. Zero dependencies (stdlib urllib only) — project invariant.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENROUTER_URL = "https://openrouter.ai/api/v1"

TIERS = ("haiku", "sonnet", "opus")

ANTHROPIC_MODELS = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-8",
}
OPENROUTER_MODELS = {
    "haiku": "anthropic/claude-haiku-4.5",
    "sonnet": "anthropic/claude-sonnet-4.6",
    "opus": "anthropic/claude-opus-4.8",
}

DEFAULT_TIMEOUT = 90
DEFAULT_MAX_TOKENS = 4096

_PROVIDER_KEY_ENV = {
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "ARCHIE_LLM_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


class LLMError(RuntimeError):
    """Hard LLM failure after retries — callers decide fail-open vs raise."""


def _read_config_file(project_root) -> dict:
    if project_root is None:
        project_root = Path.cwd()
    path = Path(project_root) / ".archie" / "models.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def resolve_config(project_root=None, env=None):
    """Resolve provider config; return None when the API path is unavailable
    (no key / disabled) so callers take their existing fail-open branch."""
    if env is None:
        env = os.environ
    file_cfg = _read_config_file(project_root)
    if file_cfg.get("enabled") is False:
        return None

    provider = env.get("ARCHIE_LLM_PROVIDER") or file_cfg.get("provider")
    if not provider:
        if env.get("OPENROUTER_API_KEY"):
            provider = "openrouter"
        elif env.get("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        else:
            return None
    provider = str(provider).strip().lower()
    if provider not in _PROVIDER_KEY_ENV:
        print(f"[archie] llm: unknown provider {provider!r}", file=sys.stderr)
        return None

    key_env = (env.get("ARCHIE_LLM_API_KEY_ENV") or file_cfg.get("api_key_env")
               or _PROVIDER_KEY_ENV[provider])
    api_key = env.get(key_env, "")
    if not api_key:
        return None

    if provider == "anthropic":
        backend, base_url, defaults = "anthropic", ANTHROPIC_URL, ANTHROPIC_MODELS
    else:
        backend, defaults = "openai", OPENROUTER_MODELS
        base_url = (env.get("ARCHIE_LLM_BASE_URL") or file_cfg.get("base_url")
                    or (OPENROUTER_URL if provider == "openrouter" else ""))
        if not base_url:
            print("[archie] llm: provider 'openai' needs base_url", file=sys.stderr)
            return None
        base_url = base_url.rstrip("/")

    file_models = file_cfg.get("models") if isinstance(file_cfg.get("models"), dict) else {}
    models = {}
    for tier in TIERS:
        models[tier] = (env.get(f"ARCHIE_MODEL_{tier.upper()}")
                        or file_models.get(tier) or defaults[tier])
    return {"backend": backend, "base_url": base_url,
            "api_key": api_key, "models": models}
