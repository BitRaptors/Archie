"""Tests for FolderHierarchyBuilder and file prioritization."""
import pytest
from domain.entities.intent_layer import FolderNode, IntentLayerConfig
from application.services.intent_layer_service import FolderHierarchyBuilder
from application.services.intent_layer_generator import prioritize_files, AncestorCodeChain


class TestBuildFromFileTree:

    def test_basic_tree(self):
        file_tree = [
            {"name": "main.py", "path": "src/main.py", "type": "file", "size": 100, "extension": "py"},
            {"name": "utils.py", "path": "src/utils.py", "type": "file", "size": 50, "extension": "py"},
            {"name": "README.md", "path": "README.md", "type": "file", "size": 200, "extension": "md"},
        ]
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)

        assert "" in nodes  # root
        assert "src" in nodes
        assert nodes["src"].files == ["main.py", "utils.py"]
        assert nodes["src"].depth == 1

    def test_nested_tree(self):
        file_tree = [
            {"name": "routes.py", "path": "src/api/routes.py", "type": "file", "size": 100, "extension": "py"},
            {"name": "models.py", "path": "src/domain/models.py", "type": "file", "size": 100, "extension": "py"},
        ]
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)

        assert "src/api" in nodes
        assert "src/domain" in nodes
        assert nodes["src/api"].depth == 2
        assert nodes["src/api"].parent_path == "src"

    def test_root_always_exists(self):
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree([])
        assert "" in nodes

    def test_children_wired(self):
        file_tree = [
            {"name": "a.py", "path": "src/a.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "b.py", "path": "src/sub/b.py", "type": "file", "size": 10, "extension": "py"},
        ]
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)

        assert "src/sub" in nodes["src"].children

    def test_recursive_file_count(self):
        file_tree = [
            {"name": "a.py", "path": "src/a.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "b.py", "path": "src/sub/b.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "c.py", "path": "src/sub/c.py", "type": "file", "size": 10, "extension": "py"},
        ]
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)

        assert nodes["src"].file_count == 3  # 1 direct + 2 in sub
        assert nodes["src/sub"].file_count == 2

    def test_excluded_dirs_filtered(self):
        file_tree = [
            {"name": "a.py", "path": "src/a.py", "type": "file", "size": 10, "extension": "py"},
            {"name": "b.js", "path": "node_modules/pkg/b.js", "type": "file", "size": 10, "extension": "js"},
        ]
        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_file_tree(file_tree)

        assert "node_modules" not in nodes
        assert "node_modules/pkg" not in nodes


class TestBuildFromPath:

    def test_basic_directory(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("code")
        (tmp_path / "README.md").write_text("readme")

        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_path(tmp_path)

        assert "" in nodes
        assert "src" in nodes
        assert "main.py" in nodes["src"].files

    def test_skips_hidden_and_ignored(self, tmp_path):
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "HEAD").write_text("ref")
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "x.js").write_text("x")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "app.py").write_text("app")

        builder = FolderHierarchyBuilder()
        nodes = builder.build_from_path(tmp_path)

        assert ".git" not in nodes
        assert "node_modules" not in nodes
        assert "src" in nodes


class TestFilterSignificant:

    def test_filters_below_min_files(self):
        config = IntentLayerConfig(min_files=3, max_depth=10)
        builder = FolderHierarchyBuilder(config)

        nodes = {
            "": FolderNode(path="", name="root", depth=0, file_count=10),
            "src": FolderNode(path="src", name="src", depth=1, file_count=5),
            "docs": FolderNode(path="docs", name="docs", depth=1, file_count=1),  # Below threshold
        }
        result = builder.filter_significant(nodes)

        assert "" in result  # Root always kept
        assert "src" in result
        assert "docs" not in result

    def test_filters_beyond_max_depth(self):
        config = IntentLayerConfig(min_files=1, max_depth=2)
        builder = FolderHierarchyBuilder(config)

        nodes = {
            "": FolderNode(path="", name="root", depth=0, file_count=10),
            "a": FolderNode(path="a", name="a", depth=1, file_count=5),
            "a/b": FolderNode(path="a/b", name="b", depth=2, file_count=3),
            "a/b/c": FolderNode(path="a/b/c", name="c", depth=3, file_count=2),  # Beyond max_depth
        }
        result = builder.filter_significant(nodes)

        assert "a/b" in result
        assert "a/b/c" not in result

    def test_root_always_kept(self):
        config = IntentLayerConfig(min_files=100)
        builder = FolderHierarchyBuilder(config)

        nodes = {"": FolderNode(path="", name="root", depth=0, file_count=1)}
        result = builder.filter_significant(nodes)

        assert "" in result


class TestGroupByDepth:

    def test_groups_correctly(self):
        builder = FolderHierarchyBuilder()
        nodes = {
            "": FolderNode(path="", name="root", depth=0),
            "src": FolderNode(path="src", name="src", depth=1),
            "tests": FolderNode(path="tests", name="tests", depth=1),
            "src/api": FolderNode(path="src/api", name="api", depth=2),
        }
        groups = builder.group_by_depth(nodes)

        assert len(groups[0]) == 1
        assert len(groups[1]) == 2
        assert len(groups[2]) == 1

    def test_sorted_within_depth(self):
        builder = FolderHierarchyBuilder()
        nodes = {
            "z": FolderNode(path="z", name="z", depth=1),
            "a": FolderNode(path="a", name="a", depth=1),
            "m": FolderNode(path="m", name="m", depth=1),
        }
        groups = builder.group_by_depth(nodes)

        paths = [n.path for n in groups[1]]
        assert paths == ["a", "m", "z"]


class TestBatchSiblings:

    def test_batches_by_parent(self):
        nodes = [
            FolderNode(path="src/a", name="a", depth=2, parent_path="src"),
            FolderNode(path="src/b", name="b", depth=2, parent_path="src"),
            FolderNode(path="tests/x", name="x", depth=2, parent_path="tests"),
        ]
        batches = FolderHierarchyBuilder.batch_siblings(nodes, batch_size=4)

        assert len(batches) == 2  # src siblings + tests siblings

    def test_respects_batch_size(self):
        nodes = [
            FolderNode(path=f"src/{chr(97+i)}", name=chr(97+i), depth=2, parent_path="src")
            for i in range(7)
        ]
        batches = FolderHierarchyBuilder.batch_siblings(nodes, batch_size=3)

        assert len(batches) == 3  # 3 + 3 + 1
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1

    def test_empty_input(self):
        batches = FolderHierarchyBuilder.batch_siblings([], batch_size=4)
        assert batches == []


class TestAncestorCodeChain:
    """AncestorCodeChain now lives in intent_layer_generator.py."""

    def test_immutability(self):
        """add_entry returns a NEW chain, original unchanged."""
        chain = AncestorCodeChain()
        new_chain = chain.add_entry("src", {"src/app.py": "code"})

        assert len(chain.entries) == 0
        assert chain.total_chars == 0
        assert len(new_chain.entries) == 1
        assert new_chain.total_chars == 4

    def test_accumulation(self):
        """Chaining add_entry builds up entries root-first."""
        chain = AncestorCodeChain()
        chain = chain.add_entry("", {"README.md": "hello"})
        chain = chain.add_entry("src", {"src/main.py": "import os"})
        chain = chain.add_entry("src/api", {"src/api/app.py": "from fastapi"})

        assert len(chain.entries) == 3
        assert chain.entries[0].folder_path == ""
        assert chain.entries[1].folder_path == "src"
        assert chain.entries[2].folder_path == "src/api"
        assert chain.total_chars == len("hello") + len("import os") + len("from fastapi")

    def test_format_for_prompt_within_budget(self):
        """When budget is large, all ancestor code is included with full content."""
        chain = AncestorCodeChain()
        chain = chain.add_entry("src", {"src/app.py": "app code"})
        chain = chain.add_entry("src/api", {"src/api/routes.py": "routes code"})

        result = chain.format_for_prompt(budget_chars=100_000)
        assert "app code" in result
        assert "routes code" in result
        assert "src/" in result
        assert "src/api/" in result

    def test_format_for_prompt_tight_budget(self):
        """When budget is tight, old ancestors get file listings only."""
        chain = AncestorCodeChain()
        chain = chain.add_entry("src", {"src/app.py": "x" * 1000})
        chain = chain.add_entry("src/api", {"src/api/routes.py": "y" * 500})

        # Budget only fits the most recent ancestor's code
        result = chain.format_for_prompt(budget_chars=600)
        # Most recent (src/api) gets full code
        assert "y" * 500 in result
        # Older (src) gets file listing only
        assert "src/app.py" in result
        assert "x" * 1000 not in result

    def test_empty_chain(self):
        """Empty chain returns descriptive message."""
        chain = AncestorCodeChain()
        result = chain.format_for_prompt(budget_chars=10_000)
        assert "No ancestor code context" in result

    def test_total_chars_tracking(self):
        """total_chars accurately tracks cumulative size."""
        chain = AncestorCodeChain()
        chain = chain.add_entry("a", {"a/x.py": "abc"})      # 3 chars
        assert chain.total_chars == 3
        chain = chain.add_entry("b", {"b/y.py": "defgh"})    # 5 chars
        assert chain.total_chars == 8


class TestPrioritizeFiles:

    def test_init_files_first(self):
        """__init__.py, app.py, main.py come before generic files."""
        files = ["utils.py", "helpers.py", "__init__.py", "app.py"]
        result = prioritize_files(files)
        assert result[0] == "__init__.py"
        assert result[1] == "app.py"

    def test_config_before_generic(self):
        """Config/settings files come before generic files but after init/app."""
        files = ["utils.py", "config.py", "main.py", "helpers.py"]
        result = prioritize_files(files)
        assert result[0] == "main.py"       # Tier 4
        assert result[1] == "config.py"     # Tier 3
        # Generic files after
        assert "utils.py" in result[2:]
        assert "helpers.py" in result[2:]

    def test_tier0_alphabetical(self):
        """Files with no priority tier are sorted alphabetically."""
        files = ["zebra.py", "alpha.py", "mango.py"]
        result = prioritize_files(files)
        assert result == ["alpha.py", "mango.py", "zebra.py"]
