"""Tests for AgentFileGenerator."""
import pytest
from unittest.mock import AsyncMock


class TestAgentFileGenerator:
    """Tests for agent file generator functionality."""
    
    @pytest.fixture
    def generator(self, mock_ai_client, mock_prompt_loader):
        """Create generator instance."""
        from application.services.agent_file_generator import AgentFileGenerator
        return AgentFileGenerator(
            ai_client=mock_ai_client,
            prompt_loader=mock_prompt_loader,
        )
    
    @pytest.fixture
    def generator_no_ai(self):
        """Create generator without AI client."""
        from application.services.agent_file_generator import AgentFileGenerator
        return AgentFileGenerator(ai_client=None, prompt_loader=None)
    
    @pytest.mark.asyncio
    async def test_generate_claude_md(self, generator_no_ai, sample_resolved_architecture):
        """Verify CLAUDE.md generation."""
        content = await generator_no_ai.generate_claude_md(
            repository_id="test-repo-123",
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert content is not None
        assert "# CLAUDE.md" in content
        assert "test/repo" in content
    
    @pytest.mark.asyncio
    async def test_claude_md_includes_rules_count(self, generator_no_ai, sample_resolved_architecture):
        """Verify CLAUDE.md includes rule counts."""
        content = await generator_no_ai.generate_claude_md(
            repository_id="test-repo-123",
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert "rules" in content.lower()
    
    @pytest.mark.asyncio
    async def test_claude_md_includes_mcp_tools(self, generator_no_ai, sample_resolved_architecture):
        """Verify CLAUDE.md mentions MCP tools."""
        content = await generator_no_ai.generate_claude_md(
            repository_id="test-repo-123",
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert "MCP" in content
        assert "get_architecture_for_repo" in content
    
    @pytest.mark.asyncio
    async def test_generate_cursor_rules(self, generator_no_ai, sample_resolved_architecture):
        """Verify Cursor rules generation."""
        content = await generator_no_ai.generate_cursor_rules(
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert content is not None
        assert "---" in content  # YAML frontmatter
        assert "globs:" in content
    
    @pytest.mark.asyncio
    async def test_cursor_rules_includes_globs(self, generator_no_ai, sample_resolved_architecture):
        """Verify Cursor rules includes file globs."""
        content = await generator_no_ai.generate_cursor_rules(
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert "globs:" in content
    
    @pytest.mark.asyncio
    async def test_generate_agents_md(self, generator_no_ai, sample_resolved_architecture):
        """Verify AGENTS.md generation."""
        content = await generator_no_ai.generate_agents_md(
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert content is not None
        assert "# AGENTS.md" in content
        assert "Agent Roles" in content
    
    @pytest.mark.asyncio
    async def test_agents_md_includes_agent_types(self, generator_no_ai, sample_resolved_architecture):
        """Verify AGENTS.md includes all agent types."""
        content = await generator_no_ai.generate_agents_md(
            repository_name="test/repo",
            architecture=sample_resolved_architecture,
        )
        
        assert "Analysis Agent" in content
        assert "Validation Agent" in content
        assert "Sync Agent" in content
    
    def test_format_rules_for_prompt(self, generator_no_ai, sample_architecture_rules):
        """Test rule formatting for prompts."""
        formatted = generator_no_ai._format_rules_for_prompt(sample_architecture_rules)
        
        assert formatted is not None
        assert "rule_type" in formatted
        assert "rule_id" in formatted
