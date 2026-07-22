# LLM Provider Abstraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route all CI-review LLM traffic through a new provider-agnostic `llm_client.py` (OpenRouter/OpenAI-compatible + Anthropic backends), configured via `.archie/models.json` + env overrides, with existing `ANTHROPIC_API_KEY`-only installs unchanged.

**Architecture:** One new zero-dependency standalone module `archie/standalone/llm_client.py` exposes `resolve_config()` and `complete()`. Two protocol backends (`openai`, `anthropic`) live inside it, including a normalized tool-use loop and unified retry. `agent_cli.py` (`_run_api`, `_run_api_tools`) and `intent_review.py::call_anthropic` become thin wrappers. Spec: `docs/archie-llm-provider-design.md`.

**Tech Stack:** Python 3.9+ stdlib only (`urllib`, `json`), pytest.

## Global Constraints

- Zero dependencies: stdlib only, raw `urllib.request` — never import a vendor SDK.
- Python 3.9 compatible (no `match`, no `X | Y` type unions at runtime except behind `from __future__ import annotations`).
- File sync invariant: every changed/created file under `archie/standalone/` must be copied to `npm-package/assets/`, and `python3 scripts/verify_sync.py` must pass before commit.
- Fail-open: CI review must never fail the check because an LLM is missing/unreachable.
- Existing behavior with only `ANTHROPIC_API_KEY` set must be unchanged (same models, same request shape).
- Run tests with `python3 -m pytest tests/ -v` (targeted files per task).

---

### Task 1: `llm_client.py` — config resolution

**Files:**
- Create: `archie/standalone/llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Produces: `resolve_config(project_root=None, env=None) -> dict | None` returning
  `{"backend": "openai"|"anthropic", "base_url": str, "api_key": str, "models": {"haiku": str, "sonnet": str, "opus": str}}`, or `None` when disabled / no key available.
- Produces module constants later tasks use: `ANTHROPIC_URL`, `OPENROUTER_URL`, `ANTHROPIC_MODELS`, `OPENROUTER_MODELS`, `LLMError`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm_client.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_llm_client.py -v`
Expected: FAIL / error with `ModuleNotFoundError: No module named 'llm_client'`

- [ ] **Step 3: Implement config resolution**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_llm_client.py -v`
Expected: all `TestResolveConfig` tests PASS

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): provider config resolution for CI LLM client"
```

---

### Task 2: `llm_client.py` — `complete()` with anthropic backend (plain, forced tool, tool loop, retry)

**Files:**
- Modify: `archie/standalone/llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Produces:
  ```python
  complete(prompt=None, *, system=None, tier="haiku", tools=None, tool_choice=None,
           max_tokens=4096, timeout=90, config=None, project_root=None,
           tool_executor=None, max_turns=6, budget_bytes=60000,
           max_retries=3) -> dict
  ```
  Returns `{"text": str, "tool_calls": [{"name": str, "input": dict}]}`.
  Raises `LLMError` on hard failure after retries. If `config is None` it calls
  `resolve_config(project_root)`; if that is `None`, raises `LLMError("no provider")`.
- `tools` uses the existing Anthropic-ish neutral shape already present in the
  codebase: `{"name", "description", "input_schema"}` (this is what
  `agent_cli._TOOLS` and `intent_review.EMIT_FINDINGS_TOOL` look like today).
- `tool_choice` is a tool *name* (string) to force, or `None`.
- `tool_executor` is `callable(name: str, args: dict) -> str`; when given,
  `complete()` runs the multi-turn tool loop and returns the final result.

- [ ] **Step 1: Write the failing tests (stubbed transport)**

Add to `tests/test_llm_client.py`:

```python
class FakeTransport:
    """Captures request bodies; replays scripted responses."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []  # list of (url, headers, body_dict)

    def __call__(self, url, body, headers, timeout, max_retries):
        self.requests.append((url, headers, json.loads(body.decode())))
        resp = self.responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp


ANTH_CFG = {"backend": "anthropic", "base_url": llm_client.ANTHROPIC_URL,
            "api_key": "sk-a", "models": dict(llm_client.ANTHROPIC_MODELS)}


class TestAnthropicBackend:
    def test_plain_completion(self, monkeypatch):
        t = FakeTransport([{"content": [{"type": "text", "text": "hello"}],
                            "stop_reason": "end_turn"}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("hi", tier="sonnet", config=ANTH_CFG)
        assert out["text"] == "hello"
        assert out["tool_calls"] == []
        url, headers, body = t.requests[0]
        assert url == llm_client.ANTHROPIC_URL
        assert headers["x-api-key"] == "sk-a"
        assert headers["anthropic-version"] == llm_client.ANTHROPIC_VERSION
        assert body["model"] == "claude-sonnet-4-6"
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert "tools" not in body

    def test_forced_tool_choice(self, monkeypatch):
        tool = {"name": "emit_findings", "description": "d",
                "input_schema": {"type": "object", "properties": {}}}
        t = FakeTransport([{"content": [{"type": "tool_use", "name": "emit_findings",
                                         "input": {"findings": [1]}}],
                            "stop_reason": "tool_use"}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("go", system="sys", tools=[tool],
                                  tool_choice="emit_findings", config=ANTH_CFG)
        assert out["tool_calls"] == [{"name": "emit_findings", "input": {"findings": [1]}}]
        _, _, body = t.requests[0]
        assert body["system"] == "sys"
        assert body["tool_choice"] == {"type": "tool", "name": "emit_findings"}
        assert body["tools"] == [tool]

    def test_tool_loop_executes_and_returns_final_text(self, monkeypatch):
        tool = {"name": "grep", "description": "d",
                "input_schema": {"type": "object", "properties": {}}}
        t = FakeTransport([
            {"content": [{"type": "tool_use", "id": "t1", "name": "grep",
                          "input": {"pattern": "x"}}],
             "stop_reason": "tool_use"},
            {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn"},
        ])
        monkeypatch.setattr(llm_client, "_post_json", t)
        calls = []
        out = llm_client.complete(
            "go", tools=[tool], config=ANTH_CFG,
            tool_executor=lambda name, args: calls.append((name, args)) or "hit")
        assert out["text"] == "done"
        assert calls == [("grep", {"pattern": "x"})]
        # second request carries the tool_result back
        _, _, body2 = t.requests[1]
        assert body2["messages"][-1]["content"][0]["type"] == "tool_result"
        assert body2["messages"][-1]["content"][0]["content"] == "hit"

    def test_tool_loop_caps_turns(self, monkeypatch):
        tool_use = {"content": [{"type": "tool_use", "id": "t", "name": "grep",
                                 "input": {}}, {"type": "text", "text": "partial"}],
                    "stop_reason": "tool_use"}
        t = FakeTransport([tool_use, tool_use])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("go", tools=[{"name": "grep", "description": "",
                                                "input_schema": {}}],
                                  config=ANTH_CFG, max_turns=2,
                                  tool_executor=lambda n, a: "x")
        assert out["text"] == "partial"  # degrades to last seen text

    def test_no_provider_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(llm_client, "resolve_config", lambda *a, **k: None)
        with pytest.raises(llm_client.LLMError):
            llm_client.complete("hi")


class TestRetry:
    def _http_error(self, code, retry_after=None):
        import io
        import urllib.error
        headers = {"Retry-After": retry_after} if retry_after else {}
        class H(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)
        return urllib.error.HTTPError("u", code, "err", H(headers), io.BytesIO(b"boom"))

    def test_retries_on_429_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
        ok = {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn"}
        err = self._http_error(429)
        seq = [err, ok]
        def fake_urlopen(req, timeout):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            import io
            return io.BytesIO(json.dumps(item).encode())
        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        out = llm_client.complete("hi", config=ANTH_CFG)
        assert out["text"] == "ok"

    def test_exhausted_retries_raise_llmerror(self, monkeypatch):
        monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
        def fake_urlopen(req, timeout):
            raise self._http_error(503)
        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(llm_client.LLMError):
            llm_client.complete("hi", config=ANTH_CFG, max_retries=2)

    def test_400_does_not_retry(self, monkeypatch):
        calls = {"n": 0}
        def fake_urlopen(req, timeout):
            calls["n"] += 1
            raise self._http_error(400)
        monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
        with pytest.raises(llm_client.LLMError):
            llm_client.complete("hi", config=ANTH_CFG, max_retries=3)
        assert calls["n"] == 1
```

Note: `fake_urlopen` return objects need `.read()` and context-manager support; use this helper at the top of the test file:

```python
class _Resp:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode()
    def read(self):
        return self._data
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
```

and have `fake_urlopen` return `_Resp(item)` instead of `io.BytesIO`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_llm_client.py -v -k "Anthropic or Retry"`
Expected: FAIL with `AttributeError: module 'llm_client' has no attribute 'complete'` (or `_post_json`)

- [ ] **Step 3: Implement `_post_json`, `complete`, and the anthropic backend**

Append to `archie/standalone/llm_client.py`:

```python
_RETRYABLE = {429, 500, 502, 503, 529}


def _post_json(url, body, headers, timeout, max_retries):
    """POST JSON with unified retry (429/5xx/529, honoring Retry-After).
    Returns the decoded JSON dict; raises LLMError on hard failure."""
    last_err = "unknown"
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            last_err = f"HTTP {e.code}: {detail}"
            if e.code in _RETRYABLE and attempt < max_retries - 1:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                delay = float(retry_after) if retry_after and str(retry_after).isdigit() \
                    else min(2 ** attempt, 30)
                time.sleep(delay)
                continue
            raise LLMError(f"LLM API error: {last_err}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < max_retries - 1:
                time.sleep(min(2 ** attempt, 30))
                continue
            raise LLMError(f"LLM API unreachable: {last_err}")
    raise LLMError(f"LLM API failed: {last_err}")


def complete(prompt=None, *, system=None, tier="haiku", tools=None,
             tool_choice=None, max_tokens=DEFAULT_MAX_TOKENS,
             timeout=DEFAULT_TIMEOUT, config=None, project_root=None,
             tool_executor=None, max_turns=6, budget_bytes=60000,
             max_retries=3):
    """One normalized completion across backends.

    Returns {"text": str, "tool_calls": [{"name", "input"}]}. With
    `tool_executor`, runs the multi-turn tool loop internally (executor gets
    (name, args-dict), returns a string) and returns the final turn's result.
    Raises LLMError on hard failure — callers pick fail-open vs propagate.
    """
    if config is None:
        config = resolve_config(project_root)
    if config is None:
        raise LLMError("no LLM provider configured (no API key / disabled)")
    model = config["models"].get(tier) or config["models"]["haiku"]
    args = dict(model=model, system=system, tools=tools, tool_choice=tool_choice,
                max_tokens=max_tokens, timeout=timeout, config=config,
                tool_executor=tool_executor, max_turns=max_turns,
                budget_bytes=budget_bytes, max_retries=max_retries)
    if config["backend"] == "anthropic":
        return _complete_anthropic(prompt, **args)
    return _complete_openai(prompt, **args)


def _complete_anthropic(prompt, *, model, system, tools, tool_choice, max_tokens,
                        timeout, config, tool_executor, max_turns, budget_bytes,
                        max_retries):
    headers = {"content-type": "application/json", "x-api-key": config["api_key"],
               "anthropic-version": ANTHROPIC_VERSION}
    messages = [{"role": "user", "content": prompt}]
    spent = 0
    last_text = ""
    turns = max_turns if tool_executor else 1
    for _ in range(turns):
        body_d = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            body_d["system"] = system
        if tools:
            body_d["tools"] = tools
        if tool_choice:
            body_d["tool_choice"] = {"type": "tool", "name": tool_choice}
        data = _post_json(config["base_url"], json.dumps(body_d).encode("utf-8"),
                          headers, timeout, max_retries)
        content = data.get("content") or []
        last_text = "".join(b.get("text", "") for b in content
                            if b.get("type") == "text") or last_text
        tool_calls = [{"name": b.get("name"), "input": b.get("input") or {}}
                      for b in content if b.get("type") == "tool_use"]
        if not tool_executor or data.get("stop_reason") != "tool_use":
            return {"text": last_text, "tool_calls": tool_calls}
        messages.append({"role": "assistant", "content": content})
        results = []
        for b in content:
            if b.get("type") != "tool_use":
                continue
            if spent >= budget_bytes:
                out = "denied: tool budget exhausted"
            else:
                try:
                    out = tool_executor(b.get("name"), b.get("input") or {})
                except Exception:
                    out = "denied: tool call failed"
                spent += len(out)
            results.append({"type": "tool_result", "tool_use_id": b.get("id"),
                            "content": out})
        messages.append({"role": "user", "content": results})
    return {"text": last_text, "tool_calls": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_llm_client.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): complete() with anthropic backend, tool loop, unified retry"
```

---

### Task 3: `llm_client.py` — openai-compatible backend

**Files:**
- Modify: `archie/standalone/llm_client.py`
- Test: `tests/test_llm_client.py`

**Interfaces:**
- Consumes: `_post_json`, `complete()` dispatch from Task 2.
- Produces: `_complete_openai(...)` with the same signature/return contract as `_complete_anthropic`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_llm_client.py`:

```python
OAI_CFG = {"backend": "openai", "base_url": llm_client.OPENROUTER_URL,
           "api_key": "sk-or", "models": dict(llm_client.OPENROUTER_MODELS)}


class TestOpenAIBackend:
    def test_plain_completion(self, monkeypatch):
        t = FakeTransport([{"choices": [{"message": {"content": "hello"},
                                         "finish_reason": "stop"}]}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("hi", system="sys", tier="haiku", config=OAI_CFG)
        assert out["text"] == "hello"
        url, headers, body = t.requests[0]
        assert url == llm_client.OPENROUTER_URL + "/chat/completions"
        assert headers["Authorization"] == "Bearer sk-or"
        assert body["model"] == "anthropic/claude-haiku-4.5"
        assert body["messages"][0] == {"role": "system", "content": "sys"}
        assert body["messages"][1] == {"role": "user", "content": "hi"}

    def test_tool_translation_and_forced_choice(self, monkeypatch):
        tool = {"name": "emit_findings", "description": "d",
                "input_schema": {"type": "object", "properties": {}}}
        t = FakeTransport([{"choices": [{"message": {
            "content": None,
            "tool_calls": [{"id": "c1", "function": {
                "name": "emit_findings",
                "arguments": "{\"findings\": [1]}"}}]},
            "finish_reason": "tool_calls"}]}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("go", tools=[tool], tool_choice="emit_findings",
                                  config=OAI_CFG)
        assert out["tool_calls"] == [{"name": "emit_findings", "input": {"findings": [1]}}]
        _, _, body = t.requests[0]
        assert body["tools"] == [{"type": "function", "function": {
            "name": "emit_findings", "description": "d",
            "parameters": {"type": "object", "properties": {}}}}]
        assert body["tool_choice"] == {"type": "function",
                                       "function": {"name": "emit_findings"}}

    def test_tool_loop(self, monkeypatch):
        tool = {"name": "grep", "description": "d",
                "input_schema": {"type": "object", "properties": {}}}
        t = FakeTransport([
            {"choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "function": {"name": "grep",
                                          "arguments": "{\"pattern\": \"x\"}"}}]},
              "finish_reason": "tool_calls"}]},
            {"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}]},
        ])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("go", tools=[tool], config=OAI_CFG,
                                  tool_executor=lambda n, a: "hit")
        assert out["text"] == "done"
        _, _, body2 = t.requests[1]
        assert body2["messages"][-1] == {"role": "tool", "tool_call_id": "c1",
                                         "content": "hit"}
        # assistant turn (with its tool_calls) is echoed back before the tool msg
        assert body2["messages"][-2]["role"] == "assistant"

    def test_malformed_tool_arguments_degrade(self, monkeypatch):
        t = FakeTransport([{"choices": [{"message": {
            "content": "text anyway",
            "tool_calls": [{"id": "c1", "function": {"name": "grep",
                                                     "arguments": "{broken"}}]},
            "finish_reason": "tool_calls"}]}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        out = llm_client.complete("go", config=OAI_CFG)  # no executor: single turn
        assert out["text"] == "text anyway"
        assert out["tool_calls"] == [{"name": "grep", "input": {}}]

    def test_empty_choices_raises(self, monkeypatch):
        t = FakeTransport([{"choices": []}])
        monkeypatch.setattr(llm_client, "_post_json", t)
        with pytest.raises(llm_client.LLMError):
            llm_client.complete("hi", config=OAI_CFG)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_llm_client.py -v -k OpenAI`
Expected: FAIL with `NameError`/`AttributeError` for `_complete_openai`

- [ ] **Step 3: Implement the openai backend**

Append to `archie/standalone/llm_client.py`:

```python
def _oai_tools(tools):
    return [{"type": "function", "function": {
        "name": t["name"], "description": t.get("description", ""),
        "parameters": t.get("input_schema") or {"type": "object"}}} for t in tools]


def _complete_openai(prompt, *, model, system, tools, tool_choice, max_tokens,
                     timeout, config, tool_executor, max_turns, budget_bytes,
                     max_retries):
    url = config["base_url"] + "/chat/completions"
    headers = {"content-type": "application/json",
               "Authorization": f"Bearer {config['api_key']}"}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    spent = 0
    last_text = ""
    turns = max_turns if tool_executor else 1
    for _ in range(turns):
        body_d = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if tools:
            body_d["tools"] = _oai_tools(tools)
        if tool_choice:
            body_d["tool_choice"] = {"type": "function",
                                     "function": {"name": tool_choice}}
        data = _post_json(url, json.dumps(body_d).encode("utf-8"),
                          headers, timeout, max_retries)
        choices = data.get("choices") or []
        if not choices:
            raise LLMError(f"LLM API malformed response: {str(data)[:300]}")
        msg = choices[0].get("message") or {}
        last_text = msg.get("content") or last_text
        raw_calls = msg.get("tool_calls") or []
        tool_calls = []
        for c in raw_calls:
            fn = c.get("function") or {}
            try:
                parsed = json.loads(fn.get("arguments") or "{}")
                if not isinstance(parsed, dict):
                    parsed = {}
            except ValueError:
                parsed = {}
            tool_calls.append({"name": fn.get("name"), "input": parsed,
                               "_id": c.get("id")})
        public_calls = [{"name": c["name"], "input": c["input"]} for c in tool_calls]
        if not tool_executor or choices[0].get("finish_reason") != "tool_calls":
            return {"text": last_text, "tool_calls": public_calls}
        messages.append({"role": "assistant", "content": msg.get("content"),
                         "tool_calls": raw_calls})
        for c in tool_calls:
            if spent >= budget_bytes:
                out = "denied: tool budget exhausted"
            else:
                try:
                    out = tool_executor(c["name"], c["input"])
                except Exception:
                    out = "denied: tool call failed"
                spent += len(out)
            messages.append({"role": "tool", "tool_call_id": c["_id"],
                             "content": out})
    return {"text": last_text, "tool_calls": []}
```

- [ ] **Step 4: Run all llm_client tests**

Run: `python3 -m pytest tests/test_llm_client.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm): openai-compatible backend (OpenRouter et al.)"
```

---

### Task 4: Wire `agent_cli.py` through `llm_client`

**Files:**
- Modify: `archie/standalone/agent_cli.py` (replace `_run_api` at :51-72, `_run_api_tools` at :153-201, dispatch in `run_verifier` at :260-264; keep `_TOOLS`, `_safe_path`, `_exec_tool` unchanged)
- Test: `tests/test_agent_cli.py` (add cases; file may already exist — check with `ls tests/ | grep agent_cli` and extend or create)

**Interfaces:**
- Consumes: `llm_client.resolve_config`, `llm_client.complete`, `llm_client.LLMError`.
- Produces: unchanged public API — `run_verifier(prompt, project_root, verifier, timeout=90, model="haiku", tools=False) -> str`. Callers (`review_core.py`, `behavioral_review.py`, `invariant_specialist.py`, `universal_specialists.py`) need no changes.

- [ ] **Step 1: Write the failing tests**

In `tests/test_agent_cli.py` (create if absent, mirroring the `sys.path` insert pattern from `tests/test_llm_client.py`):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import agent_cli
import llm_client


def _no_clis(monkeypatch):
    monkeypatch.setattr(agent_cli.shutil, "which", lambda name: None)


class TestRunVerifierApiPath:
    def test_api_path_uses_llm_client(self, monkeypatch, tmp_path):
        _no_clis(monkeypatch)
        seen = {}
        def fake_complete(prompt, **kw):
            seen.update(kw, prompt=prompt)
            return {"text": "verdict", "tool_calls": []}
        monkeypatch.setattr(agent_cli.llm_client, "resolve_config",
                            lambda project_root=None, env=None: {"backend": "openai"})
        monkeypatch.setattr(agent_cli.llm_client, "complete", fake_complete)
        out = agent_cli.run_verifier("p", tmp_path, "claude", model="sonnet")
        assert out == "verdict"
        assert seen["tier"] == "sonnet"
        assert seen["prompt"] == "p"

    def test_tools_flag_passes_executor(self, monkeypatch, tmp_path):
        _no_clis(monkeypatch)
        seen = {}
        monkeypatch.setattr(agent_cli.llm_client, "resolve_config",
                            lambda project_root=None, env=None: {"backend": "openai"})
        monkeypatch.setattr(agent_cli.llm_client, "complete",
                            lambda prompt, **kw: seen.update(kw) or
                            {"text": "t", "tool_calls": []})
        agent_cli.run_verifier("p", tmp_path, "claude", tools=True)
        assert callable(seen["tool_executor"])
        assert seen["tools"] == agent_cli._TOOLS

    def test_no_provider_returns_empty(self, monkeypatch, tmp_path):
        _no_clis(monkeypatch)
        monkeypatch.setattr(agent_cli.llm_client, "resolve_config",
                            lambda project_root=None, env=None: None)
        assert agent_cli.run_verifier("p", tmp_path, "claude") == ""

    def test_llm_error_fails_open(self, monkeypatch, tmp_path):
        _no_clis(monkeypatch)
        def boom(prompt, **kw):
            raise llm_client.LLMError("down")
        monkeypatch.setattr(agent_cli.llm_client, "resolve_config",
                            lambda project_root=None, env=None: {"backend": "openai"})
        monkeypatch.setattr(agent_cli.llm_client, "complete", boom)
        assert agent_cli.run_verifier("p", tmp_path, "claude") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_agent_cli.py -v -k ApiPath`
Expected: FAIL — `agent_cli` has no attribute `llm_client` (module not imported yet)

- [ ] **Step 3: Rewire `agent_cli.py`**

At the top (after the existing `sys.path`-free imports — `agent_cli` lives beside `llm_client`, so a plain import works because pipeline scripts add the directory to `sys.path`; add the same guard used elsewhere):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
import llm_client  # noqa: E402
```

Delete `ANTHROPIC_URL`, `API_MODEL`, `API_MODELS` constants and the bodies of `_run_api` / `_run_api_tools`; replace with:

```python
def _run_api(prompt: str, timeout: int = DEFAULT_TIMEOUT, model: str = "haiku",
             project_root=None) -> str:
    """Direct LLM API call via llm_client — used in CI where no coding-agent
    CLI exists. Returns the text response or '' on any error (fail-open)."""
    try:
        return llm_client.complete(prompt, tier=model, timeout=timeout,
                                   project_root=project_root)["text"]
    except llm_client.LLMError as e:
        print(f"[archie] api call failed ({e})", file=sys.stderr)
        return ""


def _run_api_tools(prompt, project_root, model="haiku",
                   timeout=DEFAULT_TIMEOUT, max_turns=6, budget_bytes=60000) -> str:
    """LLM tool-use loop offering jailed read_file/grep against project_root
    (see _exec_tool). Fail-open: returns '' or last seen text, never raises."""
    try:
        return llm_client.complete(
            prompt, tier=model, timeout=timeout, project_root=project_root,
            tools=_TOOLS, max_turns=max_turns, budget_bytes=budget_bytes,
            tool_executor=lambda name, args: _exec_tool(project_root, name, args),
        )["text"]
    except llm_client.LLMError as e:
        print(f"[archie] api tool loop failed ({e})", file=sys.stderr)
        return ""
```

In `run_verifier`, replace the API branch (`key = os.environ.get("ANTHROPIC_API_KEY") ...`) with:

```python
    if llm_client.resolve_config(project_root) is not None:
        if tools:
            return _run_api_tools(prompt, project_root, model=model, timeout=timeout)
        return _run_api(prompt, timeout, model=model, project_root=project_root)
    return ""
```

Update the `run_verifier` docstring's priority list item 3 to: "Direct LLM API via `llm_client` (OpenRouter / any OpenAI-compatible endpoint / Anthropic — resolved from `.archie/models.json`, `ARCHIE_LLM_*`, or `OPENROUTER_API_KEY`/`ANTHROPIC_API_KEY`) — CI fallback where no coding-agent CLI is installed." Update the module docstring's Anthropic-specific wording likewise.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_agent_cli.py tests/test_llm_client.py -v`
Expected: all PASS. Also run the reviewer-pipeline suites that go through `run_verifier`:
`python3 -m pytest tests/ -v -k "verifier or review or specialist"` — expected: no new failures vs. `git stash && pytest` baseline.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/agent_cli.py tests/test_agent_cli.py
git commit -m "refactor(llm): route agent_cli API fallback through llm_client"
```

---

### Task 5: Wire `intent_review.py::call_anthropic` through `llm_client`

**Files:**
- Modify: `archie/standalone/intent_review.py` (`MODEL`/`ANTHROPIC_URL`/`ANTHROPIC_VERSION` constants at :41-43, `call_anthropic` at :582-621, `_extract_findings` at :624-631)
- Test: `tests/test_intent_review.py` (extend existing — check `ls tests/ | grep intent_review`)

**Interfaces:**
- Consumes: `llm_client.complete`, `llm_client.LLMError`.
- Produces: `call_anthropic(system, user, api_key, max_retries=3) -> list` — **signature unchanged** so `contract_delta.py:168` keeps working. The `api_key` param is retained but only used as a presence gate (config resolution finds the real key); rename in a later cleanup if desired — not now.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_intent_review.py` (follow the file's existing import pattern):

```python
def test_call_anthropic_delegates_to_llm_client(monkeypatch):
    import intent_review
    import llm_client
    seen = {}
    def fake_complete(prompt, **kw):
        seen.update(kw, prompt=prompt)
        return {"text": "", "tool_calls": [
            {"name": "emit_findings", "input": {"findings": [{"id": 1}]}}]}
    monkeypatch.setattr(intent_review.llm_client, "complete", fake_complete)
    out = intent_review.call_anthropic("SYS", "USER", "sk-key", max_retries=2)
    assert out == [{"id": 1}]
    assert seen["prompt"] == "USER"
    assert seen["system"] == "SYS"
    assert seen["tool_choice"] == "emit_findings"
    assert seen["tools"] == [intent_review.EMIT_FINDINGS_TOOL]
    assert seen["max_retries"] == 2
    assert seen["tier"] == "haiku"


def test_call_anthropic_wraps_llmerror(monkeypatch):
    import intent_review
    import llm_client
    def boom(prompt, **kw):
        raise llm_client.LLMError("HTTP 500")
    monkeypatch.setattr(intent_review.llm_client, "complete", boom)
    import pytest
    with pytest.raises(RuntimeError):
        intent_review.call_anthropic("s", "u", "sk-key")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_intent_review.py -v -k call_anthropic`
Expected: FAIL — `intent_review` has no attribute `llm_client`

- [ ] **Step 3: Rewire `intent_review.py`**

Add next to the existing `from _common import ...` import (`sys.path` is already set at :35):

```python
import llm_client  # noqa: E402
```

Replace `call_anthropic` (:582-621) and `_extract_findings` (:624-631) with:

```python
def call_anthropic(system: str, user: str, api_key: str, max_retries: int = 3) -> list:
    """One forced-tool completion returning the raw findings list.

    Name kept for compatibility (contract_delta imports it); routing is now
    provider-agnostic via llm_client (OpenRouter / OpenAI-compatible /
    Anthropic). `api_key` is legacy — the client resolves the real key from
    config/env — but an empty value still means "skip", matching old callers.
    Raises RuntimeError on hard failure.
    """
    try:
        result = llm_client.complete(
            user, system=system, tier="haiku", max_tokens=MAX_TOKENS,
            tools=[EMIT_FINDINGS_TOOL], tool_choice="emit_findings",
            max_retries=max_retries)
    except llm_client.LLMError as e:
        raise RuntimeError(f"LLM API failed: {e}")
    for call in result["tool_calls"]:
        if call["name"] == "emit_findings":
            findings = call["input"].get("findings")
            return findings if isinstance(findings, list) else []
    return []
```

Delete the now-unused constants `MODEL`, `ANTHROPIC_URL`, `ANTHROPIC_VERSION` (:41-43) — first grep the file (and `contract_delta.py`, `delivery_review.py`) for other uses: `grep -n "MODEL\b\|ANTHROPIC_URL\|ANTHROPIC_VERSION" archie/standalone/*.py`. Keep any constant that still has a consumer. Keep `MAX_TOKENS`.

Also update the API-key gate that decides whether review runs (near `intent_review.py:962`, the fail-open skip when `ANTHROPIC_API_KEY` missing): change the condition from "is `ANTHROPIC_API_KEY` env set" to `llm_client.resolve_config() is not None` (grep for `ANTHROPIC_API_KEY` in `intent_review.py` and `delivery_review.py` and update every gate the same way, keeping the skip message wording in sync, e.g. "no LLM provider configured (set OPENROUTER_API_KEY or ANTHROPIC_API_KEY)").

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_intent_review.py tests/test_llm_client.py -v`
and `python3 -m pytest tests/ -v -k "contract_delta or delivery"`
Expected: all PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add archie/standalone/intent_review.py tests/test_intent_review.py
git commit -m "refactor(llm): intent_review findings call via llm_client"
```

---

### Task 6: Registration, workflows, sync, docs

**Files:**
- Modify: `archie/install.py:52` (`_STANDALONE_SCRIPTS` list)
- Modify: `npm-package/bin/archie.mjs:425` (script list)
- Modify: `.github/workflows/archie-check.yml:38` area
- Modify: `archie/assets/workflows/archie-intent-review.yml:32` area (+ synced copy `npm-package/assets/workflows/archie-intent-review.yml`)
- Create: `npm-package/assets/llm_client.py` (copy)
- Modify: `npm-package/assets/agent_cli.py`, `npm-package/assets/intent_review.py` (copies)
- Modify: `CLAUDE.md` (one line in Repository Layout / Rules context noting `llm_client.py`)

- [ ] **Step 1: Register the new script**

In `archie/install.py` `_STANDALONE_SCRIPTS`, add `"llm_client.py",` on the line containing `"agent_cli.py"`. In `npm-package/bin/archie.mjs:425`, add `"llm_client.py"` to the array (next to `"agent_cli.py"`).

- [ ] **Step 2: Extend workflow env blocks**

In each of the three workflow files, directly below the `ANTHROPIC_API_KEY` line, add (matching indentation):

```yaml
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
```

- [ ] **Step 3: Sync asset copies**

```bash
cp archie/standalone/llm_client.py npm-package/assets/llm_client.py
cp archie/standalone/agent_cli.py npm-package/assets/agent_cli.py
cp archie/standalone/intent_review.py npm-package/assets/intent_review.py
cp archie/assets/workflows/archie-intent-review.yml npm-package/assets/workflows/archie-intent-review.yml
```

- [ ] **Step 4: Verify sync + full test suite**

Run: `python3 scripts/verify_sync.py`
Expected: PASS (no missing copies, no dead references)

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 5: Document**

In `CLAUDE.md`, add to the standalone-scripts description (Repository Layout bullet for `archie/standalone/`): mention `llm_client.py` — e.g. append ", llm client (provider-agnostic CI LLM calls: OpenRouter/OpenAI-compatible/Anthropic via `.archie/models.json` + `ARCHIE_LLM_*` env)".

- [ ] **Step 6: Commit**

```bash
git add archie/install.py npm-package/bin/archie.mjs npm-package/assets/ \
  .github/workflows/archie-check.yml archie/assets/workflows/ CLAUDE.md
git commit -m "feat(llm): register llm_client, pass OPENROUTER_API_KEY in CI workflows"
```

---

### Task 7: End-to-end smoke check

**Files:** none created — verification only.

- [ ] **Step 1: Offline smoke of the resolution chain**

```bash
cd /tmp && mkdir -p llmtest/.archie && cd llmtest
cat > .archie/models.json <<'EOF'
{"provider": "openrouter", "models": {"haiku": "google/gemini-2.5-flash"}}
EOF
OPENROUTER_API_KEY=x python3 -c "
import sys; sys.path.insert(0, '/Users/csacsi/DEV/Archie/archie/standalone')
import llm_client
cfg = llm_client.resolve_config('.')
assert cfg['backend'] == 'openai' and cfg['models']['haiku'] == 'google/gemini-2.5-flash', cfg
print('resolution OK:', cfg['base_url'], cfg['models'])
"
```

Expected: `resolution OK: https://openrouter.ai/api/v1 {...}`

- [ ] **Step 2: Live smoke (requires a real key; skip if unavailable)**

With a real `OPENROUTER_API_KEY` exported:

```bash
python3 -c "
import sys; sys.path.insert(0, '/Users/csacsi/DEV/Archie/archie/standalone')
import llm_client
print(llm_client.complete('Reply with the single word: pong')['text'])
"
```

Expected: output containing `pong`. Repeat with only `ANTHROPIC_API_KEY` exported to confirm the legacy path.

- [ ] **Step 3: Push and watch CI**

```bash
git push
```

Open the PR / check run for `archie-check.yml`; confirm the delivery-review comment still appears (fail-open at minimum, live review if secrets are set).
