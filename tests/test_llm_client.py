import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import llm_client


def _write_config(tmp_path, cfg):
    d = tmp_path / ".archie"
    d.mkdir(exist_ok=True)
    (d / "models.json").write_text(json.dumps(cfg))


class TestResolveConfig:
    def test_no_keys_no_config_returns_none(self, tmp_path):
        assert llm_client.resolve_config(tmp_path, env={}) is None

    def test_anthropic_key_only_selects_anthropic_backend(self, tmp_path):
        cfg = llm_client.resolve_config(tmp_path, env={"ANTHROPIC_API_KEY": "sk-a"})
        assert cfg["backend"] == "anthropic"
        assert cfg["api_key"] == "sk-a"
        assert cfg["base_url"] == llm_client.ANTHROPIC_URL
        assert cfg["models"] == llm_client.ANTHROPIC_MODELS
        assert cfg["models"]["haiku"] == "claude-haiku-4-5"

    def test_openrouter_key_wins_over_anthropic(self, tmp_path):
        cfg = llm_client.resolve_config(
            tmp_path, env={"ANTHROPIC_API_KEY": "sk-a", "OPENROUTER_API_KEY": "sk-or"})
        assert cfg["backend"] == "openai"
        assert cfg["api_key"] == "sk-or"
        assert cfg["base_url"] == llm_client.OPENROUTER_URL
        assert cfg["models"] == llm_client.OPENROUTER_MODELS

    def test_config_file_openrouter(self, tmp_path):
        _write_config(tmp_path, {
            "provider": "openrouter",
            "models": {"haiku": "google/gemini-2.5-flash"},
        })
        cfg = llm_client.resolve_config(tmp_path, env={"OPENROUTER_API_KEY": "sk-or"})
        assert cfg["backend"] == "openai"
        assert cfg["models"]["haiku"] == "google/gemini-2.5-flash"
        # unspecified tiers fall back to provider defaults
        assert cfg["models"]["opus"] == llm_client.OPENROUTER_MODELS["opus"]

    def test_config_file_generic_openai_requires_base_url(self, tmp_path):
        _write_config(tmp_path, {"provider": "openai", "api_key_env": "MY_KEY"})
        assert llm_client.resolve_config(tmp_path, env={"MY_KEY": "k"}) is None  # no base_url
        _write_config(tmp_path, {"provider": "openai", "base_url": "http://localhost:11434/v1",
                                 "api_key_env": "MY_KEY"})
        cfg = llm_client.resolve_config(tmp_path, env={"MY_KEY": "k"})
        assert cfg["backend"] == "openai"
        assert cfg["base_url"] == "http://localhost:11434/v1"

    def test_enabled_false_disables(self, tmp_path):
        _write_config(tmp_path, {"provider": "openrouter", "enabled": False})
        assert llm_client.resolve_config(
            tmp_path, env={"OPENROUTER_API_KEY": "sk-or"}) is None

    def test_missing_key_for_configured_provider_returns_none(self, tmp_path):
        _write_config(tmp_path, {"provider": "openrouter"})
        assert llm_client.resolve_config(tmp_path, env={}) is None

    def test_env_overrides_beat_config_file(self, tmp_path):
        _write_config(tmp_path, {"provider": "anthropic"})
        cfg = llm_client.resolve_config(tmp_path, env={
            "ANTHROPIC_API_KEY": "sk-a",
            "ARCHIE_LLM_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "sk-or",
            "ARCHIE_LLM_BASE_URL": "https://gw.example/v1",
            "ARCHIE_MODEL_HAIKU": "meta-llama/llama-4-scout",
        })
        assert cfg["backend"] == "openai"
        assert cfg["base_url"] == "https://gw.example/v1"
        assert cfg["models"]["haiku"] == "meta-llama/llama-4-scout"
        assert cfg["api_key"] == "sk-or"

    def test_api_key_env_override(self, tmp_path):
        cfg = llm_client.resolve_config(tmp_path, env={
            "ARCHIE_LLM_PROVIDER": "openrouter",
            "ARCHIE_LLM_API_KEY_ENV": "CUSTOM_KEY", "CUSTOM_KEY": "sk-c"})
        assert cfg["api_key"] == "sk-c"

    def test_malformed_config_file_ignored(self, tmp_path):
        d = tmp_path / ".archie"
        d.mkdir()
        (d / "models.json").write_text("{not json")
        cfg = llm_client.resolve_config(tmp_path, env={"ANTHROPIC_API_KEY": "sk-a"})
        assert cfg["backend"] == "anthropic"
