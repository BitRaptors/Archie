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
    by_path = {t["path"]: t["kind"] for t in scanner.detect_build_targets(files)}
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


def test_build_targets_excludes_barrel_and_ui_files():
    # index.ts/js (barrels) and App.tsx (UI root) are NOT deployable containers.
    files = _files(
        "api/client/javascript/index.ts",
        "api/spec/packages/legacy/lib/index.js",
        "src/App.tsx",
        "cmd/server/main.go",   # the only real deployable
    )
    paths = {t["path"] for t in scanner.detect_build_targets(files)}
    assert paths == {"cmd/server/main.go"}


def test_entry_stem_rule_is_language_agnostic():
    # Universal process-entry stems across any extension — no per-language list.
    files = _files(
        "src/main.rs",                 # Rust
        "app/Program.cs",              # C# / .NET
        "svc/main.cpp",                # C++
        "lib/main.dart",              # Dart / Flutter
        "pkg/__main__.py",            # Python module
        "web/main.ts",                 # Node
        "android/MainActivity.kt",     # Android
        "ios/AppDelegate.swift",       # iOS
        "components/Button.tsx",       # NOT an entry
    )
    paths = {t["path"] for t in scanner.detect_build_targets(files)}
    assert paths == {
        "src/main.rs", "app/Program.cs", "svc/main.cpp", "lib/main.dart",
        "pkg/__main__.py", "web/main.ts", "android/MainActivity.kt",
        "ios/AppDelegate.swift",
    }


def test_stem_rule_ignores_non_code_extensions():
    # main.* that isn't a programming-language source file is NOT a deployable.
    files = _files(
        "api/spec/legacy/src/main.tsp",   # TypeSpec schema
        "styles/main.css",                # CSS
        "docs/main.md",                   # Markdown
        "infra/main.tf",                  # Terraform
        "cmd/app/main.go",                # the only real one
    )
    paths = {t["path"] for t in scanner.detect_build_targets(files)}
    assert paths == {"cmd/app/main.go"}


def test_manifest_marks_standalone_mobile_app():
    # A Flutter app: pubspec at root + main.dart under lib → one mobile container.
    files = _files("pubspec.yaml", "lib/main.dart")
    targets = scanner.detect_build_targets(files)
    # pubspec (root) is an umbrella over lib/main.dart → suppressed; the entry is
    # upgraded to platform 'mobile'.
    assert len(targets) == 1
    assert targets[0]["path"] == "lib/main.dart" and targets[0]["kind"] == "mobile"


def test_csproj_desktop_app_without_entry_file():
    # A .NET app with no recognized source entry → the manifest IS the container.
    files = _files("App/App.csproj", "App/Window.xaml.cs")
    targets = scanner.detect_build_targets(files)
    assert len(targets) == 1
    assert targets[0]["kind"] == "desktop" and targets[0]["name"] == "App"


def test_umbrella_manifest_suppressed_by_binaries():
    # Root go.mod + Dockerfile over cmd/* binaries → only the binaries, no umbrella.
    files = _files("go.mod", "Dockerfile", "cmd/a/main.go", "cmd/b/main.go")
    paths = {t["path"] for t in scanner.detect_build_targets(files)}
    assert paths == {"cmd/a/main.go", "cmd/b/main.go"}
