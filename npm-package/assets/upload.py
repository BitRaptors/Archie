#!/usr/bin/env python3
"""Archie share — upload blueprint bundle for sharing.

Run: python3 upload.py /path/to/project
Reads from .archie/: blueprint.json (required), health.json, scan.json, rules.json,
                     proposed_rules.json, scan_report.md (all optional).
Prints: shareable URL on success, warning on failure.

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

UPLOAD_URL = os.environ.get(
    "ARCHIE_UPLOAD_URL",
    "https://chlmyhkjnirrcrjdsvrc.supabase.co/functions/v1/upload",
)
PROD_VIEWER_URL = "https://archie-viewer.vercel.app"
ENTERPRISE_TOKEN = "ext"

SHARE_PROFILE_PATH = Path.home() / ".archie" / "share-profile.json"
DEFAULT_KEY_PREFIX = "archie-shares/"
DEFAULT_PRESIGN_EXPIRES_SECONDS = 7 * 24 * 60 * 60  # 7 days (AWS IAM-user max)


def _detect_viewer_url() -> str:
    """Resolve the viewer host. Precedence:
    1. ARCHIE_VIEWER_URL env var (explicit override)
    2. Production default
    """
    override = os.environ.get("ARCHIE_VIEWER_URL")
    if override:
        return override.rstrip("/")

    return PROD_VIEWER_URL


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        return path.read_text()
    except OSError:
        return None


TOP_N_HIGH_CC = 20
TOP_N_DUPLICATES = 10


def _strip_scan_meta(scan: dict) -> dict:
    return {
        "total_files": len(scan.get("file_tree", [])),
        "frameworks": [
            {"name": s.get("name", ""), "version": s.get("version", "")}
            for s in (scan.get("framework_signals") or [])
        ],
        "frontend_ratio": scan.get("frontend_ratio", 0),
        "subprojects": [
            {"name": s.get("name", ""), "type": s.get("type", "")}
            for s in (scan.get("subprojects") or [])
        ],
        "dependency_count": len(scan.get("dependencies") or []),
    }


def _strip_health(health: dict) -> dict:
    functions = health.get("functions") or []
    # Rank by mass (cc*sqrt(sloc)) when present; fall back to cc for older
    # health.json that predates the mass field.
    top_cc = sorted(
        functions,
        key=lambda f: (f.get("mass") or f.get("cc", 0)),
        reverse=True,
    )[:TOP_N_HIGH_CC]

    duplicates = health.get("duplicates") or []
    top_dupes = sorted(duplicates, key=lambda d: d.get("lines", 0), reverse=True)[:TOP_N_DUPLICATES]

    return {
        "erosion": health.get("erosion"),
        "gini": health.get("gini"),
        "top20_share": health.get("top20_share"),
        "verbosity": health.get("verbosity"),
        "total_functions": health.get("total_functions"),
        "high_cc_functions": health.get("high_cc_functions"),
        "total_loc": health.get("total_loc"),
        "duplicate_lines": health.get("duplicate_lines"),
        "cc_distribution": health.get("cc_distribution"),
        "mass": health.get("mass"),
        "top_high_cc": [
            {
                "path": f.get("path"),
                "name": f.get("name"),
                "cc": f.get("cc"),
                "sloc": f.get("sloc"),
                "line": f.get("line"),
                "mass": f.get("mass"),
            }
            for f in top_cc
        ],
        "top_duplicates": [
            {
                "lines": d.get("lines"),
                "locations": d.get("locations") or d.get("files") or [],
            }
            for d in top_dupes
        ],
    }


def build_bundle(project_root: Path) -> dict:
    archie_dir = project_root / ".archie"

    blueprint = _read_json(archie_dir / "blueprint.json")
    if blueprint is None:
        print("Error: .archie/blueprint.json not found. Run /archie-scan first.", file=sys.stderr)
        sys.exit(1)

    bundle: dict = {"blueprint": blueprint}

    health = _read_json(archie_dir / "health.json")
    if health:
        bundle["health"] = _strip_health(health)
    else:
        history = _read_json(archie_dir / "health_history.json")
        if isinstance(history, list) and history:
            latest = history[-1]
            bundle["health"] = {
                "erosion": latest.get("erosion"),
                "gini": latest.get("gini"),
                "top20_share": latest.get("top20_share"),
                "verbosity": latest.get("verbosity"),
                "total_loc": latest.get("total_loc"),
                "total_functions": None,
                "high_cc_functions": None,
                "duplicate_lines": None,
                "top_high_cc": [],
                "top_duplicates": [],
                "_source": "history_fallback",
            }

    scan = _read_json(archie_dir / "scan.json")
    if scan:
        bundle["scan_meta"] = _strip_scan_meta(scan)

    rules = _read_json(archie_dir / "rules.json")
    if rules:
        bundle["rules_adopted"] = rules

    proposed = _read_json(archie_dir / "proposed_rules.json")
    if proposed:
        bundle["rules_proposed"] = proposed

    scan_report = _read_text(archie_dir / "scan_report.md")
    if scan_report:
        bundle["scan_report"] = scan_report

    # Structured findings from the shared accumulating store. Gives the share
    # viewer the 4-field shape (problem_statement/evidence/root_cause/
    # fix_direction) — far richer than the title/description regex-scraped
    # from scan_report.md. Old bundles without this still fall back to the
    # markdown-parsed findings.
    findings_store = _read_json(archie_dir / "findings.json")
    if isinstance(findings_store, dict) and isinstance(findings_store.get("findings"), list):
        bundle["findings"] = findings_store["findings"]
    elif isinstance(findings_store, list):
        bundle["findings"] = findings_store

    # Structured semantic duplications from Agent C — "near-twin" functions,
    # reimplementations, same logic under different names. Distinct from
    # health.json's textual duplicates (which are line-identical copy-paste).
    sem = _read_json(archie_dir / "semantic_duplications.json")
    if sem and isinstance(sem.get("duplications"), list):
        bundle["semantic_duplications"] = sem["duplications"]

    return bundle


def upload(bundle: dict) -> str | None:
    data = json.dumps(bundle).encode("utf-8")

    req = urllib.request.Request(
        UPLOAD_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            token = result.get("token")
            if not token:
                return None
            return f"{_detect_viewer_url()}/r/{token}"
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Upload failed (HTTP {e.code}): {body}", file=sys.stderr)
        return None
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Enterprise mode — BYO customer bucket, zero BitRaptors storage
#
# The viewer loads the bundle directly from the customer's bucket by reading
# the GET URL from the share URL's fragment (#...). URL fragments are a
# browser-only construct — they are never transmitted to any server, including
# Vercel. So BitRaptors' only role is serving static JS from archie-viewer.
# No upload to our infra, no pointer stored, no metadata captured.
# ---------------------------------------------------------------------------


def _build_enterprise_bundle(bundle: dict) -> bytes:
    """Wrap the bundle in the same envelope the viewer expects for Supabase
    shares: {"bundle": {...}, "created_at": "<ISO8601>"}.

    The viewer's fetchReport() returns a ReportResponse of the same shape, so
    enterprise + default modes render identically once the blob is fetched.

    `created_at` is the scan timestamp (when the blueprint was produced), not
    the upload time, so the viewer shows a stable date across re-shares of the
    same blueprint. Falls back to "now" only when the blueprint lacks meta.
    """
    blueprint = bundle.get("blueprint") or {}
    meta = blueprint.get("meta") or {}
    created_at = (
        meta.get("scanned_at")
        or meta.get("last_scan")
        or datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    envelope = {
        "bundle": bundle,
        "created_at": created_at,
    }
    return json.dumps(envelope).encode("utf-8")


def _build_enterprise_share_url(get_url: str) -> str:
    """Pack the GET URL into a base64url-encoded fragment on the viewer URL.

    Fragment never crosses the network — viewer JS reads it client-side and
    fetches the bundle directly from the customer bucket.
    """
    encoded = (
        base64.urlsafe_b64encode(get_url.encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    return f"{_detect_viewer_url()}/r/{ENTERPRISE_TOKEN}#{encoded}"


def _enterprise_put(put_url: str, body: bytes, content_type: str = "application/json") -> bool:
    """PUT body to a presigned URL. Returns True on 2xx, False otherwise."""
    req = urllib.request.Request(
        put_url,
        data=body,
        headers={"Content-Type": content_type},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        print(f"Upload failed (HTTP {e.code}): {body_err}", file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError) as e:
        print(f"Upload failed: {e}", file=sys.stderr)
        return False


def enterprise_upload_paste(bundle: dict, put_url: str, get_url: str) -> str | None:
    """Mode 2B — upload bundle via a presigned PUT URL, return the viewer URL.

    No credentials touch Archie. The customer's InfoSec minted both URLs.
    """
    body = _build_enterprise_bundle(bundle)
    if not _enterprise_put(put_url, body):
        return None
    return _build_enterprise_share_url(get_url)


# ---------------------------------------------------------------------------
# AWS Signature Version 4 (S3) — pure stdlib
# Supports two surfaces the enterprise-creds flow needs:
#   1. Signed PUT (header-based Authorization) for uploading the bundle.
#   2. Presigned GET (query-string auth) whose URL is packed into the share
#      URL's fragment so the browser can fetch the bundle directly.
# No boto3 / no third-party deps. ~120 lines total.
# ---------------------------------------------------------------------------


def _sigv4_derive_key(secret: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = hmac.new(
        ("AWS4" + secret).encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    k_region = hmac.new(k_date, region.encode("utf-8"), hashlib.sha256).digest()
    k_service = hmac.new(k_region, service.encode("utf-8"), hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
    return k_signing


def _sigv4_sign_put(
    host: str,
    region: str,
    object_key: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    content_type: str = "application/json",
    now: datetime.datetime | None = None,
) -> tuple[str, dict]:
    """Sign a PUT request with sigv4 (header-based Authorization).

    Returns (url, headers). The caller passes both to urllib.request.
    """
    service = "s3"
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_uri = "/" + urllib.parse.quote(object_key, safe="/")
    canonical_querystring = ""
    payload_hash = hashlib.sha256(body).hexdigest()

    canonical_headers = (
        f"content-type:{content_type}\n"
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"

    canonical_request = (
        "PUT\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _sigv4_derive_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 "
        f"Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, "
        f"Signature={signature}"
    )

    url = f"https://{host}{canonical_uri}"
    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-Amz-Content-Sha256": payload_hash,
        "X-Amz-Date": amz_date,
    }
    return url, headers


def _sigv4_presign_get(
    host: str,
    region: str,
    object_key: str,
    access_key: str,
    secret_key: str,
    expires_in: int = DEFAULT_PRESIGN_EXPIRES_SECONDS,
    now: datetime.datetime | None = None,
) -> str:
    """Return a sigv4 presigned GET URL (query-string auth)."""
    service = "s3"
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"

    canonical_uri = "/" + urllib.parse.quote(object_key, safe="/")

    # Build canonical query string: sorted, URL-encoded values.
    # Keys are already safe (all ASCII, no special chars).
    qs_pairs = [
        ("X-Amz-Algorithm", "AWS4-HMAC-SHA256"),
        ("X-Amz-Credential", f"{access_key}/{credential_scope}"),
        ("X-Amz-Date", amz_date),
        ("X-Amz-Expires", str(expires_in)),
        ("X-Amz-SignedHeaders", "host"),
    ]
    encoded = [(k, urllib.parse.quote(v, safe="")) for k, v in qs_pairs]
    canonical_querystring = "&".join(f"{k}={v}" for k, v in sorted(encoded))

    canonical_headers = f"host:{host}\n"
    signed_headers = "host"
    payload_hash = "UNSIGNED-PAYLOAD"

    canonical_request = (
        "GET\n"
        f"{canonical_uri}\n"
        f"{canonical_querystring}\n"
        f"{canonical_headers}\n"
        f"{signed_headers}\n"
        f"{payload_hash}"
    )

    string_to_sign = (
        "AWS4-HMAC-SHA256\n"
        f"{amz_date}\n"
        f"{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = _sigv4_derive_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return f"https://{host}{canonical_uri}?{canonical_querystring}&X-Amz-Signature={signature}"


# ---------------------------------------------------------------------------
# Mode 2A — stored credentials + sigv4 upload
# ---------------------------------------------------------------------------


def _read_share_profile() -> dict | None:
    """Read ~/.archie/share-profile.json if it exists. Returns None if missing
    or malformed. Emits a diagnostic on the latter."""
    if not SHARE_PROFILE_PATH.exists():
        return None
    try:
        profile = json.loads(SHARE_PROFILE_PATH.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: {SHARE_PROFILE_PATH} unreadable ({e}). Skipping enterprise-creds mode.", file=sys.stderr)
        return None
    required = ("bucket", "region", "access_key_id", "secret_access_key")
    missing = [k for k in required if not profile.get(k)]
    if missing:
        print(f"Warning: {SHARE_PROFILE_PATH} missing keys: {missing}. Run /archie-share setup.", file=sys.stderr)
        return None
    return profile


def _sigv4_put_request(
    host: str,
    region: str,
    object_key: str,
    body: bytes,
    access_key: str,
    secret_key: str,
    content_type: str = "application/json",
    now: datetime.datetime | None = None,
) -> bool:
    """Execute a sigv4-signed PUT. Returns True on 2xx, False on error."""
    url, headers = _sigv4_sign_put(
        host=host,
        region=region,
        object_key=object_key,
        body=body,
        access_key=access_key,
        secret_key=secret_key,
        content_type=content_type,
        now=now,
    )
    req = urllib.request.Request(url, data=body, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")
        print(f"S3 PUT failed (HTTP {e.code}): {body_err}", file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError) as e:
        print(f"S3 PUT failed: {e}", file=sys.stderr)
        return False


def enterprise_upload_creds(bundle: dict, profile: dict) -> str | None:
    """Mode 2A — upload to customer bucket using stored credentials, return viewer URL.

    Uses sigv4 for the PUT and generates a presigned GET URL (packed into the
    share URL's fragment). No credentials touch BitRaptors.
    """
    bucket = profile["bucket"]
    region = profile["region"]
    access_key = profile["access_key_id"]
    secret_key = profile["secret_access_key"]
    key_prefix = profile.get("key_prefix") or DEFAULT_KEY_PREFIX
    expires = int(profile.get("presign_expires_seconds") or DEFAULT_PRESIGN_EXPIRES_SECONDS)

    # Normalize prefix: no leading slash, exactly one trailing slash. Catches
    # both "shares" (missing separator → sharesUUID.json) and "/shares/"
    # (leading slash breaks S3 keys).
    normalized_prefix = key_prefix.strip("/")
    if normalized_prefix:
        normalized_prefix += "/"
    object_key = f"{normalized_prefix}{uuid.uuid4()}.json"
    host = f"{bucket}.s3.{region}.amazonaws.com"
    body = _build_enterprise_bundle(bundle)

    if not _sigv4_put_request(
        host=host,
        region=region,
        object_key=object_key,
        body=body,
        access_key=access_key,
        secret_key=secret_key,
    ):
        return None

    get_url = _sigv4_presign_get(
        host=host,
        region=region,
        object_key=object_key,
        access_key=access_key,
        secret_key=secret_key,
        expires_in=expires,
    )
    return _build_enterprise_share_url(get_url)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archie share — upload blueprint bundle for sharing.",
    )
    parser.add_argument("project_root", help="Path to the Archie project root")
    parser.add_argument(
        "--mode",
        choices=["default", "enterprise-paste", "enterprise-creds"],
        default="default",
        help="Upload target. 'default' uses the BitRaptors Supabase share "
        "(existing behavior). 'enterprise-paste' uploads to a customer bucket "
        "via a presigned PUT URL (requires --put-url and --get-url). "
        "'enterprise-creds' uses credentials from ~/.archie/share-profile.json "
        "(run share_setup.py first).",
    )
    parser.add_argument(
        "--put-url",
        help="Presigned PUT URL for enterprise-paste mode. Archie uploads the "
        "bundle to this URL via HTTP PUT.",
    )
    parser.add_argument(
        "--get-url",
        help="GET URL for enterprise-paste mode. Viewer fetches the bundle "
        "directly from this URL. Packed into the share URL's fragment.",
    )
    return parser.parse_args(argv)


def main():
    args = _parse_args(sys.argv[1:])

    project_root = Path(args.project_root).resolve()
    bundle = build_bundle(project_root)

    if args.mode == "default":
        print("Uploading blueprint to BitRaptors share...", file=sys.stderr)
        url = upload(bundle)
    elif args.mode == "enterprise-paste":
        if not args.put_url or not args.get_url:
            print(
                "Error: enterprise-paste mode requires both --put-url and --get-url.",
                file=sys.stderr,
            )
            sys.exit(2)
        print("Uploading blueprint to customer bucket (enterprise-paste)...", file=sys.stderr)
        url = enterprise_upload_paste(bundle, args.put_url, args.get_url)
    elif args.mode == "enterprise-creds":
        profile = _read_share_profile()
        if not profile:
            print(
                f"Error: enterprise-creds mode requires a valid profile at {SHARE_PROFILE_PATH}. "
                "Run share_setup.py to create it.",
                file=sys.stderr,
            )
            sys.exit(2)
        print(
            f"Uploading blueprint to s3://{profile['bucket']}/ (enterprise-creds)...",
            file=sys.stderr,
        )
        url = enterprise_upload_creds(bundle, profile)
    else:
        print(f"Unknown mode: {args.mode}", file=sys.stderr)
        sys.exit(1)

    if url:
        print(f"\nShareable URL: {url}", file=sys.stderr)
        print(url)
    else:
        print(
            "\nUpload failed. Your blueprint is still at .archie/blueprint.json",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
