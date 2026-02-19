"""Tests for analysis settings domain entities and constants."""
import pytest

from domain.entities.analysis_settings import (
    CAPABILITY_OPTIONS,
    DEFAULT_IGNORED_DIRS,
    DEFAULT_LIBRARY_CAPABILITIES,
    ECOSYSTEM_OPTIONS,
    IgnoredDirectory,
    LibraryCapability,
)


class TestCapabilityOptions:

    def test_is_sorted(self):
        assert CAPABILITY_OPTIONS == sorted(CAPABILITY_OPTIONS)

    def test_no_duplicates(self):
        assert len(CAPABILITY_OPTIONS) == len(set(CAPABILITY_OPTIONS))

    def test_all_lowercase_snake_case(self):
        for cap in CAPABILITY_OPTIONS:
            assert cap == cap.lower(), f"{cap} is not lowercase"
            assert " " not in cap, f"{cap} contains spaces"

    def test_known_capabilities_present(self):
        required = [
            "persistence", "authentication", "networking",
            "state_management", "orm", "realtime", "storage",
        ]
        for cap in required:
            assert cap in CAPABILITY_OPTIONS, f"{cap} missing from CAPABILITY_OPTIONS"


class TestEcosystemOptions:

    def test_is_sorted(self):
        assert ECOSYSTEM_OPTIONS == sorted(ECOSYSTEM_OPTIONS)

    def test_no_duplicates(self):
        assert len(ECOSYSTEM_OPTIONS) == len(set(ECOSYSTEM_OPTIONS))

    def test_known_ecosystems_present(self):
        required = ["React", "iOS", "Android", "Python", "Flutter", "Node.js"]
        for eco in required:
            assert eco in ECOSYSTEM_OPTIONS, f"{eco} missing from ECOSYSTEM_OPTIONS"


class TestDefaultIgnoredDirs:

    def test_is_set(self):
        assert isinstance(DEFAULT_IGNORED_DIRS, set)

    def test_common_dirs_present(self):
        expected = ["node_modules", "Pods", ".git", "__pycache__", "dist", "build", "vendor"]
        for d in expected:
            assert d in DEFAULT_IGNORED_DIRS, f"{d} missing from DEFAULT_IGNORED_DIRS"

    def test_no_empty_strings(self):
        for d in DEFAULT_IGNORED_DIRS:
            assert d.strip(), "Empty string found in DEFAULT_IGNORED_DIRS"


class TestDefaultLibraryCapabilities:

    def test_all_capabilities_are_valid(self):
        """Every capability in the defaults must be in CAPABILITY_OPTIONS."""
        valid = set(CAPABILITY_OPTIONS)
        for lib_name, info in DEFAULT_LIBRARY_CAPABILITIES.items():
            for cap in info["capabilities"]:
                assert cap in valid, (
                    f"Invalid capability '{cap}' for library '{lib_name}'. "
                    f"Not in CAPABILITY_OPTIONS."
                )

    def test_all_ecosystems_are_valid(self):
        """Every ecosystem in the defaults must be in ECOSYSTEM_OPTIONS."""
        valid = set(ECOSYSTEM_OPTIONS)
        for lib_name, info in DEFAULT_LIBRARY_CAPABILITIES.items():
            assert info["ecosystem"] in valid, (
                f"Invalid ecosystem '{info['ecosystem']}' for library '{lib_name}'. "
                f"Not in ECOSYSTEM_OPTIONS."
            )

    def test_every_entry_has_ecosystem_and_capabilities(self):
        for lib_name, info in DEFAULT_LIBRARY_CAPABILITIES.items():
            assert "ecosystem" in info, f"{lib_name} missing 'ecosystem'"
            assert "capabilities" in info, f"{lib_name} missing 'capabilities'"
            assert isinstance(info["capabilities"], list)
            assert len(info["capabilities"]) > 0, f"{lib_name} has empty capabilities"

    def test_known_libraries_present(self):
        expected = ["firebase", "supabase", "axios", "redux", "prisma", "sentry"]
        for lib in expected:
            assert lib in DEFAULT_LIBRARY_CAPABILITIES, f"{lib} missing from defaults"


class TestIgnoredDirectoryModel:

    def test_default_values(self):
        d = IgnoredDirectory()
        assert d.id == ""
        assert d.directory_name == ""
        assert d.created_at is None

    def test_model_dump(self):
        d = IgnoredDirectory(id="abc", directory_name="node_modules")
        data = d.model_dump()
        assert data["id"] == "abc"
        assert data["directory_name"] == "node_modules"


class TestLibraryCapabilityModel:

    def test_default_values(self):
        lib = LibraryCapability()
        assert lib.id == ""
        assert lib.library_name == ""
        assert lib.ecosystem == ""
        assert lib.capabilities == []
        assert lib.created_at is None
        assert lib.updated_at is None

    def test_model_dump(self):
        lib = LibraryCapability(
            id="abc", library_name="firebase",
            ecosystem="Google Firebase",
            capabilities=["persistence", "authentication"],
        )
        data = lib.model_dump()
        assert data["library_name"] == "firebase"
        assert data["ecosystem"] == "Google Firebase"
        assert "persistence" in data["capabilities"]
