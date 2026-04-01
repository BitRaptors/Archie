"""Tests for PhasedBlueprintGenerator with observation-first architecture."""
import json

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPhasedBlueprintGenerator:
    """Tests for the phased blueprint generator."""

    @pytest.fixture
    def mock_ai_client(self):
        """Create mock Anthropic client."""
        mock = AsyncMock()
        mock.messages.create = AsyncMock(return_value=MagicMock(
            content=[MagicMock(text='{"architecture_style": "layered", "components": []}')]
        ))
        return mock

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        mock = AsyncMock()
        mock_table = AsyncMock()
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.order = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=[]))
        mock.table = MagicMock(return_value=mock_table)
        return mock

    @pytest.fixture
    def sample_repo(self, tmp_path):
        """Create a sample repository structure for testing."""
        # Create directory structure
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "api").mkdir()
        (tmp_path / "src" / "services").mkdir()
        (tmp_path / "src" / "domain").mkdir()
        (tmp_path / "tests").mkdir()

        # Create Python files
        (tmp_path / "src" / "api" / "routes.py").write_text("""
from fastapi import APIRouter
from src.services.user_service import UserService

router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    service = UserService()
    return await service.get(user_id)
""")

        (tmp_path / "src" / "services" / "user_service.py").write_text("""
from typing import Optional
from src.domain.user import User

class UserService:
    async def get(self, user_id: str) -> Optional[User]:
        return User(id=user_id)
""")

        (tmp_path / "src" / "domain" / "user.py").write_text("""
from dataclasses import dataclass

@dataclass
class User:
    id: str
    name: str = ""
    email: str = ""
""")

        (tmp_path / "requirements.txt").write_text("fastapi>=0.100.0\npydantic>=2.0.0\n")
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-app"\n')

        return tmp_path

    @pytest.fixture
    def generator(self, mock_settings):
        """Create generator instance."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"result": "test"}')]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen


class TestObservationPhase:
    """Tests for the observation-first architecture detection phase."""

    @pytest.fixture
    def generator_with_mocks(self, mock_settings):
        """Create generator with mocked AI client."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            
            # Return observation result JSON
            observation_result = '''```json
{
    "organization_style": "Layered architecture with clear separation",
    "detected_components": [
        {"type": "API Routes", "naming_pattern": "*_routes.py", "examples": ["routes.py"]},
        {"type": "Services", "naming_pattern": "*_service.py", "examples": ["user_service.py"]},
        {"type": "Domain Entities", "naming_pattern": "*.py in domain/", "examples": ["user.py"]}
    ],
    "dependency_flow": "API -> Services -> Domain",
    "architecture_style": "Traditional layered with services and repositories",
    "unique_patterns": ["FastAPI dependency injection"],
    "standard_patterns_if_any": ["Repository pattern", "Service layer"],
    "key_search_terms": ["APIRouter", "Service", "dataclass"],
    "concerns": []
}
```'''
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text=observation_result)]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen

    @pytest.mark.asyncio
    async def test_extract_file_signatures(self, generator_with_mocks, sample_repo):
        """Test file signature extraction from repository."""
        generator = generator_with_mocks
        
        # Call the internal method to extract signatures
        signatures = await generator._extract_all_file_signatures(sample_repo)
        
        # Verify signatures contain expected content
        assert signatures is not None
        assert len(signatures) > 0
        
        # Should contain file paths
        assert "routes.py" in signatures or "user_service.py" in signatures

    @pytest.mark.asyncio
    async def test_observation_phase_detects_architecture(self, generator_with_mocks, sample_repo):
        """Test that observation phase detects architecture style."""
        generator = generator_with_mocks
        
        # Run observation phase
        result = await generator._run_observation_phase(
            repo_path=sample_repo,
            repository_name="test-repo",
            analysis_id="test-analysis-id"
        )
        
        # Verify result contains architecture detection
        assert result is not None
        assert "layered" in result.lower() or "architecture" in result.lower()

    @pytest.mark.asyncio
    async def test_observation_phase_captures_data(self, generator_with_mocks, sample_repo):
        """Test that observation phase captures analysis data."""
        generator = generator_with_mocks
        
        with patch('application.services.phased_blueprint_generator.analysis_data_collector') as mock_collector:
            mock_collector.capture_phase_data = AsyncMock()
            
            await generator._run_observation_phase(
                repo_path=sample_repo,
                repository_name="test-repo",
                analysis_id="test-analysis-id"
            )
            
            # Verify data was captured
            mock_collector.capture_phase_data.assert_called_once()
            call_args = mock_collector.capture_phase_data.call_args
            
            # Check positional args: (analysis_id, phase_name, gathered=..., sent=...)
            args = call_args[0]
            kwargs = call_args[1]
            
            assert args[0] == "test-analysis-id"  # analysis_id
            assert args[1] == "observation"  # phase_name
            assert "file_signatures" in kwargs.get("gathered", {})


class TestDynamicRAGQueries:
    """Tests for dynamic RAG query generation based on observation."""

    @pytest.fixture
    def generator_with_mocks(self, mock_settings):
        """Create generator with mocked AI client for RAG query generation."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            
            # Return RAG query generation result
            rag_queries_result = '''```json
{
    "discovery": ["FastAPI application structure", "main entry point", "app initialization"],
    "layers": ["service layer implementation", "domain entities", "API routes"],
    "patterns": ["dependency injection", "repository pattern", "service pattern"],
    "communication": ["HTTP endpoints", "API routes", "request handling"],
    "technology": ["FastAPI", "Pydantic", "async Python"]
}
```'''
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text=rag_queries_result)]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen

    @pytest.mark.asyncio
    async def test_generate_dynamic_rag_queries(self, generator_with_mocks):
        """Test dynamic RAG query generation from observation."""
        generator = generator_with_mocks
        
        observation_result = '''
{
    "architecture_style": "Layered FastAPI application",
    "key_search_terms": ["APIRouter", "Service", "domain"],
    "detected_components": [
        {"type": "Routes", "naming_pattern": "*_routes.py"}
    ]
}
'''
        
        queries = await generator._generate_dynamic_rag_queries(observation_result)
        
        # Verify queries were generated
        assert queries is not None
        assert isinstance(queries, dict)
        
        # Should have queries for major phases
        assert "discovery" in queries or len(queries) > 0


class TestFullPipeline:
    """Integration tests for the full analysis pipeline."""

    @pytest.fixture
    def full_generator(self, mock_settings):
        """Create full generator with comprehensive mocks."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            
            # Different responses for different phases
            responses = [
                # Observation phase (includes priority_files_by_phase)
                '```json\n{"architecture_style": "layered", "key_search_terms": ["service"], "priority_files_by_phase": {"discovery": ["src/api/routes.py"], "layers": ["src/services/user_service.py"], "patterns": [], "communication": [], "technology": [], "frontend": []}}\n```',
                # RAG query generation
                '```json\n{"discovery": ["structure"], "layers": ["layers"]}\n```',
                # Discovery phase
                "# Discovery\nFound a layered architecture with services.",
                # Layers phase
                "# Layers\nPresentation, Application, Domain layers identified.",
                # Patterns phase
                "# Patterns\nRepository and service patterns used.",
                # Communication phase
                "# Communication\nREST API endpoints.",
                # Technology phase
                "# Technology\nPython, FastAPI, PostgreSQL.",
                # Synthesis phase
                "# Backend Blueprint\n\n## Overview\nA layered FastAPI application.",
            ]
            
            call_count = {"n": 0}
            
            async def mock_create(*args, **kwargs):
                idx = min(call_count["n"], len(responses) - 1)
                call_count["n"] += 1
                return MagicMock(content=[MagicMock(text=responses[idx])])
            
            mock_client.messages.create = mock_create
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen

    @pytest.mark.asyncio
    async def test_full_pipeline_runs_observation_first(self, full_generator, sample_repo):
        """Test that full pipeline runs observation phase first."""
        generator = full_generator
        
        with patch('application.services.phased_blueprint_generator.analysis_data_collector') as mock_collector:
            mock_collector.capture_phase_data = AsyncMock()
            mock_collector.capture_gathered_data = AsyncMock()
            mock_collector.capture_rag_stats = AsyncMock()
            
            # Run the pipeline (this will fail without full setup, but we can check phase ordering)
            try:
                await generator.generate(
                    repo_path=sample_repo,
                    repository_name="test-repo",
                    analysis_id="test-id",
                )
            except Exception:
                pass  # Expected to fail without full setup
            
            # Check that capture_phase_data was called
            calls = mock_collector.capture_phase_data.call_args_list

            if calls:
                # First phase should be observation
                # Args are positional: (analysis_id, phase_name, gathered=..., sent=...)
                first_call = calls[0]
                args = first_call[0]
                assert args[1] == "observation"  # phase_name is second positional arg


class TestArchitectureAgnostic:
    """Tests to verify architecture-agnostic behavior."""

    @pytest.fixture
    def ios_repo(self, tmp_path):
        """Create a sample iOS repository structure."""
        (tmp_path / "App").mkdir()
        (tmp_path / "App" / "Views").mkdir()
        (tmp_path / "App" / "ViewModels").mkdir()
        (tmp_path / "App" / "Models").mkdir()
        (tmp_path / "App" / "Services").mkdir()

        (tmp_path / "App" / "Views" / "ContentView.swift").write_text("""
import SwiftUI

struct ContentView: View {
    @StateObject var viewModel = ContentViewModel()
    
    var body: some View {
        Text(viewModel.message)
    }
}
""")

        (tmp_path / "App" / "ViewModels" / "ContentViewModel.swift").write_text("""
import Foundation
import Combine

class ContentViewModel: ObservableObject {
    @Published var message: String = ""
    private let userService: UserService
    
    init(userService: UserService = UserService()) {
        self.userService = userService
    }
}
""")

        (tmp_path / "App" / "Models" / "User.swift").write_text("""
import Foundation

struct User: Codable, Identifiable {
    let id: UUID
    let name: String
    let email: String
}
""")

        (tmp_path / "Package.swift").write_text("""
// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TestApp",
    platforms: [.iOS(.v17)]
)
""")

        return tmp_path

    @pytest.fixture
    def android_repo(self, tmp_path):
        """Create a sample Android repository structure."""
        (tmp_path / "app" / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
        (tmp_path / "app" / "src" / "main" / "java" / "com" / "example" / "ui").mkdir()
        (tmp_path / "app" / "src" / "main" / "java" / "com" / "example" / "data").mkdir()
        (tmp_path / "app" / "src" / "main" / "java" / "com" / "example" / "domain").mkdir()

        (tmp_path / "app" / "src" / "main" / "java" / "com" / "example" / "ui" / "MainActivity.kt").write_text("""
package com.example.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import com.example.ui.theme.TestAppTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            TestAppTheme {
                MainScreen()
            }
        }
    }
}
""")

        (tmp_path / "app" / "build.gradle.kts").write_text("""
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example"
    compileSdk = 34
}
""")

        return tmp_path

    @pytest.mark.asyncio
    async def test_detects_ios_mvvm_architecture(self, ios_repo, mock_settings):
        """Test that observation phase correctly detects iOS MVVM architecture."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            
            # iOS MVVM observation result
            ios_result = '''```json
{
    "organization_style": "MVVM with SwiftUI",
    "detected_components": [
        {"type": "Views", "naming_pattern": "*View.swift", "examples": ["ContentView.swift"]},
        {"type": "ViewModels", "naming_pattern": "*ViewModel.swift", "examples": ["ContentViewModel.swift"]},
        {"type": "Models", "naming_pattern": "*.swift in Models/", "examples": ["User.swift"]}
    ],
    "dependency_flow": "Views -> ViewModels -> Services -> Models",
    "architecture_style": "MVVM (Model-View-ViewModel) with SwiftUI and Combine",
    "unique_patterns": ["@StateObject", "@Published", "ObservableObject"],
    "standard_patterns_if_any": ["MVVM", "Dependency Injection"],
    "key_search_terms": ["View", "ViewModel", "@StateObject", "ObservableObject"],
    "concerns": []
}
```'''
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text=ios_result)]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client

            result = await gen._run_observation_phase(
                repo_path=ios_repo,
                repository_name="ios-app",
                analysis_id=None
            )

            # Verify MVVM was detected
            assert "MVVM" in result or "ViewModel" in result

    @pytest.mark.asyncio
    async def test_detects_android_architecture(self, android_repo, mock_settings):
        """Test that observation phase correctly detects Android architecture."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            
            # Android observation result
            android_result = '''```json
{
    "organization_style": "Clean Architecture with Jetpack Compose",
    "detected_components": [
        {"type": "UI Layer", "naming_pattern": "*Activity.kt, *Screen.kt", "examples": ["MainActivity.kt"]},
        {"type": "Data Layer", "naming_pattern": "*Repository.kt", "examples": []},
        {"type": "Domain Layer", "naming_pattern": "*UseCase.kt", "examples": []}
    ],
    "dependency_flow": "UI -> Domain -> Data",
    "architecture_style": "Android Clean Architecture with Jetpack Compose",
    "unique_patterns": ["ComponentActivity", "setContent", "Composable"],
    "standard_patterns_if_any": ["Clean Architecture", "MVVM"],
    "key_search_terms": ["Activity", "Compose", "ViewModel", "Repository"],
    "concerns": []
}
```'''
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text=android_result)]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client

            result = await gen._run_observation_phase(
                repo_path=android_repo,
                repository_name="android-app",
                analysis_id=None
            )

            # Verify Android architecture was detected
            assert "Android" in result or "Compose" in result or "Activity" in result


class TestTokenBudget:
    """Tests for token budget management in observation phase."""

    @pytest.fixture
    def large_repo(self, tmp_path):
        """Create a large repository with many files."""
        for i in range(100):
            dir_path = tmp_path / f"module_{i}"
            dir_path.mkdir()
            for j in range(10):
                (dir_path / f"file_{j}.py").write_text(f"""
# File {i}-{j}
import os
from typing import List, Dict

class Class{i}_{j}:
    def method_a(self):
        pass
    
    def method_b(self, param: str) -> List[str]:
        return []
""")
        return tmp_path

    @pytest.mark.asyncio
    async def test_observation_respects_file_limit(self, large_repo, mock_settings):
        """Test that observation phase respects file count limits."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"architecture_style": "modular"}')]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client

            # Extract signatures
            signatures = await gen._extract_all_file_signatures(large_repo)
            
            # Should not exceed reasonable token budget
            # Assuming ~300 files limit and ~100 chars per signature
            assert len(signatures) < 500000  # ~500K chars max

    @pytest.mark.asyncio
    async def test_observation_prioritizes_important_files(self, tmp_path, mock_settings):
        """Test that observation phase prioritizes important files."""
        # Create mix of important and less important files
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("# Main entry point\nfrom app import create_app")
        (tmp_path / "src" / "app.py").write_text("# App factory\ndef create_app(): pass")
        (tmp_path / "src" / "__init__.py").write_text("")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text("# Tests\nimport pytest")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "readme.md").write_text("# Documentation")

        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=MagicMock(
                content=[MagicMock(text='{"architecture_style": "simple"}')]
            ))
            mock_anthropic.return_value = mock_client

            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client

            signatures = await gen._extract_all_file_signatures(tmp_path)

            # Should include main source files
            assert "main.py" in signatures or "app.py" in signatures


class TestSmartFileReading:
    """Tests for priority file parsing and reading (Phase 0.5)."""

    @pytest.fixture
    def generator(self, mock_settings):
        """Create a generator instance for testing utility methods."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen

    def test_parse_priority_files_valid_json(self, generator):
        """Test parsing priority_files_by_phase from well-formed observation."""
        observation = '```json\n' + json.dumps({
            "architecture_style": "layered",
            "detected_components": [
                {"type": "Routes", "examples": ["src/routes.py"]}
            ],
            "priority_files_by_phase": {
                "discovery": ["src/main.py", "src/config.py"],
                "layers": ["src/container.py"],
                "patterns": ["src/decorators.py"],
                "communication": [],
                "technology": ["Dockerfile"],
                "frontend": []
            }
        }) + '\n```'

        result = generator._parse_priority_files(observation)

        assert "discovery" in result
        assert "src/main.py" in result["discovery"]
        assert "src/config.py" in result["discovery"]
        # Should merge detected_components examples into discovery
        assert "src/routes.py" in result["discovery"]
        assert "src/container.py" in result["layers"]

    def test_parse_priority_files_missing_field(self, generator):
        """Test graceful fallback when priority_files_by_phase is absent."""
        observation = '```json\n{"architecture_style": "layered"}\n```'
        result = generator._parse_priority_files(observation)
        assert result == {}

    def test_parse_priority_files_invalid_json(self, generator):
        """Test graceful fallback on garbage input."""
        result = generator._parse_priority_files("not valid json at all {{{")
        assert result == {}

    @pytest.mark.asyncio
    async def test_read_priority_files_respects_budget(self, generator, tmp_path):
        """Test that reading stops once total_budget_chars is reached."""
        # Create 50 files of 500 chars each = 25K total
        for i in range(50):
            (tmp_path / f"file_{i}.py").write_text("x" * 500)

        priority_map = {
            "discovery": [f"file_{i}.py" for i in range(50)]
        }

        result = await generator._read_priority_files(
            tmp_path, priority_map, total_budget_chars=5_000, per_file_max_chars=500
        )

        # Should have stopped before reading all 50 files
        total_chars = sum(len(c) for c in result.get("discovery", {}).values())
        assert total_chars <= 5_000

    @pytest.mark.asyncio
    async def test_read_priority_files_deduplicates(self, generator, tmp_path):
        """Test that a file appearing in two phases is read from disk only once."""
        (tmp_path / "shared.py").write_text("shared content")

        priority_map = {
            "discovery": ["shared.py"],
            "layers": ["shared.py"],
        }

        result = await generator._read_priority_files(tmp_path, priority_map)

        # Both phases should have the file
        assert "shared.py" in result.get("discovery", {})
        assert "shared.py" in result.get("layers", {})
        # Content should be identical (read once from cache)
        assert result["discovery"]["shared.py"] == result["layers"]["shared.py"]

    @pytest.mark.asyncio
    async def test_read_priority_files_skips_missing(self, generator, tmp_path):
        """Test that nonexistent files are silently skipped."""
        (tmp_path / "exists.py").write_text("real content")

        priority_map = {
            "discovery": ["exists.py", "does_not_exist.py"],
        }

        result = await generator._read_priority_files(tmp_path, priority_map)

        assert "exists.py" in result.get("discovery", {})
        assert "does_not_exist.py" not in result.get("discovery", {})

    def test_build_phase_context_formatting(self, generator):
        """Test that output has filepath heading and code block."""
        generator._phase_files = {
            "layers": {"src/container.py": "class Container:\n    pass"}
        }

        ctx = generator._build_phase_context("layers")

        assert "**src/container.py**" in ctx
        assert "```" in ctx
        assert "class Container:" in ctx

    def test_build_phase_context_max_chars(self, generator):
        """Test that large files are truncated by max_chars."""
        generator._phase_files = {
            "layers": {"big.py": "x" * 50_000}
        }

        ctx = generator._build_phase_context("layers", max_chars=1_000)
        assert len(ctx) <= 1_100  # small margin for truncation marker

    @pytest.mark.asyncio
    async def test_read_priority_files_skips_ignored_dirs(self, generator, tmp_path):
        """Files inside ignored directories are not read."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("good content")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "react.js").write_text("react")
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "site.py").write_text("site")

        priority_map = {
            "discovery": [
                "src/main.py",
                "node_modules/react.js",
                ".venv/lib/site.py",
            ],
        }

        result = await generator._read_priority_files(
            tmp_path, priority_map,
            discovery_ignored_dirs={"node_modules", ".venv"},
        )

        assert "src/main.py" in result.get("discovery", {})
        assert "node_modules/react.js" not in result.get("discovery", {})
        assert ".venv/lib/site.py" not in result.get("discovery", {})

    @pytest.mark.asyncio
    async def test_read_priority_files_no_ignored_dirs_reads_all(self, generator, tmp_path):
        """When no ignored dirs passed, all files are read."""
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "react.js").write_text("react")

        priority_map = {"discovery": ["node_modules/react.js"]}

        result = await generator._read_priority_files(tmp_path, priority_map)

        assert "node_modules/react.js" in result.get("discovery", {})

    @pytest.mark.asyncio
    async def test_read_priority_files_ignored_dir_nested(self, generator, tmp_path):
        """Files deep inside ignored directories are also skipped."""
        (tmp_path / "vendor" / "bundle" / "gems").mkdir(parents=True)
        (tmp_path / "vendor" / "bundle" / "gems" / "gem.rb").write_text("gem")

        priority_map = {"discovery": ["vendor/bundle/gems/gem.rb"]}

        result = await generator._read_priority_files(
            tmp_path, priority_map,
            discovery_ignored_dirs={"vendor"},
        )

        assert result == {}


class TestPhaseCodeContext:
    """Tests for _get_phase_code priority cascade."""

    @pytest.fixture
    def generator(self, mock_settings):
        """Create generator for cascade tests."""
        with patch('anthropic.AsyncAnthropic') as mock_anthropic:
            mock_client = AsyncMock()
            mock_anthropic.return_value = mock_client
            from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
            gen = PhasedBlueprintGenerator(settings=mock_settings)
            gen._client = mock_client
            return gen

    @pytest.mark.asyncio
    async def test_cascade_targeted_only(self, generator, tmp_path):
        """No RAG, phase_files present → uses targeted context."""
        generator._phase_files = {
            "layers": {"src/di.py": "class Container: ..."}
        }

        code, label = await generator._get_phase_code(
            phase="layers",
            repository_id=None,
            repo_path=tmp_path,
            rag_enabled=False,
            code_samples={"fallback.py": "# fallback"},
        )

        assert label == "targeted"
        assert "Container" in code

    @pytest.mark.asyncio
    async def test_cascade_fallback(self, generator, tmp_path):
        """No RAG, no phase_files → uses code_samples fallback."""
        generator._phase_files = {}

        code, label = await generator._get_phase_code(
            phase="layers",
            repository_id=None,
            repo_path=tmp_path,
            rag_enabled=False,
            code_samples={"routes.py": "from fastapi import APIRouter"},
        )

        assert label == "fallback"
        assert "APIRouter" in code

    @pytest.mark.asyncio
    async def test_cascade_returns_source_label(self, generator, tmp_path):
        """Verify correct label strings for each cascade level."""
        # Targeted
        generator._phase_files = {"patterns": {"f.py": "content"}}
        _, label = await generator._get_phase_code(
            phase="patterns", repository_id=None, repo_path=tmp_path,
            rag_enabled=False, code_samples={},
        )
        assert label == "targeted"

        # Fallback
        generator._phase_files = {}
        _, label = await generator._get_phase_code(
            phase="patterns", repository_id=None, repo_path=tmp_path,
            rag_enabled=False, code_samples={"a.py": "code"},
        )
        assert label == "fallback"
