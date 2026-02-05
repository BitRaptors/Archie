"""Agent file generator service for creating CLAUDE.md and Cursor rules."""
import logging
from datetime import datetime, timezone
from typing import Any

from anthropic import AsyncAnthropic

from domain.entities.architecture_rule import ArchitectureRule
from domain.entities.resolved_architecture import ResolvedArchitecture
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class AgentFileGenerator:
    """Generates instruction files for AI coding agents.
    
    Creates:
    - CLAUDE.md for Claude/general AI agents
    - .cursor/rules/architecture.md for Cursor IDE
    - AGENTS.md for multi-agent systems
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None = None,
        prompt_loader: PromptLoader | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize generator.
        
        Args:
            ai_client: Optional Anthropic client for AI-enhanced generation
            prompt_loader: Loader for prompts
            model: AI model to use
        """
        self._ai_client = ai_client
        self._prompt_loader = prompt_loader
        self._model = model
    
    async def generate_claude_md(
        self,
        repository_id: str,
        repository_name: str,
        architecture: ResolvedArchitecture,
    ) -> str:
        """Generate CLAUDE.md content.
        
        Args:
            repository_id: Repository ID
            repository_name: Human-readable repository name
            architecture: Resolved architecture rules
            
        Returns:
            CLAUDE.md content as string
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Try AI-enhanced generation if available
        if self._ai_client and self._prompt_loader:
            ai_content = await self._generate_with_ai(
                "worker_generate_claude_md",
                repository_name=repository_name,
                repository_id=repository_id,
                architecture_rules=self._format_rules_for_prompt(architecture.rules),
                timestamp=timestamp,
            )
            if ai_content:
                return ai_content
        
        # Fallback to template-based generation
        return self._generate_claude_md_template(
            repository_id=repository_id,
            repository_name=repository_name,
            architecture=architecture,
            timestamp=timestamp,
        )
    
    async def generate_cursor_rules(
        self,
        repository_name: str,
        architecture: ResolvedArchitecture,
    ) -> str:
        """Generate .cursor/rules/architecture.md content.
        
        Args:
            repository_name: Repository name
            architecture: Resolved architecture rules
            
        Returns:
            Cursor rules content
        """
        # Try AI-enhanced generation
        if self._ai_client and self._prompt_loader:
            ai_content = await self._generate_with_ai(
                "worker_generate_cursor_rules",
                repository_name=repository_name,
                architecture_rules=self._format_rules_for_prompt(architecture.rules),
            )
            if ai_content:
                return ai_content
        
        # Fallback to template
        return self._generate_cursor_rules_template(
            repository_name=repository_name,
            architecture=architecture,
        )
    
    async def generate_agents_md(
        self,
        repository_name: str,
        architecture: ResolvedArchitecture,
    ) -> str:
        """Generate AGENTS.md content for multi-agent systems.
        
        Args:
            repository_name: Repository name
            architecture: Resolved architecture rules
            
        Returns:
            AGENTS.md content
        """
        return self._generate_agents_md_template(
            repository_name=repository_name,
            architecture=architecture,
        )
    
    async def _generate_with_ai(
        self,
        prompt_key: str,
        **variables: Any,
    ) -> str | None:
        """Generate content using AI.
        
        Args:
            prompt_key: Key for prompt in prompts.json
            **variables: Variables for prompt template
            
        Returns:
            Generated content or None
        """
        if not self._ai_client or not self._prompt_loader:
            return None
        
        try:
            prompt_template = self._prompt_loader.get_prompt_by_key(prompt_key)
            if not prompt_template:
                return None
            
            if hasattr(prompt_template, 'render'):
                prompt = prompt_template.render(variables)
            else:
                prompt = str(prompt_template).format(**variables)
            
            response = await self._ai_client.messages.create(
                model=self._model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.warning(f"AI generation failed: {e}")
            return None
    
    def _format_rules_for_prompt(self, rules: list[ArchitectureRule]) -> str:
        """Format rules for inclusion in a prompt.
        
        Args:
            rules: Architecture rules
            
        Returns:
            Formatted string
        """
        import json
        
        formatted = []
        for rule in rules[:50]:  # Limit to avoid token overflow
            formatted.append({
                "rule_type": rule.rule_type,
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "rule_data": rule.rule_data,
            })
        
        return json.dumps(formatted, indent=2)
    
    def _generate_claude_md_template(
        self,
        repository_id: str,
        repository_name: str,
        architecture: ResolvedArchitecture,
        timestamp: str,
    ) -> str:
        """Generate CLAUDE.md using template.
        
        Args:
            repository_id: Repository ID
            repository_name: Repository name
            architecture: Resolved architecture
            timestamp: Generation timestamp
            
        Returns:
            CLAUDE.md content
        """
        lines = [
            "# CLAUDE.md",
            "",
            "> Auto-generated architecture guidance for AI coding agents.",
            f"> Repository: {repository_name}",
            f"> Last updated: {timestamp}",
            "",
            "## Architecture Overview",
            "",
            f"This repository has **{len(architecture.rules)}** architecture rules derived from analysis.",
            f"- Learned rules: {architecture.learned_rules_count}",
            f"- Reference rules: {architecture.reference_rules_count}",
            f"- Merge strategy: {architecture.get_merge_strategy()}",
            "",
        ]
        
        # File Organization
        location_rules = architecture.get_rules_by_type("location")
        if location_rules:
            lines.extend([
                "## File Organization",
                "",
                "| Location | Purpose |",
                "|----------|---------|",
            ])
            for rule in location_rules[:15]:
                path = rule.rule_data.get("path", "")
                purpose = rule.rule_data.get("purpose", rule.description or "")[:50]
                lines.append(f"| `{path}` | {purpose} |")
            lines.append("")
        
        # Dependency Rules
        dep_rules = architecture.get_dependency_rules()
        layer_rules = architecture.get_layer_rules()
        
        if dep_rules or layer_rules:
            lines.extend([
                "## Dependency Rules",
                "",
            ])
            
            # Extract allowed/forbidden from rules
            allowed = []
            forbidden = []
            
            for rule in dep_rules + layer_rules:
                rule_data = rule.rule_data
                allowed.extend(rule_data.get("allowed_imports", []))
                forbidden.extend(rule_data.get("forbidden_imports", []))
                
                # Layer dependencies
                if rule.rule_type == "layer":
                    depends_on = rule_data.get("depends_on", [])
                    if depends_on:
                        allowed.append(f"{rule.name} can import from: {', '.join(depends_on)}")
            
            if allowed:
                lines.append("### Allowed")
                for item in allowed[:10]:
                    lines.append(f"- {item}")
                lines.append("")
            
            if forbidden:
                lines.append("### Forbidden")
                for item in forbidden[:10]:
                    lines.append(f"- {item}")
                lines.append("")
        
        # Conventions
        convention_rules = architecture.get_convention_rules()
        if convention_rules:
            lines.extend([
                "## Naming Conventions",
                "",
            ])
            for rule in convention_rules[:10]:
                pattern = rule.rule_data.get("pattern", rule.description or rule.name)
                lines.append(f"- {pattern}")
            lines.append("")
        
        # Boundaries
        boundary_rules = architecture.get_boundary_rules()
        if boundary_rules:
            lines.extend([
                "## Component Boundaries",
                "",
            ])
            for rule in boundary_rules[:10]:
                boundary = rule.rule_data.get("boundary", "")
                relationship = rule.rule_data.get("relationship", rule.description or "")
                if boundary or relationship:
                    lines.append(f"- {boundary}: {relationship}")
            lines.append("")
        
        # Before You Code section
        lines.extend([
            "## Before You Code",
            "",
            "When adding new code:",
            "",
            "1. Check the File Organization section to find the correct location",
            "2. Review the Dependency Rules to understand what you can import",
            "3. Follow the Naming Conventions for consistent naming",
            "4. Respect Component Boundaries to maintain separation of concerns",
            "",
            "## MCP Tools Available",
            "",
            "This repository has architecture tools available via MCP:",
            "",
            "- `get_architecture_for_repo` - Get full architecture rules",
            "- `validate_code` - Validate code before committing",
            "- `check_file_location` - Verify file placement",
            "- `get_implementation_guide` - Get implementation guidance",
            "",
            "---",
            "*This file is auto-generated. Do not edit manually.*",
        ])
        
        return "\n".join(lines)
    
    def _generate_cursor_rules_template(
        self,
        repository_name: str,
        architecture: ResolvedArchitecture,
    ) -> str:
        """Generate Cursor rules using template.
        
        Args:
            repository_name: Repository name
            architecture: Resolved architecture
            
        Returns:
            Cursor rules content
        """
        # Determine file globs based on rules
        globs = set()
        for rule in architecture.rules:
            if rule.rule_data:
                path = rule.rule_data.get("path", "")
                if path:
                    if path.endswith("/"):
                        globs.add(f"{path}**/*")
                    else:
                        globs.add(path)
        
        if not globs:
            globs = {"**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"}
        
        globs_str = ", ".join(f'"{g}"' for g in sorted(list(globs))[:10])
        
        lines = [
            "---",
            f"description: Architecture rules for {repository_name}",
            f"globs: [{globs_str}]",
            "---",
            "",
            "# Architecture Rules",
            "",
            "## Overview",
            "",
            f"This codebase has {len(architecture.rules)} architecture rules.",
            "",
        ]
        
        # File structure
        location_rules = architecture.get_rules_by_type("location")
        if location_rules:
            lines.extend([
                "## File Structure",
                "",
            ])
            for rule in location_rules[:10]:
                path = rule.rule_data.get("path", "")
                purpose = rule.rule_data.get("purpose", "")[:80]
                lines.append(f"- `{path}`: {purpose}")
            lines.append("")
        
        # Dependencies
        dep_rules = architecture.get_dependency_rules()
        if dep_rules:
            lines.extend([
                "## Dependencies",
                "",
            ])
            for rule in dep_rules[:10]:
                imports = rule.rule_data.get("imports", [])
                if imports:
                    lines.append(f"- {rule.name}: imports {', '.join(imports[:5])}")
            lines.append("")
        
        # Patterns
        pattern_rules = architecture.get_pattern_rules()
        if pattern_rules:
            lines.extend([
                "## Patterns",
                "",
            ])
            for rule in pattern_rules[:10]:
                lines.append(f"- **{rule.name}**: {(rule.description or '')[:100]}")
            lines.append("")
        
        # Anti-patterns
        anti_rules = architecture.get_rules_by_type("anti_pattern")
        if anti_rules:
            lines.extend([
                "## Anti-Patterns",
                "",
            ])
            for rule in anti_rules[:10]:
                lines.append(f"- {rule.description or rule.name}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _generate_agents_md_template(
        self,
        repository_name: str,
        architecture: ResolvedArchitecture,
    ) -> str:
        """Generate AGENTS.md using template.
        
        Args:
            repository_name: Repository name
            architecture: Resolved architecture
            
        Returns:
            AGENTS.md content
        """
        lines = [
            "# AGENTS.md",
            "",
            f"Multi-agent architecture guidance for {repository_name}.",
            "",
            "## Agent Roles",
            "",
            "### Analysis Agent",
            "- Scans codebase and extracts architecture rules",
            "- Uses pure observation (no predefined patterns)",
            "- Outputs structured rules to database",
            "",
            "### Validation Agent",
            "- Validates code changes against architecture",
            "- Reports violations with suggested fixes",
            "- Integrates with CI/CD pipelines",
            "",
            "### Sync Agent",
            "- Detects changes since last analysis",
            "- Recommends full re-analysis vs incremental updates",
            "- Tracks affected rules",
            "",
            "## Architecture Summary",
            "",
            f"- Total rules: {len(architecture.rules)}",
            f"- Learned: {architecture.learned_rules_count}",
            f"- Reference: {architecture.reference_rules_count}",
            "",
            "## Key Rules for Agents",
            "",
        ]
        
        # Add most important rules
        for rule in architecture.rules[:20]:
            lines.append(f"- **{rule.rule_type}**: {rule.name}")
        
        lines.extend([
            "",
            "---",
            "*Auto-generated from architecture analysis.*",
        ])
        
        return "\n".join(lines)
