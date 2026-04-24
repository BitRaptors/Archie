"""Tests for the enterprise share setup wizard (share_setup.py).

The wizard is invoked with explicit flags (no interactive input, since Claude
Code doesn't support stdin prompting). It writes ~/.archie/share-profile.json
with chmod 600.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
from share_setup import _parse_args, write_profile  # noqa: E402


def test_parse_args_all_required_fields():
    args = _parse_args([
        "--bucket", "acme-archie-shares",
        "--region", "us-east-1",
        "--access-key-id", "AKIAEXAMPLE",
        "--secret-access-key", "secretexample",
    ])
    assert args.bucket == "acme-archie-shares"
    assert args.region == "us-east-1"
    assert args.access_key_id == "AKIAEXAMPLE"
    assert args.secret_access_key == "secretexample"
    # defaults
    assert args.key_prefix == "archie-shares/"
    assert args.presign_expires_seconds == 604800  # 7 days


def test_parse_args_rejects_missing_required():
    with pytest.raises(SystemExit):
        _parse_args(["--bucket", "acme"])


def test_parse_args_accepts_optional_overrides():
    args = _parse_args([
        "--bucket", "b",
        "--region", "r",
        "--access-key-id", "k",
        "--secret-access-key", "s",
        "--key-prefix", "custom-prefix/",
        "--presign-expires-seconds", "3600",
    ])
    assert args.key_prefix == "custom-prefix/"
    assert args.presign_expires_seconds == 3600


def test_write_profile_writes_json(tmp_path):
    target = tmp_path / ".archie" / "share-profile.json"
    profile = {
        "bucket": "acme",
        "region": "us-east-1",
        "access_key_id": "AKIA",
        "secret_access_key": "secret",
    }
    path = write_profile(profile, path=target)
    assert path == target
    assert target.exists()
    parsed = json.loads(target.read_text())
    assert parsed == profile


def test_write_profile_creates_parent_directory(tmp_path):
    """Parent dir gets created automatically."""
    target = tmp_path / "deep" / "nested" / "share-profile.json"
    write_profile({"bucket": "b", "region": "r", "access_key_id": "k", "secret_access_key": "s"}, path=target)
    assert target.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX chmod not meaningful on Windows")
def test_write_profile_sets_chmod_600(tmp_path):
    """The profile file contains secrets — perms must restrict to owner only."""
    target = tmp_path / "share-profile.json"
    write_profile({"bucket": "b", "region": "r", "access_key_id": "k", "secret_access_key": "s"}, path=target)
    mode = stat.S_IMODE(target.stat().st_mode)
    # 0o600 = owner read+write, nothing for group or other
    assert mode == 0o600, f"Expected 0o600 but got {oct(mode)}"


def test_write_profile_overwrites_existing(tmp_path):
    """Re-running setup replaces the file, doesn't append."""
    target = tmp_path / "share-profile.json"
    write_profile({"bucket": "old", "region": "r", "access_key_id": "k", "secret_access_key": "s"}, path=target)
    write_profile({"bucket": "new", "region": "r", "access_key_id": "k", "secret_access_key": "s"}, path=target)
    parsed = json.loads(target.read_text())
    assert parsed["bucket"] == "new"
