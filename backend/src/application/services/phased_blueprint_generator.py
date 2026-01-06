"""Phased blueprint generator using AI for comprehensive architecture documentation."""
import json
from pathlib import Path
from typing import Any
from anthropic import AsyncAnthropic
from infrastructure.prompts.prompt_loader import PromptLoader
from config.settings import Settings


class PhasedBlueprintGenerator:
    """Generates comprehensive architecture blueprints through phased AI analysis."""

    def __init__(self, settings: Settings):
        """Initialize phased blueprint generator.
        
        Args:
            settings: Application settings for AI configuration
        """
        self._settings = settings
        self._prompt_loader = PromptLoader()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        self._model = settings.default_ai_model

    async def generate(
        self,
        repo_path: Path,
        repository_name: str,
        file_tree: str,
        dependencies: str,
        config_files: dict[str, str],
        code_samples: dict[str, str],
    ) -> str:
        """Generate comprehensive architecture blueprint through phased analysis.
        
        Args:
            repo_path: Path to cloned repository
            repository_name: Name of the repository
            file_tree: Compressed file tree structure
            dependencies: Parsed dependencies (requirements.txt, package.json, etc.)
            config_files: Key configuration files content
            code_samples: Representative code samples from the repository
        
        Returns:
            Complete architecture blueprint markdown document
        """
        if not self._client:
            return self._generate_mock_blueprint(repository_name)
        
        # Phase 1: Discovery
        phase1_result = await self._run_phase1_discovery(
            repository_name=repository_name,
            file_tree=file_tree,
            dependencies=dependencies,
            config_files=config_files,
        )
        
        # Phase 2: Layer Identification
        phase2_result = await self._run_phase2_layers(
            repository_name=repository_name,
            discovery_summary=phase1_result,
            file_tree=file_tree,
            code_samples=code_samples,
        )
        
        # Phase 3: Pattern Extraction
        phase3_result = await self._run_phase3_patterns(
            repository_name=repository_name,
            discovery_summary=phase1_result,
            layer_analysis=phase2_result,
            code_samples=code_samples,
        )
        
        # Phase 4: Communication Analysis
        previous_phases = {
            "discovery": phase1_result,
            "layers": phase2_result,
            "patterns": phase3_result,
        }
        phase4_result = await self._run_phase4_communication(
            repository_name=repository_name,
            previous_phases=json.dumps(previous_phases, indent=2),
            code_samples=code_samples,
        )
        
        # Phase 5: Technology Inventory
        all_phases = {
            "discovery": phase1_result,
            "layers": phase2_result,
            "patterns": phase3_result,
            "communication": phase4_result,
        }
        phase5_result = await self._run_phase5_technology(
            repository_name=repository_name,
            all_phases=json.dumps(all_phases, indent=2),
            dependencies=dependencies,
        )
        
        # Final Synthesis: Generate comprehensive blueprint
        final_blueprint = await self._run_final_synthesis(
            repository_name=repository_name,
            phase1_discovery=phase1_result,
            phase2_layers=phase2_result,
            phase3_patterns=phase3_result,
            phase4_communication=phase4_result,
            phase5_technology=phase5_result,
            code_samples=self._format_code_samples(code_samples),
        )
        
        return final_blueprint

    async def _run_phase1_discovery(
        self,
        repository_name: str,
        file_tree: str,
        dependencies: str,
        config_files: dict[str, str],
    ) -> str:
        """Run Phase 1: Discovery."""
        prompt = self._prompt_loader.get_prompt_by_key("phase1_discovery")
        
        config_files_str = "\n\n".join([
            f"**{filename}:**\n```\n{content[:500]}...\n```"
            for filename, content in config_files.items()
        ])
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "file_tree": file_tree[:2000],  # Limit file tree size
            "dependencies": dependencies[:1000],
            "config_files": config_files_str[:1000],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_phase2_layers(
        self,
        repository_name: str,
        discovery_summary: str,
        file_tree: str,
        code_samples: dict[str, str],
    ) -> str:
        """Run Phase 2: Layer Identification."""
        prompt = self._prompt_loader.get_prompt_by_key("phase2_layers")
        
        code_samples_str = self._format_code_samples(code_samples, limit=5)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1500],
            "file_tree": file_tree[:2000],
            "code_samples": code_samples_str[:3000],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_phase3_patterns(
        self,
        repository_name: str,
        discovery_summary: str,
        layer_analysis: str,
        code_samples: dict[str, str],
    ) -> str:
        """Run Phase 3: Pattern Extraction."""
        prompt = self._prompt_loader.get_prompt_by_key("phase3_patterns")
        
        code_samples_str = self._format_code_samples(code_samples, limit=8)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1000],
            "layer_analysis": layer_analysis[:1500],
            "code_samples": code_samples_str[:4000],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_phase4_communication(
        self,
        repository_name: str,
        previous_phases: str,
        code_samples: dict[str, str],
    ) -> str:
        """Run Phase 4: Communication Analysis."""
        prompt = self._prompt_loader.get_prompt_by_key("phase4_communication")
        
        code_samples_str = self._format_code_samples(code_samples, limit=6)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "previous_phases": previous_phases[:2500],
            "code_samples": code_samples_str[:3000],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_phase5_technology(
        self,
        repository_name: str,
        all_phases: str,
        dependencies: str,
    ) -> str:
        """Run Phase 5: Technology Inventory."""
        prompt = self._prompt_loader.get_prompt_by_key("phase5_technology")
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "all_phases": all_phases[:3000],
            "dependencies": dependencies[:1500],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_final_synthesis(
        self,
        repository_name: str,
        phase1_discovery: str,
        phase2_layers: str,
        phase3_patterns: str,
        phase4_communication: str,
        phase5_technology: str,
        code_samples: str,
    ) -> str:
        """Run Final Synthesis: Generate comprehensive blueprint document."""
        prompt = self._prompt_loader.get_prompt_by_key("final_synthesis")
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "phase1_discovery": phase1_discovery[:2000],
            "phase2_layers": phase2_layers[:2000],
            "phase3_patterns": phase3_patterns[:2000],
            "phase4_communication": phase4_communication[:2000],
            "phase5_technology": phase5_technology[:2000],
            "code_samples": code_samples[:3000],
        })
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4000,  # Large output for comprehensive document
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    def _format_code_samples(self, code_samples: dict[str, str], limit: int = 10) -> str:
        """Format code samples for inclusion in prompts.
        
        Args:
            code_samples: Dictionary of filename -> code content
            limit: Maximum number of samples to include
        
        Returns:
            Formatted string of code samples
        """
        formatted_samples = []
        
        for i, (filename, content) in enumerate(list(code_samples.items())[:limit]):
            # Limit each sample to ~500 lines
            lines = content.split('\n')
            if len(lines) > 500:
                content = '\n'.join(lines[:500]) + '\n... (truncated)'
            
            formatted_samples.append(f"**{filename}:**\n```\n{content}\n```\n")
        
        return "\n".join(formatted_samples)

    def _generate_mock_blueprint(self, repository_name: str) -> str:
        """Generate a mock blueprint when AI client is not available."""
        return f"""# {repository_name} Architecture Blueprint

## Purpose

This is a mock blueprint generated because the AI service is not configured.

## Architecture Overview

Unable to analyze architecture without AI service configuration.

Please configure the Anthropic API key to enable full blueprint generation.
"""

