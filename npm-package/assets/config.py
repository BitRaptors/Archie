#!/usr/bin/env python3
"""Machine-level Archie config at ~/.archie/config.json.

Holds telemetry consent, update-check preferences, and a stable random
installation_id. All Archie installs on this machine share this file — it is
NOT per-project. Each project install ships a copy of this script in
.archie/config.py so it can read or update the central config.

CLI:
  config.py get <key>             — print value (empty if unset)
  config.py set <key> <value>     — validate + write
  config.py list                  — print all key=value
  config.py path                  — print absolute config path
  config.py installation-id       — print id (auto-creates on first call)
  config.py should-prompt         — exit 0 if first-run prompt needed, else 1
  config.py apply-prompt-result <off|anonymous|community>
                                  — set telemetry tier and mark prompted

Programmatic:
  from archie.standalone.config import (
      load_config, save_config, get_installation_id, get_telemetry_tier,
  )

Zero deps beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

VALID_TELEMETRY_TIERS = {"off", "anonymous", "community"}

DEFAULTS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "telemetry": "off",
    "update_check": True,
    "installation_id": "",
    "telemetry_prompted": False,
    "snooze_until_iso": None,
    "snooze_level": 0,
    "snoozed_for_version": None,
}


def config_dir() -> Path:
    return Path.home() / ".archie"


def config_path() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict[str, Any]:
    """Read config from disk, filling in defaults for any missing keys.

    Auto-creates an installation_id (random UUIDv4) on first read and persists
    it. Never raises on a missing or unreadable file — returns defaults instead.
    """
    path = config_path()
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
        except (OSError, json.JSONDecodeError):
            data = {}

    merged = {**DEFAULTS, **data}

    if not merged.get("installation_id"):
        merged["installation_id"] = str(uuid.uuid4())
        save_config(merged)

    return merged


def save_config(cfg: dict[str, Any]) -> None:
    """Atomically write the config (tmp + rename)."""
    config_dir().mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(cfg, indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".config.", dir=str(config_dir()))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(serialized)
            f.write("\n")
        os.replace(tmp_name, config_path())
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def get_installation_id() -> str:
    return load_config()["installation_id"]


def get_telemetry_tier() -> str:
    return load_config().get("telemetry", "off")


def telemetry_enabled() -> bool:
    return get_telemetry_tier() in {"anonymous", "community"}


def update_check_enabled() -> bool:
    return bool(load_config().get("update_check", True))


def _set_value(key: str, raw: str) -> None:
    cfg = load_config()
    if key == "telemetry":
        if raw not in VALID_TELEMETRY_TIERS:
            sys.stderr.write(
                f"telemetry must be one of {sorted(VALID_TELEMETRY_TIERS)}\n"
            )
            sys.exit(2)
        cfg["telemetry"] = raw
    elif key == "update_check":
        if raw.lower() in {"true", "1", "yes", "on"}:
            cfg["update_check"] = True
        elif raw.lower() in {"false", "0", "no", "off"}:
            cfg["update_check"] = False
        else:
            sys.stderr.write("update_check must be true/false\n")
            sys.exit(2)
    elif key == "installation_id":
        sys.stderr.write(
            "installation_id is auto-generated and read-only. "
            "Delete the config file to rotate it.\n"
        )
        sys.exit(2)
    elif key in {"snooze_until_iso", "snooze_level", "snoozed_for_version", "telemetry_prompted"}:
        sys.stderr.write(f"{key} is internal state, not user-settable\n")
        sys.exit(2)
    else:
        sys.stderr.write(f"unknown key: {key}\n")
        sys.exit(2)
    save_config(cfg)


def _format_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _cmd_get(args: list[str]) -> int:
    if len(args) != 1:
        sys.stderr.write("usage: config.py get <key>\n")
        return 2
    cfg = load_config()
    print(_format_value(cfg.get(args[0])))
    return 0


def _cmd_set(args: list[str]) -> int:
    if len(args) != 2:
        sys.stderr.write("usage: config.py set <key> <value>\n")
        return 2
    _set_value(args[0], args[1])
    return 0


def _cmd_list(_args: list[str]) -> int:
    cfg = load_config()
    for key in sorted(cfg.keys()):
        print(f"{key}={_format_value(cfg[key])}")
    return 0


def _cmd_path(_args: list[str]) -> int:
    print(str(config_path()))
    return 0


def _cmd_installation_id(_args: list[str]) -> int:
    print(get_installation_id())
    return 0


def _cmd_should_prompt(_args: list[str]) -> int:
    cfg = load_config()
    return 0 if not cfg.get("telemetry_prompted") else 1


def _cmd_apply_prompt_result(args: list[str]) -> int:
    if len(args) != 1 or args[0] not in VALID_TELEMETRY_TIERS:
        sys.stderr.write(
            f"usage: config.py apply-prompt-result <{('|').join(sorted(VALID_TELEMETRY_TIERS))}>\n"
        )
        return 2
    cfg = load_config()
    cfg["telemetry"] = args[0]
    cfg["telemetry_prompted"] = True
    save_config(cfg)
    return 0


COMMANDS = {
    "get": _cmd_get,
    "set": _cmd_set,
    "list": _cmd_list,
    "path": _cmd_path,
    "installation-id": _cmd_installation_id,
    "should-prompt": _cmd_should_prompt,
    "apply-prompt-result": _cmd_apply_prompt_result,
}


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help", "help"}:
        sys.stdout.write(__doc__ or "")
        return 0
    cmd = argv[1]
    handler = COMMANDS.get(cmd)
    if handler is None:
        sys.stderr.write(f"unknown command: {cmd}\n")
        sys.stderr.write("known: " + ", ".join(sorted(COMMANDS.keys())) + "\n")
        return 2
    return handler(argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
