"""Tests for scanner.detect_monorepo_type."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
from scanner import detect_monorepo_type  # noqa: E402


def write(path: Path, content: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_none_for_plain_single_project(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "x", "version": "1.0.0"}))
    assert detect_monorepo_type(tmp_path) == "none"


def test_empty_dir_is_none(tmp_path):
    assert detect_monorepo_type(tmp_path) == "none"


def test_bun_workspaces(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "bun.lock", "")
    assert detect_monorepo_type(tmp_path) == "bun-workspaces"


def test_bun_workspaces_via_bunfig(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "bunfig.toml", "")
    assert detect_monorepo_type(tmp_path) == "bun-workspaces"


def test_npm_workspaces_when_no_bun_signals(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    assert detect_monorepo_type(tmp_path) == "npm-workspaces"


def test_pnpm_detected(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r"}))
    write(tmp_path / "pnpm-workspace.yaml", "packages:\n  - 'apps/*'")
    assert detect_monorepo_type(tmp_path) == "pnpm"


def test_turborepo_wins_over_underlying(tmp_path):
    # turborepo layered on top of pnpm should report turborepo
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "pnpm-workspace.yaml", "packages: []")
    write(tmp_path / "turbo.json", "{}")
    assert detect_monorepo_type(tmp_path) == "turborepo"


def test_nx_detected(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "nx.json", "{}")
    assert detect_monorepo_type(tmp_path) == "nx"


def test_lerna_detected(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "lerna.json", "{}")
    assert detect_monorepo_type(tmp_path) == "lerna"


def test_cargo_workspace(tmp_path):
    write(tmp_path / "Cargo.toml", "[workspace]\nmembers = ['foo']\n")
    assert detect_monorepo_type(tmp_path) == "cargo"


def test_cargo_non_workspace(tmp_path):
    write(tmp_path / "Cargo.toml", "[package]\nname = 'x'\n")
    assert detect_monorepo_type(tmp_path) == "none"


def test_gradle_multiproject(tmp_path):
    write(tmp_path / "settings.gradle.kts", "include(':app', ':lib')")
    assert detect_monorepo_type(tmp_path) == "gradle"


def test_gradle_single_module(tmp_path):
    write(tmp_path / "settings.gradle", "rootProject.name = 'x'")
    assert detect_monorepo_type(tmp_path) == "none"


def test_priority_turbo_over_bun(tmp_path):
    write(tmp_path / "package.json", json.dumps({"name": "r", "workspaces": ["apps/*"]}))
    write(tmp_path / "bun.lock", "")
    write(tmp_path / "turbo.json", "{}")
    assert detect_monorepo_type(tmp_path) == "turborepo"
