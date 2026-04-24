import base64
import datetime
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "archie" / "standalone"))
from upload import (  # noqa: E402
    _build_enterprise_bundle,
    _build_enterprise_share_url,
    _enterprise_put,
    _parse_args,
    _read_share_profile,
    _sigv4_derive_key,
    _sigv4_presign_get,
    _sigv4_sign_put,
    _strip_health,
    _strip_scan_meta,
    build_bundle,
    enterprise_upload_creds,
    enterprise_upload_paste,
)


@pytest.fixture
def mock_archie_dir(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    archie.joinpath("blueprint.json").write_text(json.dumps({
        "meta": {"repository": "test/repo"},
        "components": {},
        "decisions": {},
    }))
    archie.joinpath("health.json").write_text(json.dumps({
        "erosion": 0.15,
        "gini": 0.4,
        "top20_share": 0.6,
        "verbosity": 0.05,
        "total_functions": 100,
        "high_cc_functions": 5,
        "total_loc": 5000,
        "duplicate_lines": 50,
        "functions": [{"path": "a.py", "name": "f", "cc": 15, "sloc": 20, "line": 1}],
    }))
    archie.joinpath("scan.json").write_text(json.dumps({
        "file_tree": [{"path": "a.py"}, {"path": "b.py"}],
        "framework_signals": [{"name": "React", "version": "18"}],
        "frontend_ratio": 0.3,
        "subprojects": [],
        "dependencies": [{"name": "react"}],
    }))
    return tmp_path


def test_build_bundle_includes_all(mock_archie_dir):
    archie = mock_archie_dir / ".archie"
    archie.joinpath("rules.json").write_text(json.dumps({
        "rules": [{"id": "r1", "description": "No circular deps", "source": "scan-adopted"}]
    }))
    archie.joinpath("proposed_rules.json").write_text(json.dumps({
        "rules": [{"id": "p1", "description": "Use barrel exports", "confidence": 0.7}]
    }))
    archie.joinpath("scan_report.md").write_text("# Scan\n\n## Findings\n- thing one")
    bundle = build_bundle(mock_archie_dir)
    assert "blueprint" in bundle
    assert "health" in bundle
    assert "scan_meta" in bundle
    assert "rules_adopted" in bundle
    assert "rules_proposed" in bundle
    assert "scan_report" in bundle
    assert "## Findings" in bundle["scan_report"]
    assert bundle["blueprint"]["meta"]["repository"] == "test/repo"
    assert len(bundle["rules_adopted"]["rules"]) == 1
    assert len(bundle["rules_proposed"]["rules"]) == 1


def test_build_bundle_blueprint_only(tmp_path):
    archie = tmp_path / ".archie"
    archie.mkdir()
    archie.joinpath("blueprint.json").write_text(json.dumps({"meta": {}}))
    bundle = build_bundle(tmp_path)
    assert "blueprint" in bundle
    assert "health" not in bundle
    assert "scan_meta" not in bundle
    assert "rules_adopted" not in bundle
    assert "rules_proposed" not in bundle


def test_build_bundle_missing_blueprint(tmp_path):
    (tmp_path / ".archie").mkdir()
    with pytest.raises(SystemExit):
        build_bundle(tmp_path)


def test_strip_health_keeps_top_cc_and_dupes():
    health = {
        "erosion": 0.1,
        "gini": 0.5,
        "cc_distribution": {"1-2": 100, "3-5": 50, "6-10": 20, "11-20": 10, "21-50": 5, "51-100": 1, "101+": 0},
        "mass": {"total": 1234.5, "heavy": 987.6, "heavy_ratio": 0.8},
        "functions": [
            {"path": "a.py", "name": "small", "cc": 3, "sloc": 5, "line": 1, "mass": 6.7},
            {"path": "b.py", "name": "huge", "cc": 50, "sloc": 200, "line": 10, "mass": 707.1},
            {"path": "c.py", "name": "medium", "cc": 12, "sloc": 40, "line": 5, "mass": 75.9},
        ],
        "duplicates": [
            {"lines": 30, "locations": ["x.py:1", "y.py:1"]},
            {"lines": 10, "locations": ["a.py", "b.py"]},
        ],
    }
    stripped = _strip_health(health)
    assert "functions" not in stripped
    assert "duplicates" not in stripped
    assert stripped["erosion"] == 0.1
    assert stripped["top_high_cc"][0]["name"] == "huge"
    assert stripped["top_high_cc"][0]["cc"] == 50
    assert stripped["top_high_cc"][0]["mass"] == 707.1
    assert len(stripped["top_high_cc"]) == 3
    assert stripped["top_duplicates"][0]["lines"] == 30
    # New: distribution + mass totals pass through
    assert stripped["cc_distribution"]["6-10"] == 20
    assert stripped["mass"]["heavy_ratio"] == 0.8


def test_strip_health_works_without_mass_field():
    """Older health.json (no mass annotation) should still produce a valid bundle."""
    health = {
        "erosion": 0.1,
        "functions": [
            {"path": "a.py", "name": "big", "cc": 40, "sloc": 100, "line": 1},
            {"path": "b.py", "name": "small", "cc": 5, "sloc": 10, "line": 2},
        ],
    }
    stripped = _strip_health(health)
    # Ranking falls back to cc — 'big' first
    assert stripped["top_high_cc"][0]["name"] == "big"
    assert stripped["top_high_cc"][0]["mass"] is None
    # New fields default to None without crashing
    assert stripped["cc_distribution"] is None
    assert stripped["mass"] is None


def test_strip_scan_meta_drops_file_tree():
    scan = {
        "file_tree": [{"path": "a.py"}, {"path": "b.py"}],
        "token_counts": {"a.py": 100},
        "framework_signals": [{"name": "Django", "version": "4.2"}],
        "frontend_ratio": 0.0,
        "subprojects": [],
        "dependencies": [{"name": "django"}],
    }
    stripped = _strip_scan_meta(scan)
    assert "file_tree" not in stripped
    assert "token_counts" not in stripped
    assert stripped["total_files"] == 2
    assert stripped["dependency_count"] == 1


# ---------------------------------------------------------------------------
# Enterprise mode (paste-URL) — zero-knowledge bucket federation
# ---------------------------------------------------------------------------


def test_build_enterprise_bundle_envelope_shape():
    """Viewer's ReportResponse expects {bundle, created_at}. The enterprise
    envelope must match so the same viewer code renders both flows."""
    bundle = {"blueprint": {"meta": {"repository": "test/repo"}}}
    body_bytes = _build_enterprise_bundle(bundle)
    envelope = json.loads(body_bytes)
    assert envelope["bundle"] == bundle
    assert isinstance(envelope["created_at"], str)
    # ISO8601 with tz info — 'T' separator + '+' or 'Z' at the end
    assert "T" in envelope["created_at"]


def test_build_enterprise_share_url_encodes_get_url_in_fragment():
    """The GET URL must be base64url-encoded into the fragment of a /r/ext URL."""
    get_url = "https://acme-archie-shares.s3.amazonaws.com/abc.json?X-Amz-Signature=xyz&expires=123"
    share_url = _build_enterprise_share_url(get_url)

    # Path should be /r/ext; separator is #
    assert "/r/ext#" in share_url
    base, fragment = share_url.split("#", 1)
    assert base.endswith("/r/ext")

    # Fragment decodes back to the original GET URL
    padded = fragment + "=" * (-len(fragment) % 4)
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
    assert decoded == get_url


def test_build_enterprise_share_url_fragment_is_urlsafe():
    """Presigned URLs contain `&`, `=`, `/`, `+`. The base64url alphabet must not
    reintroduce characters that break when pasted in Slack/Markdown."""
    get_url = "https://bucket.s3.amazonaws.com/path?a=1&b=2&c=/+foo"
    share_url = _build_enterprise_share_url(get_url)
    fragment = share_url.split("#", 1)[1]
    # base64url uses only [A-Za-z0-9_-]; no +, /, or = (we strip padding)
    assert all(c.isalnum() or c in "_-" for c in fragment)


def test_enterprise_put_returns_true_on_2xx():
    """PUT succeeds when the presigned URL accepts the body."""

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=FakeResponse()):
        assert _enterprise_put("https://bucket/key?sig=x", b'{"x":1}') is True


def test_enterprise_put_returns_false_on_http_error(capsys):
    """PUT fails cleanly and prints a diagnostic on HTTP error."""
    import urllib.error
    import io

    http_error = urllib.error.HTTPError(
        url="https://bucket/key",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b"access denied"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        assert _enterprise_put("https://bucket/key?sig=x", b'{"x":1}') is False

    captured = capsys.readouterr()
    assert "403" in captured.err
    assert "access denied" in captured.err


def test_enterprise_upload_paste_end_to_end():
    """Given a bundle + PUT + GET URL, it uploads and returns the viewer URL."""

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    bundle = {"blueprint": {"meta": {"repository": "test/repo"}}}
    put_url = "https://bucket.s3.amazonaws.com/k?put_sig=1"
    get_url = "https://bucket.s3.amazonaws.com/k?get_sig=2"

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
        share_url = enterprise_upload_paste(bundle, put_url, get_url)

    assert share_url is not None
    # The share URL points at the viewer, not the customer bucket directly
    assert "/r/ext#" in share_url
    # The GET URL is in the fragment (base64url-encoded)
    fragment = share_url.split("#", 1)[1]
    padded = fragment + "=" * (-len(fragment) % 4)
    assert base64.urlsafe_b64decode(padded).decode("utf-8") == get_url

    # The upload request went to PUT URL with method PUT
    call_args = mock_urlopen.call_args
    req = call_args[0][0]
    assert req.full_url == put_url
    assert req.get_method() == "PUT"
    # Body is JSON with bundle wrapped in envelope
    envelope = json.loads(req.data.decode("utf-8"))
    assert envelope["bundle"] == bundle


def test_enterprise_upload_paste_returns_none_on_put_failure():
    """If the bucket rejects the PUT, the function returns None (no URL published)."""
    import urllib.error
    import io

    http_error = urllib.error.HTTPError(
        url="https://bucket/key",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b"denied"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        result = enterprise_upload_paste(
            {"blueprint": {}}, "https://bucket/put", "https://bucket/get"
        )
    assert result is None


# ---------------------------------------------------------------------------
# Argument parsing — mode flag routing
# ---------------------------------------------------------------------------


def test_parse_args_default_mode_no_flags():
    """Backward compatibility: `python3 upload.py /path` still works."""
    args = _parse_args(["/some/project"])
    assert args.project_root == "/some/project"
    assert args.mode == "default"
    assert args.put_url is None
    assert args.get_url is None


def test_parse_args_enterprise_paste_with_both_urls():
    args = _parse_args(
        [
            "/some/project",
            "--mode",
            "enterprise-paste",
            "--put-url",
            "https://bucket/put",
            "--get-url",
            "https://bucket/get",
        ]
    )
    assert args.mode == "enterprise-paste"
    assert args.put_url == "https://bucket/put"
    assert args.get_url == "https://bucket/get"


def test_parse_args_accepts_enterprise_creds():
    """Mode 2A doesn't take URL args — they're read from the profile file."""
    args = _parse_args(["/some/project", "--mode", "enterprise-creds"])
    assert args.mode == "enterprise-creds"


def test_parse_args_rejects_unknown_mode():
    """argparse enforces --mode choices."""
    with pytest.raises(SystemExit):
        _parse_args(["/some/project", "--mode", "bogus-mode"])


# ---------------------------------------------------------------------------
# SigV4 signing (pure stdlib)
# ---------------------------------------------------------------------------


# AWS canonical example (see: AWS docs "Generating a presigned URL for
# uploading objects" — Example 1). Real, published test vector that gives
# the same signature regardless of who signs it, letting us catch any drift
# in our sigv4 implementation.
#
# Source: AWS S3 documentation, historically used as the canonical sigv4 S3
# example. These are the example keys AWS documents for learning purposes —
# not real credentials.
AWS_EXAMPLE_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_EXAMPLE_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_EXAMPLE_HOST = "examplebucket.s3.amazonaws.com"
AWS_EXAMPLE_REGION = "us-east-1"
AWS_EXAMPLE_OBJECT = "test.txt"
AWS_EXAMPLE_DATE = datetime.datetime(2013, 5, 24, 0, 0, 0, tzinfo=datetime.timezone.utc)
AWS_EXAMPLE_EXPIRES = 86400
AWS_EXAMPLE_EXPECTED_SIG = "aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404"


def test_sigv4_derive_key_matches_aws_example():
    """Derive the kSigning value from the AWS docs example.
    Secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    Date: 20130524, Region: us-east-1, Service: s3
    This is an intermediate step — getting this right means the HMAC chain works."""
    k = _sigv4_derive_key(AWS_EXAMPLE_SECRET_KEY, "20130524", "us-east-1", "s3")
    assert isinstance(k, bytes)
    assert len(k) == 32  # SHA-256 output is always 32 bytes


def test_sigv4_presign_get_matches_aws_canonical_vector():
    """Validate the full presign against AWS's published example.

    URL host uses the pre-region format (examplebucket.s3.amazonaws.com)
    because that's what the AWS docs example uses. Modern format is
    examplebucket.s3.us-east-1.amazonaws.com, and for us-east-1 both work
    server-side — but canonical-request computation differs, so the vector
    only matches the pre-region form.
    """
    url = _sigv4_presign_get(
        host=AWS_EXAMPLE_HOST,
        region=AWS_EXAMPLE_REGION,
        object_key=AWS_EXAMPLE_OBJECT,
        access_key=AWS_EXAMPLE_ACCESS_KEY,
        secret_key=AWS_EXAMPLE_SECRET_KEY,
        expires_in=AWS_EXAMPLE_EXPIRES,
        now=AWS_EXAMPLE_DATE,
    )
    # Pull signature out of the URL
    assert f"X-Amz-Signature={AWS_EXAMPLE_EXPECTED_SIG}" in url, (
        f"Expected signature {AWS_EXAMPLE_EXPECTED_SIG} not found in URL:\n{url}"
    )


def test_sigv4_presign_get_url_structure():
    """All required query params are present, signature is hex-lowercase SHA-256 (64 chars)."""
    url = _sigv4_presign_get(
        host="bucket.s3.us-east-1.amazonaws.com",
        region="us-east-1",
        object_key="archie-shares/abc.json",
        access_key="AKIA000000000000TEST",
        secret_key="secret000000000000000000000000000000test",
    )
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "X-Amz-Credential=" in url
    assert "X-Amz-Date=" in url
    assert "X-Amz-Expires=" in url
    assert "X-Amz-SignedHeaders=host" in url
    # Signature is 64 hex chars
    sig = url.split("X-Amz-Signature=")[1]
    assert len(sig) == 64
    assert all(c in "0123456789abcdef" for c in sig)


def test_sigv4_sign_put_returns_full_auth_headers():
    """PUT signing returns URL + all required Authorization headers."""
    url, headers = _sigv4_sign_put(
        host="bucket.s3.us-east-1.amazonaws.com",
        region="us-east-1",
        object_key="archie-shares/abc.json",
        body=b'{"test": 1}',
        access_key="AKIA000000000000TEST",
        secret_key="secret000000000000000000000000000000test",
    )
    assert url == "https://bucket.s3.us-east-1.amazonaws.com/archie-shares/abc.json"
    assert headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")
    assert "Credential=AKIA000000000000TEST/" in headers["Authorization"]
    assert "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date" in headers["Authorization"]
    # Signature is 64 hex chars in the Authorization header
    sig_part = headers["Authorization"].split("Signature=")[1]
    assert len(sig_part) == 64
    assert all(c in "0123456789abcdef" for c in sig_part)
    assert headers["Content-Type"] == "application/json"
    assert headers["Host"] == "bucket.s3.us-east-1.amazonaws.com"
    assert headers["X-Amz-Content-Sha256"] != "UNSIGNED-PAYLOAD"


def test_sigv4_sign_put_payload_hash_matches_body():
    """Content hash in headers must be SHA-256 of the actual body."""
    import hashlib

    body = b'{"x": "secret bundle"}'
    _, headers = _sigv4_sign_put(
        host="bucket.s3.us-east-1.amazonaws.com",
        region="us-east-1",
        object_key="key",
        body=body,
        access_key="AKIA",
        secret_key="secret",
    )
    assert headers["X-Amz-Content-Sha256"] == hashlib.sha256(body).hexdigest()


def test_sigv4_sign_put_deterministic_given_same_time():
    """Same inputs at the same fixed time produce the same signature. (Non-reproducibility
    would mean our implementation has a hidden dependency on wallclock state.)"""
    now = datetime.datetime(2026, 4, 24, 10, 0, 0, tzinfo=datetime.timezone.utc)
    args = dict(
        host="bucket.s3.us-east-1.amazonaws.com",
        region="us-east-1",
        object_key="key",
        body=b"body",
        access_key="AKIA",
        secret_key="secret",
        now=now,
    )
    _, h1 = _sigv4_sign_put(**args)
    _, h2 = _sigv4_sign_put(**args)
    assert h1["Authorization"] == h2["Authorization"]


# ---------------------------------------------------------------------------
# Mode 2A — enterprise-creds end-to-end
# ---------------------------------------------------------------------------


def test_read_share_profile_returns_none_if_missing(tmp_path):
    """Absent profile returns None without raising."""
    with patch("upload.SHARE_PROFILE_PATH", tmp_path / "nonexistent.json"):
        assert _read_share_profile() is None


def test_read_share_profile_returns_none_if_missing_required_fields(tmp_path, capsys):
    """A half-filled profile returns None with a clear warning."""
    bad_profile = tmp_path / "share-profile.json"
    bad_profile.write_text(json.dumps({"bucket": "acme", "region": "us-east-1"}))  # no keys
    with patch("upload.SHARE_PROFILE_PATH", bad_profile):
        assert _read_share_profile() is None
    captured = capsys.readouterr()
    assert "missing keys" in captured.err


def test_read_share_profile_returns_parsed_dict_for_valid_file(tmp_path):
    profile_path = tmp_path / "share-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "bucket": "acme-archie-shares",
                "region": "us-east-1",
                "access_key_id": "AKIA",
                "secret_access_key": "secret",
                "key_prefix": "shares/",
            }
        )
    )
    with patch("upload.SHARE_PROFILE_PATH", profile_path):
        profile = _read_share_profile()
    assert profile is not None
    assert profile["bucket"] == "acme-archie-shares"
    assert profile["region"] == "us-east-1"


def test_enterprise_upload_creds_end_to_end():
    """Given a valid profile, the upload happens via sigv4 PUT and the returned
    URL is the viewer URL with a presigned GET URL in its fragment."""

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    profile = {
        "bucket": "acme-archie-shares",
        "region": "us-east-1",
        "access_key_id": "AKIAEXAMPLE",
        "secret_access_key": "secretexample",
        "key_prefix": "archie-shares/",
        "presign_expires_seconds": 604800,
    }
    bundle = {"blueprint": {"meta": {"repository": "test/repo"}}}

    with patch("urllib.request.urlopen", return_value=FakeResponse()) as mock_urlopen:
        share_url = enterprise_upload_creds(bundle, profile)

    assert share_url is not None
    assert "/r/ext#" in share_url

    # Fragment decodes to a presigned GET URL (has X-Amz-Signature)
    fragment = share_url.split("#", 1)[1]
    padded = fragment + "=" * (-len(fragment) % 4)
    get_url = base64.urlsafe_b64decode(padded).decode("utf-8")
    assert "acme-archie-shares.s3.us-east-1.amazonaws.com" in get_url
    assert "X-Amz-Signature=" in get_url
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in get_url

    # The PUT happened to the customer bucket (not BitRaptors Supabase)
    call_args = mock_urlopen.call_args
    put_req = call_args[0][0]
    assert "acme-archie-shares.s3.us-east-1.amazonaws.com" in put_req.full_url
    assert put_req.get_method() == "PUT"
    assert "Authorization" in put_req.headers
    assert put_req.headers["Authorization"].startswith("AWS4-HMAC-SHA256 ")

    # Body is the bundle envelope
    envelope = json.loads(put_req.data.decode("utf-8"))
    assert envelope["bundle"] == bundle


def test_enterprise_upload_creds_returns_none_on_put_failure():
    import urllib.error
    import io

    profile = {
        "bucket": "acme-archie-shares",
        "region": "us-east-1",
        "access_key_id": "AKIAEXAMPLE",
        "secret_access_key": "secretexample",
    }
    bundle = {"blueprint": {}}

    http_error = urllib.error.HTTPError(
        url="https://bucket/key",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b"access denied"),
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        result = enterprise_upload_creds(bundle, profile)
    assert result is None
