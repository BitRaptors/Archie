"""Phased blueprint generator using AI for comprehensive architecture documentation."""
import json
from pathlib import Path
from typing import Any
from anthropic import AsyncAnthropic
from infrastructure.prompts.prompt_loader import PromptLoader
from infrastructure.analysis.rag_retriever import RAGRetriever
from application.services.analysis_data_collector import analysis_data_collector
from domain.entities.blueprint import StructuredBlueprint
from config.settings import Settings


class PhasedBlueprintGenerator:
    """Generates comprehensive architecture blueprints through phased AI analysis.
    
    This generator uses an OBSERVATION-FIRST approach:
    1. Full File Scan: Extract signatures from ALL files (not just RAG matches)
    2. Pattern Detection: AI observes patterns WITHOUT predefined assumptions
    3. Dynamic Queries: Generate RAG queries based on what was ACTUALLY observed
    4. Phased Analysis: Build understanding incrementally with targeted retrieval
    
    This allows analyzing ANY architecture style - traditional layered, actor-based,
    event-sourced, CQRS, Flux, or completely custom patterns.
    """

    def __init__(self, settings: Settings, supabase_client=None, progress_callback=None):
        """Initialize phased blueprint generator.
        
        Args:
            settings: Application settings for AI configuration
            supabase_client: Supabase client for RAG retrieval (optional)
            progress_callback: Optional async callback function(analysis_id, event_type, message) for progress logging
        """
        self._settings = settings
        self._prompt_loader = PromptLoader()
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=600.0,  # 10 min timeout for API calls (synthesis with Sonnet can be slow)
        ) if settings.anthropic_api_key else None
        self._model = settings.default_ai_model  # Fast model for intermediate phases
        self._synthesis_model = getattr(settings, "synthesis_ai_model", settings.default_ai_model)  # Capable model for synthesis
        self._synthesis_max_tokens = getattr(settings, "synthesis_max_tokens", 10000)
        self._progress_callback = progress_callback
        self._rag_retriever = RAGRetriever(supabase_client, progress_callback) if supabase_client else None
        self._supabase_client = supabase_client

    async def generate(
        self,
        repo_path: Path,
        repository_name: str,
        repository_id: str | None = None,
        analysis_id: str | None = None,
        file_tree: str = "",
        dependencies: str = "",
        config_files: dict[str, str] | None = None,
        code_samples: dict[str, str] | None = None,
        blueprint_type: str = "backend",
    ) -> dict[str, Any]:
        """Generate comprehensive architecture blueprint through phased analysis.
        
        Uses RAG-based retrieval to analyze the ENTIRE codebase, not just samples.
        
        Args:
            repo_path: Path to cloned repository
            repository_name: Name of the repository
            repository_id: UUID of the repository (for RAG retrieval)
            analysis_id: UUID of the analysis (for progress logging)
            file_tree: Compressed file tree structure
            dependencies: Parsed dependencies (requirements.txt, package.json, etc.)
            config_files: Key configuration files content
            code_samples: Fallback code samples if RAG not available
            blueprint_type: Type of blueprint to generate ("backend" or "frontend")
        
        Returns:
            Dict with keys:
              - "structured": dict (the JSON blueprint)
              - "markdown": str  (rendered human-readable markdown)
        """
        if not self._client:
            mock_md = self._generate_mock_blueprint(repository_name)
            return {"structured": {}, "markdown": mock_md}
        
        config_files = config_files or {}
        code_samples = code_samples or {}
        
        # If RAG is available, index the repository first
        rag_enabled = self._rag_retriever and repository_id
        if rag_enabled:
            try:
                if self._progress_callback and analysis_id:
                    await self._progress_callback(analysis_id, "INFO", "Starting repository indexing for semantic search...")
                await self._rag_retriever.index_repository(repository_id, repo_path, analysis_id)
            except Exception:
                rag_enabled = False  # Fall back to sample-based analysis
                if self._progress_callback and analysis_id:
                    await self._progress_callback(analysis_id, "INFO", "RAG indexing failed, falling back to sample-based analysis")
        
        # PHASE 0: Observation-first full file scan (architecture-agnostic)
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Phase 0: Full file signature scan (architecture-agnostic observation)...")
        
        observation_result = await self._run_observation_phase(
            repo_path=repo_path,
            repository_name=repository_name,
            analysis_id=analysis_id,
        )
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Observation complete - detected architecture style and patterns")
        
        # Update RAG queries based on observations (if RAG is enabled)
        custom_rag_queries = None
        if rag_enabled and observation_result:
            custom_rag_queries = await self._generate_dynamic_rag_queries(observation_result, analysis_id)
            if self._rag_retriever:
                self._rag_retriever.set_custom_queries(custom_rag_queries)
        
        # Discovery: understand project purpose and structure
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Analyzing project structure and discovery...")
        discovery_result = await self._run_discovery_analysis(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            file_tree=file_tree,
            dependencies=dependencies,
            config_files=config_files,
            rag_enabled=rag_enabled,
            analysis_id=analysis_id,
            observation_result=observation_result,  # Pass observation insights
        )
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Project discovery finished")
        
        # Layers: identify architectural layers
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Identifying architectural layers...")
        layers_result = await self._run_layers_analysis(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            discovery_summary=discovery_result,
            file_tree=file_tree,
            code_samples=code_samples,
            rag_enabled=rag_enabled,
            analysis_id=analysis_id,
        )
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Layer architecture identified")
        
        # Patterns: identify design patterns
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Extracting design patterns...")
        patterns_result = await self._run_patterns_analysis(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            discovery_summary=discovery_result,
            layer_analysis=layers_result,
            code_samples=code_samples,
            rag_enabled=rag_enabled,
            analysis_id=analysis_id,
        )
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Design patterns extracted")
        
        # Communication: how components communicate
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Analyzing communication patterns...")
        previous_analyses = {
            "discovery": discovery_result,
            "layers": layers_result,
            "patterns": patterns_result,
        }
        communication_result = await self._run_communication_analysis(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            previous_analyses=json.dumps(previous_analyses, indent=2),
            code_samples=code_samples,
            rag_enabled=rag_enabled,
            analysis_id=analysis_id,
        )
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Communication patterns analyzed")
        
        # Technology: complete tech stack inventory
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Inventorying technology stack...")
        all_analyses = {
            "discovery": discovery_result,
            "layers": layers_result,
            "patterns": patterns_result,
            "communication": communication_result,
        }
        technology_result = await self._run_technology_analysis(
            repository_name=repository_name,
            repository_id=repository_id,
            repo_path=repo_path,
            all_analyses=json.dumps(all_analyses, indent=2),
            dependencies=dependencies,
            rag_enabled=rag_enabled,
            analysis_id=analysis_id,
        )
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Technology inventory complete")
        
        # Detect platforms from discovery result
        has_frontend = self._detect_frontend(discovery_result, file_tree, dependencies)

        # Frontend Analysis (if frontend detected)
        frontend_result = ""
        if has_frontend:
            if self._progress_callback and analysis_id:
                await self._progress_callback(analysis_id, "INFO", "Analyzing frontend architecture...")
            frontend_result = await self._run_frontend_analysis(
                repository_name=repository_name,
                repository_id=repository_id,
                repo_path=repo_path,
                previous_analyses=json.dumps({
                    "discovery": discovery_result,
                    "layers": layers_result,
                    "patterns": patterns_result,
                }, indent=2),
                code_samples=code_samples,
                rag_enabled=rag_enabled,
                analysis_id=analysis_id,
            )
            if self._progress_callback and analysis_id:
                await self._progress_callback(analysis_id, "INFO", "Frontend architecture analyzed")

        # Final Synthesis: Generate structured JSON blueprint
        if self._progress_callback and analysis_id:
            await self._progress_callback(analysis_id, "INFO", "Generating unified architecture blueprint...")

        if has_frontend:
            synthesis_result = await self._run_unified_synthesis(
                repository_name=repository_name,
                repository_id=repository_id or "",
                discovery=discovery_result,
                layers=layers_result,
                patterns=patterns_result,
                communication=communication_result,
                technology=technology_result,
                frontend_analysis=frontend_result,
                code_samples=self._format_code_samples(code_samples),
                analysis_id=analysis_id,
            )
        else:
            synthesis_result = await self._run_backend_synthesis(
                repository_name=repository_name,
                repository_id=repository_id or "",
                discovery=discovery_result,
                layers=layers_result,
                patterns=patterns_result,
                communication=communication_result,
                technology=technology_result,
                code_samples=self._format_code_samples(code_samples),
                analysis_id=analysis_id,
            )

        return synthesis_result

    async def _retrieve_relevant_code(
        self,
        stage: str,
        repository_id: str,
        repo_path: Path,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Retrieve relevant code chunks for an analysis stage using RAG.
        
        Args:
            stage: Current analysis stage (discovery, layers, patterns, etc.)
            repository_id: UUID of the repository
            repo_path: Path to cloned repository
            context: Context from previous stages
            
        Returns:
            Formatted string of relevant code chunks
        """
        if not self._rag_retriever:
            return ""
        
        try:
            chunks = await self._rag_retriever.retrieve_for_phase(
                phase=stage,
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

    async def _run_discovery_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        file_tree: str,
        dependencies: str,
        config_files: dict[str, str],
        rag_enabled: bool,
        analysis_id: str | None = None,
        observation_result: str = "",
    ) -> str:
        """Run Discovery analysis: understand project purpose and structure.
        
        Enhanced with observation results from the full file scan phase.
        """
        prompt = self._prompt_loader.get_prompt_by_key("discovery")
        
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
        
        # Include observation insights in the prompt
        observation_context = ""
        if observation_result:
            observation_context = f"\n\n## Architecture Observations (from full file scan)\n{observation_result[:2000]}\n\nUse these observations to inform your discovery analysis."
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "file_tree": file_tree[:3000],
            "dependencies": dependencies[:1500],
            "config_files": all_code[:4000] + observation_context,
        })
        
        # Capture analysis data if analysis_id is provided
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "discovery", 
                gathered={
                    "file_tree": {"full_content": file_tree, "char_count": len(file_tree)},
                    "dependencies": {"full_content": dependencies, "char_count": len(dependencies)},
                    "config_files": {"full_content": config_files_str, "char_count": len(config_files_str)}
                },
                sent={
                    "file_tree": {"content": file_tree[:3000], "char_count": len(file_tree[:3000]), "truncated_from": len(file_tree)},
                    "dependencies": {"content": dependencies[:1500], "char_count": len(dependencies[:1500]), "truncated_from": len(dependencies)},
                    "config_files": {"content": all_code[:4000], "char_count": len(all_code[:4000]), "truncated_from": len(all_code)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_layers_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        discovery_summary: str,
        file_tree: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
        analysis_id: str | None = None,
    ) -> str:
        """Run Layers analysis: identify architectural layers."""
        prompt = self._prompt_loader.get_prompt_by_key("layers")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            # Pass discovery context for smarter retrieval
            context = {"stage": "discovery", "summary": discovery_summary[:500]}
            retrieved_code = await self._retrieve_relevant_code(
                "layers", repository_id, repo_path, context
            )
        
        # Fall back to samples if RAG didn't return results
        formatted_samples = self._format_code_samples(code_samples, limit=5)
        code_to_analyze = retrieved_code or formatted_samples
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1500],
            "file_tree": file_tree[:2500],
            "code_samples": code_to_analyze[:5000],
        })
        
        # Capture analysis data if analysis_id is provided
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "layers", 
                gathered={
                    "discovery_summary": {"full_content": discovery_summary, "char_count": len(discovery_summary)},
                    "file_tree": {"full_content": file_tree, "char_count": len(file_tree)},
                    "code_samples": {"full_content": code_to_analyze, "char_count": len(code_to_analyze)}
                },
                sent={
                    "discovery_summary": {"content": discovery_summary[:1500], "char_count": len(discovery_summary[:1500]), "truncated_from": len(discovery_summary)},
                    "file_tree": {"content": file_tree[:2500], "char_count": len(file_tree[:2500]), "truncated_from": len(file_tree)},
                    "code_samples": {"content": code_to_analyze[:5000], "char_count": len(code_to_analyze[:5000]), "truncated_from": len(code_to_analyze)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_patterns_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        discovery_summary: str,
        layer_analysis: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
        analysis_id: str | None = None,
    ) -> str:
        """Run Patterns analysis: identify design patterns."""
        prompt = self._prompt_loader.get_prompt_by_key("patterns")
        
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
        
        formatted_samples = self._format_code_samples(code_samples, limit=8)
        code_to_analyze = retrieved_code or formatted_samples
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery_summary": discovery_summary[:1000],
            "layer_analysis": layer_analysis[:1500],
            "code_samples": code_to_analyze[:6000],
        })
        
        # Capture analysis data
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "patterns", 
                gathered={
                    "discovery_summary": {"full_content": discovery_summary, "char_count": len(discovery_summary)},
                    "layer_analysis": {"full_content": layer_analysis, "char_count": len(layer_analysis)},
                    "code_samples": {"full_content": code_to_analyze, "char_count": len(code_to_analyze)}
                },
                sent={
                    "discovery_summary": {"content": discovery_summary[:1000], "char_count": len(discovery_summary[:1000]), "truncated_from": len(discovery_summary)},
                    "layer_analysis": {"content": layer_analysis[:1500], "char_count": len(layer_analysis[:1500]), "truncated_from": len(layer_analysis)},
                    "code_samples": {"content": code_to_analyze[:6000], "char_count": len(code_to_analyze[:6000]), "truncated_from": len(code_to_analyze)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_communication_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        previous_analyses: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
        analysis_id: str | None = None,
    ) -> str:
        """Run Communication analysis: how components communicate."""
        prompt = self._prompt_loader.get_prompt_by_key("communication")
        
        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            retrieved_code = await self._retrieve_relevant_code(
                "communication", repository_id, repo_path
            )
        
        formatted_samples = self._format_code_samples(code_samples, limit=6)
        code_to_analyze = retrieved_code or formatted_samples
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "previous_analyses": previous_analyses[:3000],
            "code_samples": code_to_analyze[:5000],
        })
        
        # Capture analysis data
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "communication", 
                gathered={
                    "previous_analyses": {"full_content": previous_analyses, "char_count": len(previous_analyses)},
                    "code_samples": {"full_content": code_to_analyze, "char_count": len(code_to_analyze)}
                },
                sent={
                    "previous_analyses": {"content": previous_analyses[:3000], "char_count": len(previous_analyses[:3000]), "truncated_from": len(previous_analyses)},
                    "code_samples": {"content": code_to_analyze[:5000], "char_count": len(code_to_analyze[:5000]), "truncated_from": len(code_to_analyze)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_technology_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        all_analyses: str,
        dependencies: str,
        rag_enabled: bool,
        analysis_id: str | None = None,
    ) -> str:
        """Run Technology analysis: complete tech stack inventory."""
        prompt = self._prompt_loader.get_prompt_by_key("technology")
        
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
            "all_analyses": all_analyses[:3500],
            "dependencies": tech_context,
        })
        
        # Capture analysis data
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "technology", 
                gathered={
                    "all_analyses": {"full_content": all_analyses, "char_count": len(all_analyses)},
                    "dependencies": {"full_content": dependencies, "char_count": len(dependencies)}
                },
                sent={
                    "all_analyses": {"content": all_analyses[:3500], "char_count": len(all_analyses[:3500]), "truncated_from": len(all_analyses)},
                    "dependencies": {"content": tech_context, "char_count": len(tech_context), "truncated_from": len(dependencies) + len(retrieved_code)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )
        
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _run_backend_synthesis(
        self,
        repository_name: str,
        repository_id: str,
        discovery: str,
        layers: str,
        patterns: str,
        communication: str,
        technology: str,
        code_samples: str,
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """Run Backend Synthesis: Generate structured JSON blueprint + rendered markdown.
        
        Returns:
            Dict with "structured" (dict) and "markdown" (str).
        """
        prompt = self._prompt_loader.get_prompt_by_key("backend_synthesis")
        
        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery": discovery[:2500],
            "layers": layers[:2500],
            "patterns": patterns[:2500],
            "communication": communication[:2500],
            "technology": technology[:2500],
            "code_samples": code_samples[:4000],
        })
        
        # Capture analysis data
        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "backend_synthesis", 
                gathered={
                    "discovery": {"full_content": discovery, "char_count": len(discovery)},
                    "layers": {"full_content": layers, "char_count": len(layers)},
                    "patterns": {"full_content": patterns, "char_count": len(patterns)},
                    "communication": {"full_content": communication, "char_count": len(communication)},
                    "technology": {"full_content": technology, "char_count": len(technology)},
                    "code_samples": {"full_content": code_samples, "char_count": len(code_samples)}
                },
                sent={
                    "discovery": {"content": discovery[:2500], "char_count": len(discovery[:2500]), "truncated_from": len(discovery)},
                    "layers": {"content": layers[:2500], "char_count": len(layers[:2500]), "truncated_from": len(layers)},
                    "patterns": {"content": patterns[:2500], "char_count": len(patterns[:2500]), "truncated_from": len(patterns)},
                    "communication": {"content": communication[:2500], "char_count": len(communication[:2500]), "truncated_from": len(communication)},
                    "technology": {"content": technology[:2500], "char_count": len(technology[:2500]), "truncated_from": len(technology)},
                    "code_samples": {"content": code_samples[:4000], "char_count": len(code_samples[:4000]), "truncated_from": len(code_samples)},
                    "full_prompt": prompt_text
                }
            )
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id,
                "INFO",
                f"Using synthesis model: {self._synthesis_model} (max_tokens={self._synthesis_max_tokens})",
            )

        response = await self._client.messages.create(
            model=self._synthesis_model,
            max_tokens=self._synthesis_max_tokens,
            messages=[{"role": "user", "content": prompt_text}],
        )

        raw_text = response.content[0].text

        # Parse the structured JSON from AI response
        structured_data = self._parse_structured_response(raw_text, repository_name, repository_id)

        # Validate and create Pydantic model
        blueprint = StructuredBlueprint.model_validate(structured_data)

        # Ensure meta fields are populated
        if not blueprint.meta.repository:
            blueprint.meta.repository = repository_name
        if not blueprint.meta.repository_id:
            blueprint.meta.repository_id = repository_id

        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id,
                "INFO",
                f"Blueprint generated: {len(json.dumps(structured_data))} chars JSON",
            )

        return {
            "structured": blueprint.model_dump(),
        }

    def _detect_frontend(self, discovery_result: str, file_tree: str, dependencies: str) -> bool:
        """Detect whether the repository contains frontend code.

        Checks the discovery result and file tree for common frontend indicators
        such as package.json with React/Vue/Angular, frontend directories,
        .tsx/.jsx/.vue files, etc.
        """
        combined = (discovery_result + file_tree + dependencies).lower()
        frontend_indicators = [
            "react", "next.js", "nextjs", "vue", "angular", "svelte",
            "nuxt", "remix", "gatsby", "expo", "react-native", "react native",
            "swiftui", "jetpack compose", "flutter",
            ".tsx", ".jsx", ".vue", ".svelte",
            "web-frontend", "frontend",
            "pages/", "components/", "src/app/", "app/src/main",
            "package.json",
        ]
        return any(indicator in combined for indicator in frontend_indicators)

    async def _run_frontend_analysis(
        self,
        repository_name: str,
        repository_id: str | None,
        repo_path: Path,
        previous_analyses: str,
        code_samples: dict[str, str],
        rag_enabled: bool,
        analysis_id: str | None = None,
    ) -> str:
        """Run Frontend analysis: UI components, state, routing, data fetching."""
        prompt = self._prompt_loader.get_prompt_by_key("frontend_analysis")

        # Get relevant code via RAG if available
        retrieved_code = ""
        if rag_enabled and repository_id:
            retrieved_code = await self._retrieve_relevant_code(
                "frontend_analysis", repository_id, repo_path
            )

        formatted_samples = self._format_code_samples(code_samples, limit=8)
        code_to_analyze = retrieved_code or formatted_samples

        prompt_text = prompt.render({
            "repository_name": repository_name,
            "previous_analyses": previous_analyses[:3000],
            "code_samples": code_to_analyze[:6000],
        })

        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "frontend_analysis",
                gathered={
                    "previous_analyses": {"full_content": previous_analyses, "char_count": len(previous_analyses)},
                    "code_samples": {"full_content": code_to_analyze, "char_count": len(code_to_analyze)}
                },
                sent={
                    "previous_analyses": {"content": previous_analyses[:3000], "char_count": len(previous_analyses[:3000]), "truncated_from": len(previous_analyses)},
                    "code_samples": {"content": code_to_analyze[:6000], "char_count": len(code_to_analyze[:6000]), "truncated_from": len(code_to_analyze)},
                    "full_prompt": prompt_text
                },
                rag_retrieved={"content": retrieved_code, "char_count": len(retrieved_code)} if retrieved_code else None
            )

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt_text}],
        )

        return response.content[0].text

    async def _run_unified_synthesis(
        self,
        repository_name: str,
        repository_id: str,
        discovery: str,
        layers: str,
        patterns: str,
        communication: str,
        technology: str,
        frontend_analysis: str,
        code_samples: str,
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """Run Unified Synthesis: Generate structured JSON blueprint covering all platforms.

        Returns:
            Dict with "structured" (dict).
        """
        prompt = self._prompt_loader.get_prompt_by_key("unified_synthesis")

        prompt_text = prompt.render({
            "repository_name": repository_name,
            "discovery": discovery[:2500],
            "layers": layers[:2500],
            "patterns": patterns[:2500],
            "communication": communication[:2500],
            "technology": technology[:2500],
            "frontend_analysis": frontend_analysis[:3000],
            "code_samples": code_samples[:4000],
        })

        if analysis_id:
            await analysis_data_collector.capture_phase_data(analysis_id, "unified_synthesis",
                gathered={
                    "discovery": {"full_content": discovery, "char_count": len(discovery)},
                    "layers": {"full_content": layers, "char_count": len(layers)},
                    "patterns": {"full_content": patterns, "char_count": len(patterns)},
                    "communication": {"full_content": communication, "char_count": len(communication)},
                    "technology": {"full_content": technology, "char_count": len(technology)},
                    "frontend_analysis": {"full_content": frontend_analysis, "char_count": len(frontend_analysis)},
                    "code_samples": {"full_content": code_samples, "char_count": len(code_samples)}
                },
                sent={
                    "discovery": {"content": discovery[:2500], "char_count": len(discovery[:2500]), "truncated_from": len(discovery)},
                    "layers": {"content": layers[:2500], "char_count": len(layers[:2500]), "truncated_from": len(layers)},
                    "patterns": {"content": patterns[:2500], "char_count": len(patterns[:2500]), "truncated_from": len(patterns)},
                    "communication": {"content": communication[:2500], "char_count": len(communication[:2500]), "truncated_from": len(communication)},
                    "technology": {"content": technology[:2500], "char_count": len(technology[:2500]), "truncated_from": len(technology)},
                    "frontend_analysis": {"content": frontend_analysis[:3000], "char_count": len(frontend_analysis[:3000]), "truncated_from": len(frontend_analysis)},
                    "code_samples": {"content": code_samples[:4000], "char_count": len(code_samples[:4000]), "truncated_from": len(code_samples)},
                    "full_prompt": prompt_text
                }
            )

        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id,
                "INFO",
                f"Using synthesis model: {self._synthesis_model} (max_tokens={self._synthesis_max_tokens})",
            )

        response = await self._client.messages.create(
            model=self._synthesis_model,
            max_tokens=self._synthesis_max_tokens,
            messages=[{"role": "user", "content": prompt_text}],
        )

        raw_text = response.content[0].text

        structured_data = self._parse_structured_response(raw_text, repository_name, repository_id)

        blueprint = StructuredBlueprint.model_validate(structured_data)

        if not blueprint.meta.repository:
            blueprint.meta.repository = repository_name
        if not blueprint.meta.repository_id:
            blueprint.meta.repository_id = repository_id

        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id,
                "INFO",
                f"Unified blueprint generated: {len(json.dumps(structured_data))} chars JSON",
            )

        return {
            "structured": blueprint.model_dump(),
        }

    def _parse_structured_response(
        self, raw_text: str, repository_name: str, repository_id: str
    ) -> dict:
        """Parse JSON from AI response, handling truncation and formatting issues."""
        text = raw_text.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3].rstrip()

        # Extract JSON substring
        brace_start = text.find("{")
        if brace_start != -1:
            text = text[brace_start:]

        # Attempt 1: direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Attempt 2: find last valid closing brace
        brace_end = text.rfind("}")
        if brace_end != -1:
            try:
                return json.loads(text[:brace_end + 1])
            except json.JSONDecodeError:
                pass

        # Attempt 3: repair truncated JSON
        repaired = self._repair_truncated_json(text)
        if repaired:
            return repaired

        # Final fallback — should rarely reach here after repair
        return {
            "meta": {
                "repository": repository_name,
                "repository_id": repository_id,
                "architecture_style": "Could not parse structured output",
            },
            "decisions": {
                "architectural_style": {
                    "title": "Architecture Style",
                    "chosen": "See raw analysis",
                    "rationale": raw_text[:3000],
                }
            },
        }

    @staticmethod
    def _repair_truncated_json(text: str) -> dict | None:
        """Attempt to repair truncated JSON by closing open structures.

        Walks the string tracking nesting of {, [, and string literals.
        When the string ends prematurely, it closes everything that was left
        open so the result is valid JSON (with partial data).
        """
        # Trim any trailing incomplete value (e.g. a truncated string or number)
        # First, close any open string
        in_string = False
        escape_next = False
        open_stack: list[str] = []  # tracks '{' and '['

        i = 0
        last_good = 0  # position after last structurally complete token

        while i < len(text):
            ch = text[i]

            if escape_next:
                escape_next = False
                i += 1
                continue

            if ch == '\\' and in_string:
                escape_next = True
                i += 1
                continue

            if ch == '"' and not escape_next:
                in_string = not in_string
                if not in_string:
                    last_good = i + 1
                i += 1
                continue

            if in_string:
                i += 1
                continue

            # Outside string
            if ch in ('{', '['):
                open_stack.append(ch)
                i += 1
                continue
            if ch == '}':
                if open_stack and open_stack[-1] == '{':
                    open_stack.pop()
                last_good = i + 1
                i += 1
                continue
            if ch == ']':
                if open_stack and open_stack[-1] == '[':
                    open_stack.pop()
                last_good = i + 1
                i += 1
                continue

            i += 1

        if not open_stack:
            # JSON wasn't actually truncated structurally — nothing to repair
            return None

        # Truncate to last structurally sound position, then build closing sequence
        # Strategy: cut back to the last complete key-value or array element,
        # then close all open structures.
        repaired = text[:last_good] if last_good > 0 else text

        # Remove any trailing commas or colons that would make JSON invalid
        repaired = repaired.rstrip()
        while repaired and repaired[-1] in (',', ':', '"'):
            repaired = repaired[:-1].rstrip()

        # Close all open structures in reverse order
        for bracket in reversed(open_stack):
            if bracket == '{':
                repaired += '}'
            elif bracket == '[':
                repaired += ']'

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            # One more attempt: be more aggressive — cut back further
            # Find the last comma before our cut point and try from there
            cut = repaired.rfind(',')
            if cut > 0:
                aggressive = repaired[:cut]
                for bracket in reversed(open_stack):
                    aggressive += '}' if bracket == '{' else ']'
                try:
                    return json.loads(aggressive)
                except json.JSONDecodeError:
                    pass
            return None


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

    async def _run_observation_phase(
        self,
        repo_path: Path,
        repository_name: str,
        analysis_id: str | None = None,
    ) -> str:
        """Run observation-first full file scan.
        
        This phase scans ALL code files and extracts signatures to give the AI
        a complete view of the codebase WITHOUT predefined pattern assumptions.
        
        The AI observes what's there and describes the architecture style,
        whether it's layered, actor-based, event-sourced, or completely custom.
        
        Args:
            repo_path: Path to cloned repository
            repository_name: Name of the repository
            analysis_id: UUID of the analysis
            
        Returns:
            Observation result describing detected architecture style and patterns
        """
        # Extract file signatures from ALL code files
        file_signatures = await self._extract_all_file_signatures(repo_path, analysis_id)
        
        if not file_signatures:
            return "No code files found for observation."
        
        # Build the observation prompt
        prompt_text = f"""## Architecture Observation - {repository_name}

**CRITICAL INSTRUCTIONS:**
You are analyzing a codebase to understand its architecture. Your goal is to OBSERVE and DESCRIBE what exists, NOT to categorize it into known patterns.

**DO NOT:**
- Assume this is a "layered architecture", "MVC", "Clean Architecture", or any specific pattern
- Look for patterns that match your training data
- Force observations into predefined categories

**DO:**
- Describe the ACTUAL file organization you see
- Identify how files relate to each other based on naming and imports
- Note any conventions unique to this codebase
- Describe the architectural style in plain language
- Identify what makes this codebase unique

## File Signatures (Every code file in the repository)

{file_signatures}

## Your Task

1. **Describe the Organization**: How are files/modules organized? What's the directory structure communicating?

2. **Identify Components**: What are the main types of components? (Don't assume - observe from class names, file names, imports)

3. **Trace Dependencies**: Based on imports, how do components relate to each other?

4. **Detect Patterns**: What patterns or conventions are being used? (Could be standard, could be custom)

5. **Architecture Style**: In plain language, describe the architectural style. Examples:
   - "Actor-based with message passing"
   - "Event-sourced with CQRS separation"
   - "Feature-sliced with co-located concerns"
   - "Traditional layered with services and repositories"
   - "Functional core with imperative shell"
   - Or describe something completely unique

6. **Key Queries**: What specific terms/patterns should we search for to understand this codebase better?

Provide your analysis in JSON format:
```json
{{
  "organization_style": "Brief description of how files are organized",
  "detected_components": [
    {{"type": "component type observed", "naming_pattern": "how they're named", "examples": ["file1.ext", "file2.ext"]}}
  ],
  "dependency_flow": "How dependencies flow between components",
  "architecture_style": "Plain language description of the architecture",
  "unique_patterns": ["Patterns unique to this codebase"],
  "standard_patterns_if_any": ["Any recognizable patterns, if present"],
  "key_search_terms": ["Terms to search for to understand this architecture better"],
  "concerns": ["Any architectural concerns or unusual patterns noted"]
}}
```"""

        # Capture analysis data
        if analysis_id:
            await analysis_data_collector.capture_phase_data(
                analysis_id, 
                "observation",
                gathered={"file_signatures": {"full_content": file_signatures, "char_count": len(file_signatures)}},
                sent={"file_signatures": {"content": file_signatures, "char_count": len(file_signatures)}, "full_prompt": prompt_text}
            )

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt_text}],
        )
        
        return response.content[0].text

    async def _extract_all_file_signatures(
        self,
        repo_path: Path,
        analysis_id: str | None = None,
    ) -> str:
        """Extract signatures from ALL code files in the repository.
        
        For each file, extracts:
        - File path
        - Import statements (first 30 lines)
        - Class/function signatures (names only, not implementation)
        
        This gives the AI visibility into the ENTIRE codebase structure
        without needing to fit full file contents in context.
        
        Args:
            repo_path: Path to repository
            analysis_id: For progress logging
            
        Returns:
            Formatted string of all file signatures
        """
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
            ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".m", ".mm",  # Added Objective-C
        }
        
        ignore_patterns = {
            "node_modules", ".git", "venv", "__pycache__", ".next",
            "dist", "build", "target", ".gradle", ".idea", ".venv",
            "env", ".env", "vendor", "coverage", ".nyc_output", "Pods",
        }
        
        signatures = []
        file_count = 0
        max_files = 300  # Limit to keep within token budget
        
        for ext in code_extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if file_count >= max_files:
                    break
                    
                if any(pattern in str(file_path) for pattern in ignore_patterns):
                    continue
                
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    relative_path = str(file_path.relative_to(repo_path))
                    
                    # Extract signature components
                    signature = self._extract_file_signature(content, relative_path, ext)
                    if signature:
                        signatures.append(signature)
                        file_count += 1
                        
                except Exception:
                    continue
            
            if file_count >= max_files:
                break
        
        if self._progress_callback and analysis_id:
            await self._progress_callback(
                analysis_id, 
                "INFO", 
                f"Extracted signatures from {file_count} code files"
            )
        
        return "\n\n".join(signatures)

    def _extract_file_signature(self, content: str, file_path: str, ext: str) -> str:
        """Extract signature from a single file.
        
        Extracts:
        - Imports (first 30 lines that contain import/require/use statements)
        - Class/struct/interface definitions (just the signature line)
        - Function/method definitions (just the signature line)
        - Export statements (for JS/TS)
        
        Args:
            content: File content
            file_path: Relative file path
            ext: File extension
            
        Returns:
            Formatted signature string (~200-400 chars per file)
        """
        import re
        
        lines = content.split('\n')
        
        # Extract imports (limit to first 30 lines containing imports)
        imports = []
        import_patterns = {
            '.py': r'^(?:from|import)\s+',
            '.js': r'^(?:import|const.*require|export)',
            '.jsx': r'^(?:import|const.*require|export)',
            '.ts': r'^(?:import|const.*require|export)',
            '.tsx': r'^(?:import|const.*require|export)',
            '.java': r'^(?:import|package)\s+',
            '.go': r'^(?:import|package)\s+',
            '.rs': r'^(?:use|mod|extern)\s+',
            '.swift': r'^(?:import|@)',
            '.kt': r'^(?:import|package)\s+',
            '.cs': r'^(?:using|namespace)\s+',
            '.rb': r'^(?:require|include|extend)',
            '.php': r'^(?:use|namespace|require|include)',
            '.m': r'^(?:#import|#include|@import)',
            '.mm': r'^(?:#import|#include|@import)',
        }
        
        pattern = import_patterns.get(ext, r'^(?:import|from|use|require)')
        for line in lines[:50]:
            if re.match(pattern, line.strip()):
                imports.append(line.strip())
                if len(imports) >= 15:
                    break
        
        # Extract class/struct/interface/protocol definitions
        definitions = []
        def_patterns = [
            r'^(?:export\s+)?(?:abstract\s+)?(?:class|struct|interface|protocol|enum|type)\s+\w+',
            r'^(?:public|private|internal|open|final)?\s*(?:class|struct|interface|enum)\s+\w+',
            r'^(?:actor)\s+\w+',  # Swift actors
            r'^(?:data\s+)?class\s+\w+',  # Kotlin
            r'^(?:object)\s+\w+',  # Kotlin/Scala
            r'^type\s+\w+\s+=',  # TypeScript type aliases
        ]
        
        for line in lines:
            for pattern in def_patterns:
                if re.match(pattern, line.strip()):
                    # Get just the signature part
                    sig = line.strip()
                    if len(sig) > 100:
                        sig = sig[:100] + "..."
                    definitions.append(sig)
                    break
            if len(definitions) >= 10:
                break
        
        # Extract function/method definitions
        functions = []
        func_patterns = [
            r'^(?:export\s+)?(?:async\s+)?(?:function|def|func|fn)\s+\w+',
            r'^(?:public|private|protected|internal|open|override)?\s*(?:async\s+)?(?:func|def)\s+\w+',
            r'^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(',  # Arrow functions
            r'^(?:public|private|protected)?\s*\w+\s*\([^)]*\)\s*(?:->|:)',  # Method signatures
        ]
        
        for line in lines:
            for pattern in func_patterns:
                if re.match(pattern, line.strip()):
                    sig = line.strip()
                    if len(sig) > 80:
                        sig = sig[:80] + "..."
                    functions.append(sig)
                    break
            if len(functions) >= 15:
                break
        
        # Build signature output
        parts = [f"**{file_path}**"]
        
        if imports:
            parts.append(f"imports: {', '.join(imports[:5])}" + ("..." if len(imports) > 5 else ""))
        
        if definitions:
            parts.append("definitions:")
            for d in definitions[:5]:
                parts.append(f"  {d}")
        
        if functions:
            parts.append("functions:")
            for f in functions[:8]:
                parts.append(f"  {f}")
        
        return '\n'.join(parts)

    async def _generate_dynamic_rag_queries(
        self,
        observation_result: str,
        analysis_id: str | None = None,
    ) -> dict[str, list[str]]:
        """Generate custom RAG queries based on observation results.
        
        Instead of using predefined queries like "service layer" or "repository pattern",
        this generates queries specific to the observed architecture style.
        
        Args:
            observation_result: JSON output from observation phase
            analysis_id: For progress logging
            
        Returns:
            Dictionary of phase -> custom queries
        """
        import json
        
        try:
            # Try to parse JSON from observation result
            json_match = observation_result
            if "```json" in observation_result:
                json_match = observation_result.split("```json")[1].split("```")[0]
            
            observation = json.loads(json_match)
            
            # Extract key search terms from observation
            key_terms = observation.get("key_search_terms", [])
            components = observation.get("detected_components", [])
            style = observation.get("architecture_style", "")
            
            # Build custom queries for each phase
            custom_queries = {
                "discovery": key_terms[:4] if key_terms else ["main entry point", "configuration"],
                "layers": [],
                "patterns": [],
                "communication": [],
                "technology": ["import from require module"],
            }
            
            # Add component-specific queries
            for comp in components[:5]:
                naming = comp.get("naming_pattern", "")
                comp_type = comp.get("type", "")
                if naming or comp_type:
                    custom_queries["layers"].append(f"{naming} {comp_type}".strip())
            
            # Add pattern-specific queries
            patterns = observation.get("unique_patterns", []) + observation.get("standard_patterns_if_any", [])
            for pattern in patterns[:5]:
                custom_queries["patterns"].append(pattern)
            
            # Add architecture-style specific queries
            if "actor" in style.lower():
                custom_queries["communication"].extend(["actor message receive", "mailbox queue"])
            elif "event" in style.lower():
                custom_queries["communication"].extend(["event store append", "event handler"])
            elif "flux" in style.lower() or "redux" in style.lower():
                custom_queries["communication"].extend(["reducer action state", "dispatch"])
            else:
                custom_queries["communication"].extend(key_terms[:3])
            
            if self._progress_callback and analysis_id:
                total = sum(len(v) for v in custom_queries.values())
                await self._progress_callback(
                    analysis_id,
                    "INFO",
                    f"Generated {total} custom RAG queries based on observations"
                )
                # Log each phase's queries so the user can see them in the process log
                for phase, queries in custom_queries.items():
                    if queries:
                        await self._progress_callback(
                            analysis_id,
                            "INFO",
                            f"  RAG [{phase}]: {', '.join(queries)}"
                        )

            return custom_queries
            
        except Exception:
            # Fall back to default queries if parsing fails
            return {}
