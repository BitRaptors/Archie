#!/usr/bin/env python3
"""Archie share — set up an enterprise bucket profile.

Writes ~/.archie/share-profile.json with the credentials + bucket info
enterprise-creds mode needs. File is chmod 600 (owner read/write only).

Run:
    python3 share_setup.py \\
        --bucket acme-archie-shares \\
        --region us-east-1 \\
        --access-key-id AKIA... \\
        --secret-access-key ... \\
        [--key-prefix archie-shares/] \\
        [--presign-expires-seconds 604800]

Security note: credentials appear in the command line, which shell history
may record. For the highest security, create the profile file manually
instead (see docs/enterprise-share-setup.md).

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

PROFILE_PATH = Path.home() / ".archie" / "share-profile.json"


def write_profile(profile: dict, path: Path = PROFILE_PATH) -> Path:
    """Write profile JSON to `path`, chmod 600. Returns the written path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2) + "\n")
    # chmod 600 — owner read/write only. On Windows this is a no-op; Archie
    # users on Windows get the POSIX-unaware behavior (which is fine since
    # the file permissions model is different there anyway).
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up the Archie enterprise share profile.",
    )
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--region", required=True, help="AWS region (e.g. us-east-1)")
    parser.add_argument("--access-key-id", required=True, help="IAM access key ID")
    parser.add_argument("--secret-access-key", required=True, help="IAM secret access key")
    parser.add_argument(
        "--key-prefix",
        default="archie-shares/",
        help="Prefix under which Archie writes share objects (default: archie-shares/)",
    )
    parser.add_argument(
        "--presign-expires-seconds",
        type=int,
        default=7 * 24 * 60 * 60,
        help="How long the presigned GET URL is valid (max 604800 = 7 days on AWS)",
    )
    return parser.parse_args(argv)


def main():
    args = _parse_args(sys.argv[1:])
    profile = {
        "bucket": args.bucket,
        "region": args.region,
        "access_key_id": args.access_key_id,
        "secret_access_key": args.secret_access_key,
        "key_prefix": args.key_prefix,
        "presign_expires_seconds": args.presign_expires_seconds,
    }
    path = write_profile(profile)
    print(f"Wrote {path} (chmod 600)", file=sys.stderr)
    print(f"Enterprise share profile ready. Run /archie-share and pick 'Enterprise (stored credentials)'.", file=sys.stderr)


if __name__ == "__main__":
    main()
