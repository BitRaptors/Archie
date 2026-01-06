"""Phased blueprint generator using AI for comprehensive architecture documentation."""
import json
from pathlib import Path
from typing import Any
from anthropic import AsyncAnthropic
from infrastructure.prompts.prompt_loader import PromptLoader
from infrastructure.analysis.rag_retriever import RAGRetriever
from config.settings import Settings


class PhasedBlueprintGenerator:
    """Generates comprehensive architecture blueprints through phased AI analysis.
    
    This generator uses a hybrid approach:
    1. RAG-based retrieval: Semantically search entire codebase for relevant code
    2. Structure analysis: Understand overall project organization
    3. Phased AI analysis: Build understanding incrementally across 6 phases
    
    This allows analyzing codebases of ANY size by retrieving only the most
    relevant code for each analysis phase.
    """

    def __init__(self, settings: Settings, supabase_client=None):
        """Initialize phased blueprint generator.
        
        Args:
            settings: Application settings for AI configuration
            supabase_client: Supabase client for RAG retrieval (optional)
        """
        self._settings = settings
        self._prompt_loader = PromptLoader()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        self._model = settings.default_ai_model
        self._rag_retriever = RAGRetriever(supabase_client) if supabase_client else None
        self._supabase_client = supabase_client

    async def generate(
        self,
        repo_path: Path,
        repository_name: str,
        repository_id: str | None = None,
        file_tree: str = "",
        dependencies: str = "",
        config_files: dict[str, str] | None = None,
        code_samples: dict[str, str] | None = None,
    ) -> str:
        """Generate comprehensive architecture blueprint through phased analysis.
        
        Uses RAG-based retrieval to analyze the ENTIRE codebase, not just samples.
        
        Args:
            repo_path: Path to cloned repository
            repository_name: Name of the repository
            repository_id: UUID of the repository (for RAG retrieval)
            file_tree: Compressed file tree structure
            dependencies: Parsed dependencies (requirements.txt, package.json, etc.)
            config_files: Key configuration files content
            code_samples: Fallback code samples if RAG not available
        
        Returns:
            Complete architecture blueprint markdown document
        """
        if not self._client:
            return self._generate_mock_blueprint(repository_name)
        
        config_files = config_files or {}
        code_samples = code_samples or {}
        
        # If RAG is available, index the repository first
        rag_enabled = self._rag_retriever and repository_id
        if rag_enabled:
            try:
                await self._rag_retriever.index_repository(repository_id, repo_path)
            except Exception:
                rag_enabled = False  # Fall back to sample-based analysis
        
        # Phase 1: Discovery - understand project purpose and structure
        phase1_result = await self._run_phase1_discovery(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            file_tree=file_tree,
            dependencies=dependencies,
            config_files=config_files,
            rag_enabled=rag_enabled,
        )
        
        # Phase 2: Layer Identification - identify architectural layers
        phase2_result = await self._run_phase2_layers(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            discovery_summary=phase1_result,
            file_tree=file_tree,
            code_samples=code_samples,
            rag_enabled=rag_enabled,
        )
        
        # Phase 3: Pattern Extraction - identify design patterns
        phase3_result = await self._run_phase3_patterns(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            discovery_summary=phase1_result,
            layer_analysis=phase2_result,
            code_samples=code_samples,
            rag_enabled=rag_enabled,
        )
        
        # Phase 4: Communication Analysis - how components communicate
        previous_phases = {
            "discovery": phase1_result,
            "layers": phase2_result,
            "patterns": phase3_result,
        }
        phase4_result = await self._run_phase4_communication(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            previous_phases=json.dumps(previous_phases, indent=2),
            code_samples=code_samples,
            rag_enabled=rag_enabled,
        )
        
        # Phase 5: Technology Inventory - complete tech stack
        all_phases = {
            "discovery": phase1_result,
            "layers": phase2_result,
            "patterns": phase3_result,
            "communication": phase4_result,
        }
        phase5_result = await self._run_phase5_technology(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            all_phases=json.dumps(all_phases, indent=2),
            dependencies=dependencies,
            rag_enabled=rag_enabled,
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

    async def _retrieve_relevant_code(
        self,
        phase: str,
        repository_id: str,
        repo_path: Path,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Retrieve relevant code chunks for a phase using RAG.
        
        Args:
            phase: Current analysis phase
            repository_id: UUID of the repository
            repo_path: Path to cloned repository
            context: Context from previous phases
            
        Returns:
            Formatted string of relevant code chunks
        """
        if not self._rag_retriever:
            return ""
        
        try:
            chunks = await self._rag_retriever.retrieve_for_phase(
                phase=phase,
                repository_id=repository_id,
                context=context,
            )
            
            if not chunks:
                return ""
            
            # Format chunks with file content
            formatted = []
            for chunk in chunks[:15]:  # Limit to top 15 most relevant
                file_path = chunk["file_path"]
                
                # Get actual file content for the chunk
                content = await self._rag_retriever.get_file_content(
                    repository_id, file_path, repo_path
                )
                
                if content:
                    # Extract relevant lines if we have line info
                    start_line = chunk.get("start_line", 0)
                    end_line = chunk.get("end_line", 0)
                    
                    if start_line and end_line:
                        lines = content.splitlines()
                        chunk_content = '\n'.join(lines[start_line-1:end_line])
                    else:
                        # Limit to 200 lines
                        chunk_content = '\n'.join(content.splitlines()[:200])
                    
                    formatted.append(
                        f"**{file_path}** (lines {start_line}-{end_line}):\n"
                        f"```\n{chunk_content[:2000]}\n```\n"
                    )
            
            return "\n".join(formatted)
        except Exception:
            return ""

    async def _run_phase1_discovery(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        file_tree: str,
        dependencies: str,
        config_files: dict[str, str],
        rag_enabled: bool,
    ) -> str:
        """Run Phase 1: Discovery - understand project purpose and structure."""
        prompt = self._prompt_loader.get_prompt_by_key("phase1_discovery")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            retrieved_code = await self._retrieve_relevant_code(
                "discovery", repository_id, repo_path
            )
        
        config_files_str = "\n\n".join([
            f"**{filename}:**\n```\n{content[:500]}...\n```"
            for filename, content in config_files.items()
        ])
        
        # Combine static samples with RAG-retrieved code
        all_code = retrieved_code or config_files_str[:1000]
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "file_tree": file_tree[:3000],  # Increased limit with RAG
            "dependencies": dependencies[:1500],
            "config_files": all_code[:4000],  # RAG provides more relevant code
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
        repository_id: str | None,
        repo_path: Path,
        discovery_summary: str,
        file_tree: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
    ) -> str:
        """Run Phase 2: Layer Identification."""
        prompt = self._prompt_loader.get_prompt_by_key("phase2_layers")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            # Pass discovery context for smarter retrieval
            context = {"phase": "discovery", "summary": discovery_summary[:500]}
            retrieved_code = await self._retrieve_relevant_code(
                "layers", repository_id, repo_path, context
            )
        
        # Fall back to samples if RAG didn't return results
        code_to_analyze = retrieved_code or self._format_code_samples(code_samples, limit=5)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1500],
            "file_tree": file_tree[:2500],
            "code_samples": code_to_analyze[:5000],  # More code with RAG
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
        repository_id: str | None,
        repo_path: Path,
        discovery_summary: str,
        layer_analysis: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
    ) -> str:
        """Run Phase 3: Pattern Extraction."""
        prompt = self._prompt_loader.get_prompt_by_key("phase3_patterns")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            context = {
                "layers": layer_analysis[:500],
                "discovery": discovery_summary[:300],
            }
            retrieved_code = await self._retrieve_relevant_code(
                "patterns", repository_id, repo_path, context
            )
        
        code_to_analyze = retrieved_code or self._format_code_samples(code_samples, limit=8)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1000],
            "layer_analysis": layer_analysis[:1500],
            "code_samples": code_to_analyze[:6000],  # More code with RAG
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
        repository_id: str | None,
        repo_path: Path,
        previous_phases: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
    ) -> str:
        """Run Phase 4: Communication Analysis."""
        prompt = self._prompt_loader.get_prompt_by_key("phase4_communication")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            retrieved_code = await self._retrieve_relevant_code(
                "communication", repository_id, repo_path
            )
        
        code_to_analyze = retrieved_code or self._format_code_samples(code_samples, limit=6)
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "previous_phases": previous_phases[:3000],
            "code_samples": code_to_analyze[:5000],
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
        repository_id: str | None,
        repo_path: Path,
        all_phases: str,
        dependencies: str,
        rag_enabled: bool,
    ) -> str:
        """Run Phase 5: Technology Inventory."""
        prompt = self._prompt_loader.get_prompt_by_key("phase5_technology")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            retrieved_code = await self._retrieve_relevant_code(
                "technology", repository_id, repo_path
            )
        
        # Combine dependencies with retrieved code for tech analysis
        tech_context = f"{dependencies[:2000]}\n\n{retrieved_code[:3000]}"
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "all_phases": all_phases[:3500],
            "dependencies": tech_context,
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
            "phase1_discovery": phase1_discovery[:2500],
            "phase2_layers": phase2_layers[:2500],
            "phase3_patterns": phase3_patterns[:2500],
            "phase4_communication": phase4_communication[:2500],
            "phase5_technology": phase5_technology[:2500],
            "code_samples": code_samples[:4000],
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
