"""Scanner emits kind-tagged deployable entrypoints for the C4 Container level."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import scanner  # noqa: E402


def _files(*paths):
    return [{"path": p} for p in paths]


def test_build_targets_tags_kind_from_parent_dir():
    files = _files(
        "cmd/server/main.go",
        "cmd/billing-worker/main.go",
        "cmd/jobs/main.go",
        "cmd/benthos-collector/main.go",
        "openmeter/billing/service.go",   # not an entrypoint
    )
    targets = scanner.detect_build_targets(files)
    by_path = {t["path"]: t["kind"] for t in targets}
    assert by_path == {
        "cmd/server/main.go": "service",
        "cmd/billing-worker/main.go": "worker",
        "cmd/jobs/main.go": "cli",
        "cmd/benthos-collector/main.go": "app",
    }


def test_build_targets_is_sorted_for_determinism():
    files = _files("cmd/b/main.go", "cmd/a/main.go")
    targets = scanner.detect_build_targets(files)
    assert [t["path"] for t in targets] == ["cmd/a/main.go", "cmd/b/main.go"]
