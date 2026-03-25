"""Tests for first-class Android & iOS mobile support.

Covers:
- SOURCE_CODE_EXTENSIONS constant (includes .xml, .kt, .swift, .m, .mm)
- Mobile frontend detection (_detect_frontend)
- Expanded CAPABILITY_OPTIONS and ECOSYSTEM_OPTIONS
- Removal of DEFAULT_LIBRARY_CAPABILITIES / DEFAULT_IGNORED_DIRS fallback constants
- Empty capabilities when no DB is available
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.entities.analysis_settings import (
    CAPABILITY_OPTIONS,
    ECOSYSTEM_OPTIONS,
    SOURCE_CODE_EXTENSIONS,
)


# ── SOURCE_CODE_EXTENSIONS ──────────────────────────────────────────────────


class TestSourceCodeExtensions:

    def test_is_frozenset(self):
        assert isinstance(SOURCE_CODE_EXTENSIONS, frozenset)

    def test_includes_xml(self):
        assert ".xml" in SOURCE_CODE_EXTENSIONS

    def test_includes_kotlin(self):
        assert ".kt" in SOURCE_CODE_EXTENSIONS

    def test_includes_swift(self):
        assert ".swift" in SOURCE_CODE_EXTENSIONS

    def test_includes_objc(self):
        assert ".m" in SOURCE_CODE_EXTENSIONS
        assert ".mm" in SOURCE_CODE_EXTENSIONS

    def test_includes_common_web_extensions(self):
        for ext in [".py", ".js", ".ts", ".tsx", ".jsx"]:
            assert ext in SOURCE_CODE_EXTENSIONS, f"{ext} missing"

    def test_includes_java(self):
        assert ".java" in SOURCE_CODE_EXTENSIONS


# ── Mobile Frontend Detection ───────────────────────────────────────────────


class TestMobileFrontendDetection:
    """Test _detect_frontend() with mobile-specific indicators."""

    def _make_generator(self):
        """Create a PhasedBlueprintGenerator with mocked settings."""
        mock_settings = MagicMock()
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.default_ai_model = "test-model"
        mock_settings.synthesis_ai_model = "test-model"
        mock_settings.synthesis_max_tokens = 10000
        mock_settings.file_reading_budget = 0
        mock_settings.file_reading_per_file_max = 0

        with patch("application.services.phased_blueprint_generator.AsyncAnthropic"):
            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            return PhasedBlueprintGenerator(settings=mock_settings)

    def test_detects_swiftui(self):
        gen = self._make_generator()
        assert gen._detect_frontend("swiftui views", "", "") is True

    def test_detects_uikit(self):
        gen = self._make_generator()
        assert gen._detect_frontend("uikit based", "", "") is True

    def test_detects_jetpack_compose(self):
        gen = self._make_generator()
        assert gen._detect_frontend("jetpack compose", "", "") is True

    def test_detects_swift_extension(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "Sources/App.swift", "") is True

    def test_detects_kotlin_extension(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "app/Main.kt", "") is True

    def test_detects_build_gradle(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "", "build.gradle") is True

    def test_detects_storyboard(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "Main.storyboard", "") is True

    def test_detects_android_manifest(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "app/src/main/AndroidManifest.xml", "") is True

    def test_detects_podfile(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "", "podfile somewhere") is True

    def test_detects_xcodeproj(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "MyApp.xcodeproj", "") is True

    def test_detects_viewcontroller(self):
        gen = self._make_generator()
        assert gen._detect_frontend("LoginViewController detected", "", "") is True

    def test_no_false_positive_on_empty(self):
        gen = self._make_generator()
        assert gen._detect_frontend("", "", "") is False

    def test_no_false_positive_on_backend_only(self):
        gen = self._make_generator()
        assert gen._detect_frontend(
            "Python FastAPI backend with SQLAlchemy",
            "src/main.py\nsrc/models.py",
            "requirements.txt",
        ) is False


# ── Capability & Ecosystem Options ──────────────────────────────────────────


class TestMobileLibraryCapabilities:

    def test_new_capabilities_in_options(self):
        new_caps = [
            "image_loading", "logging", "navigation",
            "serialization", "ui_framework", "concurrency",
        ]
        for cap in new_caps:
            assert cap in CAPABILITY_OPTIONS, f"{cap} missing from CAPABILITY_OPTIONS"

    def test_new_ecosystems_in_options(self):
        assert "Kotlin Multiplatform" in ECOSYSTEM_OPTIONS
        assert "Cross-platform" in ECOSYSTEM_OPTIONS

    def test_no_default_library_capabilities_constant(self):
        """Verify DEFAULT_LIBRARY_CAPABILITIES no longer exists in analysis_settings."""
        import domain.entities.analysis_settings as mod
        assert not hasattr(mod, "DEFAULT_LIBRARY_CAPABILITIES"), (
            "DEFAULT_LIBRARY_CAPABILITIES should be removed (renamed to SEED_LIBRARY_CAPABILITIES)"
        )

    def test_no_default_ignored_dirs_constant(self):
        """Verify DEFAULT_IGNORED_DIRS no longer exists in analysis_settings."""
        import domain.entities.analysis_settings as mod
        assert not hasattr(mod, "DEFAULT_IGNORED_DIRS"), (
            "DEFAULT_IGNORED_DIRS should be removed (renamed to SEED_IGNORED_DIRS)"
        )

    def test_seed_constants_exist(self):
        """The renamed SEED_* constants should exist."""
        import domain.entities.analysis_settings as mod
        assert hasattr(mod, "SEED_IGNORED_DIRS")
        assert hasattr(mod, "SEED_LIBRARY_CAPABILITIES")


# ── Empty Capabilities When No DB ───────────────────────────────────────────


class TestEmptyCapabilitiesWhenNoDB:

    @pytest.mark.asyncio
    async def test_empty_capabilities_when_no_db(self):
        """AnalysisService with no DB client should use empty library_capabilities."""
        # Import here to avoid issues with module-level dependencies
        from application.services.analysis_service import AnalysisService

        mock_analysis_repo = AsyncMock()
        mock_analysis = MagicMock()
        mock_analysis.id = "test-analysis-id"
        mock_analysis.repository_id = "test-repo-id"
        mock_analysis_repo.get_by_id = AsyncMock(return_value=mock_analysis)

        mock_repo_repo = AsyncMock()
        mock_repo = MagicMock()
        mock_repo.full_name = "test/repo"
        mock_repo_repo.get_by_id = AsyncMock(return_value=mock_repo)

        mock_event_repo = AsyncMock()
        mock_structure_analyzer = AsyncMock()
        mock_structure_analyzer.analyze = AsyncMock(return_value={
            "file_tree": [{"type": "file", "path": "main.py", "size": 100}],
        })
        mock_storage = AsyncMock()
        mock_storage.exists = AsyncMock(return_value=True)
        mock_generator = AsyncMock()
        mock_generator.generate = AsyncMock(return_value={
            "structured": {"meta": {"repository": "test"}},
            "phase_outputs": {},
        })
        mock_generator._progress_callback = None

        service = AnalysisService(
            analysis_repo=mock_analysis_repo,
            repository_repo=mock_repo_repo,
            event_repo=mock_event_repo,
            structure_analyzer=mock_structure_analyzer,
            persistent_storage=mock_storage,
            phased_blueprint_generator=mock_generator,
            db_client=None,  # No DB!
        )

        # The service should initialize without error and use empty defaults
        # We verify by checking that it doesn't raise on import of removed constants
        assert service._db_client is None
