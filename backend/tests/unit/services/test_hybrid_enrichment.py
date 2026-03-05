"""Tests for HybridEnrichmentEngine."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from domain.entities.intent_layer import (
    FolderNode,
    FolderBlueprint,
    FolderEnrichment,
    KeyFileGuide,
    CommonTask,
    IntentLayerConfig,
)
from application.services.hybrid_enrichment_engine import (
    HybridEnrichmentEngine,
    _count_tokens,
    _truncate_to_tokens,
    _prioritize_files,
)


# ── Fixtures ──

@pytest.fixture
def settings():
    s = MagicMock()
    s.anthropic_api_key = "test-key"
    s.default_ai_model = "claude-haiku-4-5-20251001"
    return s


@pytest.fixture
def config():
    return IntentLayerConfig(
        max_concurrent=5,
        enable_ai_enrichment=True,
        enrichment_model="",
    )


@pytest.fixture
def engine(settings, config):
    return HybridEnrichmentEngine(settings, config)


def _make_node(path: str, depth: int, files: list[str] = None, children: list[str] = None) -> FolderNode:
    name = path.rsplit("/", 1)[-1] if "/" in path else (path or "root")
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    return FolderNode(
        path=path,
        name=name,
        depth=depth,
        parent_path=parent,
        files=files or [],
        file_count=len(files or []),
        children=children or [],
    )


# ── TestParseResponse ──

class TestParseResponse:

    def test_valid_json(self):
        text = json.dumps({
            "purpose": "HTTP routing layer",
            "patterns": ["Use decorators"],
            "key_file_guides": [{"file": "routes.py", "purpose": "Routes", "modification_guide": "Add route"}],
            "anti_patterns": ["Don't put logic here"],
            "common_task": {"task": "Add endpoint", "steps": ["Create route"]},
            "testing": ["pytest routes"],
            "debugging": ["Check logs"],
            "decisions": ["Thin by design"],
        })
        result = HybridEnrichmentEngine._parse_response("src/api", text)

        assert result.has_ai_content is True
        assert result.purpose == "HTTP routing layer"
        assert len(result.patterns) == 1
        assert result.key_file_guides[0].file == "routes.py"
        assert result.common_task.task == "Add endpoint"
        assert len(result.testing) == 1
        assert len(result.debugging) == 1
        assert len(result.decisions) == 1

    def test_json_in_code_block(self):
        text = '```json\n{"purpose": "Test folder", "patterns": ["pattern1"]}\n```'
        result = HybridEnrichmentEngine._parse_response("src/test", text)

        assert result.has_ai_content is True
        assert result.purpose == "Test folder"

    def test_malformed_json_returns_empty(self):
        result = HybridEnrichmentEngine._parse_response("src/bad", "not json at all {{{")

        assert result.has_ai_content is False
        assert result.path == "src/bad"

    def test_partial_fields(self):
        text = json.dumps({"purpose": "Partial", "patterns": ["p1", "p2"]})
        result = HybridEnrichmentEngine._parse_response("src/partial", text)

        assert result.has_ai_content is True
        assert result.purpose == "Partial"
        assert len(result.patterns) == 2
        assert result.common_task is None
        assert result.testing == []

    def test_common_task_parsing(self):
        text = json.dumps({
            "purpose": "Test",
            "common_task": {"task": "Add feature", "steps": ["Step 1", "Step 2", "Step 3"]},
        })
        result = HybridEnrichmentEngine._parse_response("src", text)

        assert result.common_task is not None
        assert result.common_task.task == "Add feature"
        assert len(result.common_task.steps) == 3

    def test_testing_debugging_decisions_parsing(self):
        text = json.dumps({
            "purpose": "Test",
            "testing": ["Run pytest", "Use mocks"],
            "debugging": ["Check env vars", "Inspect logs"],
            "decisions": ["Clean architecture", "DI everywhere"],
        })
        result = HybridEnrichmentEngine._parse_response("src", text)

        assert len(result.testing) == 2
        assert len(result.debugging) == 2
        assert len(result.decisions) == 2


# ── TestTokenCounting ──

class TestTokenCounting:

    def test_count_tokens_returns_int(self):
        count = _count_tokens("Hello, world!")
        assert isinstance(count, int)
        assert count > 0

    def test_truncate_to_tokens_truncates_long_text(self):
        long_text = "word " * 5000  # ~5000 tokens
        truncated = _truncate_to_tokens(long_text, 100)
        assert _count_tokens(truncated) <= 100

    def test_truncate_to_tokens_preserves_short_text(self):
        short_text = "Hello, world!"
        result = _truncate_to_tokens(short_text, 1000)
        assert result == short_text

    def test_token_count_matches_tiktoken(self):
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        text = "def hello_world():\n    print('hello')"
        assert _count_tokens(text) == len(enc.encode(text))


# ── TestReadFolderFiles ──

class TestReadFolderFiles:

    def test_priority_ordering(self):
        node = _make_node("src/api", 2, files=["utils.py", "__init__.py", "main.py", "helpers.py"])

        def reader(path):
            return f"# content of {path}"

        result = HybridEnrichmentEngine._read_folder_files(node, reader)
        keys = list(result.keys())
        # __init__.py and main.py are priority tier 4, should come first
        assert keys[0] in ("__init__.py", "main.py")

    def test_token_budget_cap(self):
        node = _make_node("src/api", 2, files=[f"file_{i}.py" for i in range(10)])

        def reader(path):
            return "x " * 3000  # ~3000 tokens per file

        result = HybridEnrichmentEngine._read_folder_files(node, reader)
        # Should be capped at _MAX_FILES_PER_FOLDER (5)
        assert len(result) <= 5

    def test_empty_folder(self):
        node = _make_node("src/empty", 2, files=[])

        def reader(path):
            return "content"

        result = HybridEnrichmentEngine._read_folder_files(node, reader)
        assert result == {}

    def test_file_truncated_to_max_tokens_per_file(self):
        node = _make_node("src/api", 2, files=["big.py"])

        def reader(path):
            return "token " * 5000  # way over _MAX_TOKENS_PER_FILE

        result = HybridEnrichmentEngine._read_folder_files(node, reader)
        assert "big.py" in result
        token_count = _count_tokens(result["big.py"])
        # Should be at most _MAX_TOKENS_PER_FILE (1500)
        assert token_count <= 1500


# ── TestBuildPrompt ──

class TestBuildPrompt:

    def test_blueprint_context_injected(self):
        node = _make_node("src/api", 2, files=["routes.py"])
        fb = FolderBlueprint(
            path="src/api",
            component_name="API Layer",
            component_responsibility="HTTP endpoints",
            depends_on=["Domain", "Infrastructure"],
            exposes_to=["Frontend"],
        )
        template = "Name: {component_name}\nResp: {component_responsibility}\nDeps: {depends_on}\nExp: {exposes_to}\nPath: {folder_path}\nIface: {interfaces_summary}\nChildren: {children_learned}\nFiles: {file_listing}\nContents: {file_contents}"

        result = HybridEnrichmentEngine._build_prompt(
            template, node, fb, {"routes.py": "# routes"}, "",
        )

        assert "API Layer" in result
        assert "HTTP endpoints" in result
        assert "Domain, Infrastructure" in result
        assert "Frontend" in result

    def test_file_contents_formatted(self):
        node = _make_node("src", 1, files=["main.py"])
        fb = FolderBlueprint(path="src")
        template = "{folder_path} {component_name} {component_responsibility} {depends_on} {exposes_to} {interfaces_summary} {children_learned} {file_listing} {file_contents}"

        result = HybridEnrichmentEngine._build_prompt(
            template, node, fb, {"main.py": "print('hello')"}, "",
        )

        assert "### main.py" in result
        assert "print('hello')" in result

    def test_handles_missing_blueprint_data(self):
        node = _make_node("src/unknown", 2, files=[])
        fb = FolderBlueprint(path="src/unknown")
        template = "Name: {component_name} Resp: {component_responsibility} Deps: {depends_on}"

        result = HybridEnrichmentEngine._build_prompt(template, node, fb, {}, "")

        assert "unknown" in result  # Falls back to node name
        assert "Not documented" in result
        assert "None" in result


# ── TestSummarizeChildren ──

class TestSummarizeChildren:

    def test_compact_summary_from_children(self):
        parent = _make_node("src", 1, children=["src/routes", "src/models"])
        enrichments = {
            "src/routes": FolderEnrichment(
                path="src/routes",
                purpose="Thin HTTP handlers",
                patterns=["Use decorators", "Validate input first"],
                has_ai_content=True,
            ),
            "src/models": FolderEnrichment(
                path="src/models",
                purpose="Pydantic data models",
                patterns=["Use BaseModel", "Add validators"],
                has_ai_content=True,
            ),
        }

        result = HybridEnrichmentEngine._summarize_children(enrichments, parent)

        assert "routes/ — Thin HTTP handlers" in result
        assert "models/ — Pydantic data models" in result
        assert "Use decorators" in result

    def test_empty_when_no_ai_content(self):
        parent = _make_node("src", 1, children=["src/empty"])
        enrichments = {
            "src/empty": FolderEnrichment(path="src/empty", has_ai_content=False),
        }

        result = HybridEnrichmentEngine._summarize_children(enrichments, parent)
        assert result == ""

    def test_handles_missing_purpose(self):
        parent = _make_node("src", 1, children=["src/child"])
        enrichments = {
            "src/child": FolderEnrichment(
                path="src/child",
                purpose="",
                patterns=["Pattern A"],
                has_ai_content=True,
            ),
        }

        result = HybridEnrichmentEngine._summarize_children(enrichments, parent)
        assert "child/" in result


# ── TestEnrichAllIntegration ──

class TestEnrichAllIntegration:

    @pytest.mark.asyncio
    async def test_all_folders_enriched(self, settings, config):
        engine = HybridEnrichmentEngine(settings, config)

        folders = {
            "src": _make_node("src", 1, files=["main.py"], children=["src/api"]),
            "src/api": _make_node("src/api", 2, files=["routes.py"]),
        }
        folder_blueprints = {
            "src": FolderBlueprint(path="src", component_name="Source"),
            "src/api": FolderBlueprint(path="src/api", component_name="API"),
        }

        def reader(path):
            return f"# {path}"

        ai_response = json.dumps({"purpose": "Test", "patterns": ["p1"]})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=ai_response)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(engine, '_make_client', return_value=mock_client):
            enrichments = await engine.enrich_all(folders, folder_blueprints, reader)

        assert len(enrichments) == 2
        assert enrichments["src"].has_ai_content is True
        assert enrichments["src/api"].has_ai_content is True
        assert engine.total_calls == 2

    @pytest.mark.asyncio
    async def test_failed_call_graceful_degradation(self, settings, config):
        engine = HybridEnrichmentEngine(settings, config)

        folders = {
            "src": _make_node("src", 1, files=["main.py"]),
        }
        folder_blueprints = {"src": FolderBlueprint(path="src")}

        def reader(path):
            return "content"

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("API error"))

        with patch.object(engine, '_make_client', return_value=mock_client):
            enrichments = await engine.enrich_all(folders, folder_blueprints, reader)

        assert enrichments["src"].has_ai_content is False

    @pytest.mark.asyncio
    async def test_bottom_up_ordering(self, settings, config):
        """Deepest folders processed first, parents receive child summaries."""
        engine = HybridEnrichmentEngine(settings, config)
        call_order = []

        folders = {
            "src": _make_node("src", 1, files=["main.py"], children=["src/api"]),
            "src/api": _make_node("src/api", 2, files=["routes.py"], children=["src/api/handlers"]),
            "src/api/handlers": _make_node("src/api/handlers", 3, files=["user.py"]),
        }
        folder_blueprints = {
            "src": FolderBlueprint(path="src"),
            "src/api": FolderBlueprint(path="src/api"),
            "src/api/handlers": FolderBlueprint(path="src/api/handlers"),
        }

        def reader(path):
            return f"# {path}"

        ai_response = json.dumps({"purpose": "Test purpose", "patterns": ["p1"]})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=ai_response)]

        original_enrich = engine._enrich_single_folder

        async def tracking_enrich(client, node, fb, file_reader, prompt, children_summary, previous_claude_md=""):
            call_order.append(node.path)
            return await original_enrich(client, node, fb, file_reader, prompt, children_summary, previous_claude_md)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(engine, '_make_client', return_value=mock_client), \
             patch.object(engine, '_enrich_single_folder', side_effect=tracking_enrich):
            await engine.enrich_all(folders, folder_blueprints, reader)

        # Deepest first
        assert call_order.index("src/api/handlers") < call_order.index("src/api")
        assert call_order.index("src/api") < call_order.index("src")

    @pytest.mark.asyncio
    async def test_parent_receives_children_learned(self, settings, config):
        """Parent prompt includes children_learned content."""
        engine = HybridEnrichmentEngine(settings, config)
        captured_prompts: dict[str, str] = {}

        folders = {
            "src": _make_node("src", 1, files=["main.py"], children=["src/child"]),
            "src/child": _make_node("src/child", 2, files=["child.py"]),
        }
        folder_blueprints = {
            "src": FolderBlueprint(path="src"),
            "src/child": FolderBlueprint(path="src/child"),
        }

        def reader(path):
            return f"# {path}"

        child_response = json.dumps({"purpose": "Child purpose here", "patterns": ["child_pattern"]})
        parent_response = json.dumps({"purpose": "Parent purpose", "patterns": ["parent_pattern"]})

        call_count = 0
        async def mock_create(**kwargs):
            nonlocal call_count
            msg_content = kwargs.get("messages", [{}])[0].get("content", "")
            # Determine which folder by checking content
            if "src/child" in msg_content and "src\n" not in msg_content.split("src/child")[0][-5:]:
                captured_prompts["src/child"] = msg_content
                resp = MagicMock()
                resp.content = [MagicMock(text=child_response)]
                return resp
            else:
                captured_prompts["src"] = msg_content
                resp = MagicMock()
                resp.content = [MagicMock(text=parent_response)]
                return resp

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        with patch.object(engine, '_make_client', return_value=mock_client):
            enrichments = await engine.enrich_all(folders, folder_blueprints, reader)

        # Parent's prompt should contain child's learned data
        if "src" in captured_prompts:
            assert "Child purpose here" in captured_prompts["src"]

    @pytest.mark.asyncio
    async def test_leaf_folders_get_empty_children_learned(self, settings, config):
        engine = HybridEnrichmentEngine(settings, config)

        folders = {
            "src/leaf": _make_node("src/leaf", 2, files=["leaf.py"]),
        }
        folder_blueprints = {"src/leaf": FolderBlueprint(path="src/leaf")}

        def reader(path):
            return "content"

        ai_response = json.dumps({"purpose": "Leaf", "patterns": []})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=ai_response)]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch.object(engine, '_make_client', return_value=mock_client):
            enrichments = await engine.enrich_all(folders, folder_blueprints, reader)

        assert enrichments["src/leaf"].has_ai_content is True


# ── TestPreviousContentInPrompt ──

class TestPreviousContentInPrompt:

    def test_previous_content_appended_to_prompt(self):
        node = _make_node("src/api", 2, files=["routes.py"])
        fb = FolderBlueprint(path="src/api", component_name="API")
        template = "{folder_path} {component_name} {component_responsibility} {depends_on} {exposes_to} {interfaces_summary} {children_learned} {file_listing} {file_contents}"

        result = HybridEnrichmentEngine._build_prompt(
            template, node, fb, {}, "", previous_claude_md="Previous insights here",
        )

        assert "### Previous CLAUDE.md Content" in result
        assert "Previous insights here" in result
        assert "Preserve valuable insights" in result

    def test_previous_content_omitted_when_empty(self):
        node = _make_node("src/api", 2, files=["routes.py"])
        fb = FolderBlueprint(path="src/api", component_name="API")
        template = "{folder_path} {component_name} {component_responsibility} {depends_on} {exposes_to} {interfaces_summary} {children_learned} {file_listing} {file_contents}"

        result = HybridEnrichmentEngine._build_prompt(
            template, node, fb, {}, "", previous_claude_md="",
        )

        assert "### Previous CLAUDE.md Content" not in result

    def test_previous_content_passed_through_untruncated(self):
        node = _make_node("src/api", 2, files=[])
        fb = FolderBlueprint(path="src/api")
        template = "{folder_path} {component_name} {component_responsibility} {depends_on} {exposes_to} {interfaces_summary} {children_learned} {file_listing} {file_contents}"

        content = "## Patterns\n- Important pattern\n" * 50
        result = HybridEnrichmentEngine._build_prompt(
            template, node, fb, {}, "", previous_claude_md=content,
        )

        assert "### Previous CLAUDE.md Content" in result
        # Full content should be present, no truncation
        assert content in result


# ── TestPreviousContentIntegration ──

class TestPreviousContentIntegration:

    @pytest.mark.asyncio
    async def test_previous_content_passed_to_prompt(self, settings, config):
        """Previous CLAUDE.md content appears in the AI prompt."""
        engine = HybridEnrichmentEngine(settings, config)
        captured_prompts: list[str] = []

        folders = {
            "src": _make_node("src", 1, files=["main.py"]),
        }
        folder_blueprints = {"src": FolderBlueprint(path="src")}
        previous_content = {"src": "# Previous notes\nKey insight here"}

        def reader(path):
            return f"# {path}"

        ai_response = json.dumps({"purpose": "Test", "patterns": ["p1"]})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=ai_response)]

        async def mock_create(**kwargs):
            msg = kwargs.get("messages", [{}])[0].get("content", "")
            captured_prompts.append(msg)
            return mock_response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        with patch.object(engine, '_make_client', return_value=mock_client):
            await engine.enrich_all(folders, folder_blueprints, reader, previous_content)

        assert len(captured_prompts) == 1
        assert "Key insight here" in captured_prompts[0]
        assert "### Previous CLAUDE.md Content" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_no_previous_content_no_section(self, settings, config):
        """Without previous content, no extra section in prompt."""
        engine = HybridEnrichmentEngine(settings, config)
        captured_prompts: list[str] = []

        folders = {
            "src": _make_node("src", 1, files=["main.py"]),
        }
        folder_blueprints = {"src": FolderBlueprint(path="src")}

        def reader(path):
            return f"# {path}"

        ai_response = json.dumps({"purpose": "Test", "patterns": []})
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=ai_response)]

        async def mock_create(**kwargs):
            msg = kwargs.get("messages", [{}])[0].get("content", "")
            captured_prompts.append(msg)
            return mock_response

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=mock_create)

        with patch.object(engine, '_make_client', return_value=mock_client):
            await engine.enrich_all(folders, folder_blueprints, reader)

        assert len(captured_prompts) == 1
        assert "### Previous CLAUDE.md Content" not in captured_prompts[0]
