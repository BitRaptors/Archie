#!/usr/bin/env python3
"""Anonymous, opt-in update check for the Archie npm package.

Hits the public npm registry once per cache TTL (60min when up-to-date,
720min when an upgrade is pending) and prints a single-line marker for the
slash-command preamble to act on. The user can snooze (24h → 48h → 7d
escalating ladder) or disable update checks entirely.

Output contracts (stdout, exactly one line, possibly empty):
  ""                                 — up to date / snoozed / disabled / offline
  "UPGRADE_AVAILABLE old new"        — newer version exists, not snoozed
  "JUST_UPGRADED old new"            — first invocation after an upgrade

CLI:
  update_check.py check                  — the workflow above (default)
  update_check.py snooze                 — bump snooze level for current latest
  update_check.py disable                — turn off update_check entirely
  update_check.py enable                 — re-enable update_check
  update_check.py status                 — print full state as JSON
  update_check.py reset                  — clear cache + snooze
  update_check.py mark-upgraded <ver>    — record that an upgrade just happened

Zero deps beyond Python 3.9+ stdlib. Failures (network, parse errors, etc.)
are silent — never break a slash command.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from archie.standalone.config import config_dir, load_config, save_config
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from config import config_dir, load_config, save_config  # type: ignore[no-redef]

REGISTRY_URL = "https://registry.npmjs.org/@bitraptors/archie/latest"
HTTP_TIMEOUT_S = 5
CACHE_TTL_OK_S = 60 * 60          # 1 hour when up-to-date
CACHE_TTL_PENDING_S = 12 * 60 * 60  # 12 hours when an upgrade is pending

SNOOZE_LADDER_HOURS = [24, 48, 24 * 7]  # capped at the longest entry
JUST_UPGRADED_GRACE_S = 6 * 60 * 60  # show "JUST_UPGRADED" for 6h after install


def _cache_path() -> Path:
    return config_dir() / "update-check.json"


def _just_upgraded_path() -> Path:
    return config_dir() / "just-upgraded.json"


def _version_marker_path() -> Path:
    return config_dir() / "version"


def _read_installed_version() -> str:
    p = _version_marker_path()
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()[:32]
    except OSError:
        return ""


def _semver_tuple(v: str) -> tuple[int, ...]:
    """Coarse semver compare. Non-numeric suffixes are ignored.

    Returns (0, 0, 0) for unparseable input so it sorts behind any real version.
    """
    parts = v.split(".")
    out: list[int] = []
    for part in parts[:3]:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def _newer(a: str, b: str) -> bool:
    """True if a > b under coarse semver."""
    return _semver_tuple(a) > _semver_tuple(b)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _read_cache() -> dict[str, Any]:
    if not _cache_path().exists():
        return {}
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _cache_fresh(cache: dict[str, Any], pending: bool) -> bool:
    fetched_at = cache.get("fetched_at")
    if not isinstance(fetched_at, (int, float)):
        return False
    ttl = CACHE_TTL_PENDING_S if pending else CACHE_TTL_OK_S
    return (time.time() - fetched_at) < ttl


def _fetch_latest_from_registry() -> str | None:
    try:
        req = urllib.request.Request(REGISTRY_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        version = data.get("version") if isinstance(data, dict) else None
        if isinstance(version, str) and version[:1].isdigit():
            return version[:32]
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    return None


def _snooze_active(cfg: dict[str, Any], latest: str) -> bool:
    """True if the user has snoozed and the snoozed-for-version is still latest."""
    snooze_until = cfg.get("snooze_until_iso")
    snoozed_for = cfg.get("snoozed_for_version")
    if not snooze_until or not snoozed_for:
        return False
    if snoozed_for != latest:
        return False  # new release invalidates the snooze
    try:
        deadline = datetime.fromisoformat(str(snooze_until).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return datetime.now(timezone.utc) < deadline


def _maybe_print_just_upgraded(installed: str) -> str | None:
    p = _just_upgraded_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    old = str(data.get("from") or "")
    new = str(data.get("to") or "")
    when = data.get("at")
    try:
        if isinstance(when, (int, float)) and time.time() - when > JUST_UPGRADED_GRACE_S:
            p.unlink()
            return None
    except OSError:
        pass
    if not old or not new:
        return None
    # Only emit while installed actually matches the upgrade target.
    if installed and installed != new:
        return None
    try:
        p.unlink()
    except OSError:
        pass
    return f"JUST_UPGRADED {old} {new}"


def check() -> str:
    """Return the marker line (possibly empty). Never raises."""
    cfg = load_config()
    if not cfg.get("update_check", True):
        return ""

    installed = _read_installed_version()

    # JUST_UPGRADED takes priority — it's a one-off acknowledgement.
    just_upgraded = _maybe_print_just_upgraded(installed)
    if just_upgraded:
        return just_upgraded

    cache = _read_cache()
    pending = bool(cache.get("latest")) and installed and _newer(str(cache.get("latest")), installed)
    if not _cache_fresh(cache, pending):
        latest = _fetch_latest_from_registry()
        if latest:
            cache = {"latest": latest, "fetched_at": time.time()}
            _write_atomic(_cache_path(), json.dumps(cache))
        else:
            # Network failure: keep stale cache if any, otherwise silent.
            if not cache:
                return ""

    latest = str(cache.get("latest") or "")
    if not latest:
        return ""
    if not installed:
        # We don't know what's installed — can't compare. Silent.
        return ""
    if not _newer(latest, installed):
        return ""
    if _snooze_active(cfg, latest):
        return ""
    return f"UPGRADE_AVAILABLE {installed} {latest}"


def snooze() -> dict[str, Any]:
    """Bump snooze level for the latest cached version."""
    cfg = load_config()
    cache = _read_cache()
    latest = str(cache.get("latest") or "")
    if not latest:
        return {"snoozed": False, "reason": "no_latest_cached"}
    level = int(cfg.get("snooze_level") or 0)
    new_level = min(level + 1, len(SNOOZE_LADDER_HOURS))  # 1-indexed (1, 2, 3)
    hours = SNOOZE_LADDER_HOURS[min(new_level - 1, len(SNOOZE_LADDER_HOURS) - 1)]
    deadline = datetime.now(timezone.utc) + timedelta(hours=hours)
    cfg["snooze_level"] = new_level
    cfg["snooze_until_iso"] = deadline.strftime("%Y-%m-%dT%H:%M:%SZ")
    cfg["snoozed_for_version"] = latest
    save_config(cfg)
    return {
        "snoozed": True,
        "level": new_level,
        "until": cfg["snooze_until_iso"],
        "snoozed_for_version": latest,
        "hours": hours,
    }


def reset_snooze() -> None:
    cfg = load_config()
    cfg["snooze_level"] = 0
    cfg["snooze_until_iso"] = None
    cfg["snoozed_for_version"] = None
    save_config(cfg)


def disable() -> None:
    cfg = load_config()
    cfg["update_check"] = False
    save_config(cfg)


def enable() -> None:
    cfg = load_config()
    cfg["update_check"] = True
    save_config(cfg)


def status() -> dict[str, Any]:
    cfg = load_config()
    cache = _read_cache()
    return {
        "update_check": bool(cfg.get("update_check", True)),
        "installed": _read_installed_version(),
        "latest": cache.get("latest"),
        "cache_fetched_at": cache.get("fetched_at"),
        "snooze_level": cfg.get("snooze_level"),
        "snooze_until_iso": cfg.get("snooze_until_iso"),
        "snoozed_for_version": cfg.get("snoozed_for_version"),
    }


def reset() -> None:
    if _cache_path().exists():
        try:
            _cache_path().unlink()
        except OSError:
            pass
    reset_snooze()


def mark_upgraded(new_version: str) -> None:
    """Record that an upgrade just landed (called by the installer)."""
    old = _read_installed_version()
    payload = {"from": old, "to": new_version, "at": time.time()}
    _write_atomic(_just_upgraded_path(), json.dumps(payload))
    reset_snooze()


def _usage() -> int:
    sys.stderr.write(
        "Usage:\n"
        "  update_check.py check\n"
        "  update_check.py snooze\n"
        "  update_check.py disable\n"
        "  update_check.py enable\n"
        "  update_check.py status\n"
        "  update_check.py reset\n"
        "  update_check.py mark-upgraded <version>\n"
    )
    return 2


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) >= 2 else "check"
    if cmd == "check":
        line = check()
        if line:
            print(line)
        return 0
    if cmd == "snooze":
        print(json.dumps(snooze()))
        return 0
    if cmd == "disable":
        disable()
        print("update_check=false")
        return 0
    if cmd == "enable":
        enable()
        print("update_check=true")
        return 0
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "reset":
        reset()
        print("reset")
        return 0
    if cmd == "mark-upgraded":
        if len(argv) < 3:
            return _usage()
        mark_upgraded(argv[2])
        return 0
    return _usage()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
