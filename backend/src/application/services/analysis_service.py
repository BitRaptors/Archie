"""Analysis service orchestrator."""
from pathlib import Path
from typing import Any
from domain.entities.analysis import Analysis
from domain.entities.repository import Repository
from domain.entities.analysis_event import AnalysisEvent
from domain.interfaces.repositories import IRepository, IAnalysisEventRepository
from domain.exceptions.domain_exceptions import NotFoundError
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.analysis.embedding_generator import EmbeddingGenerator
from infrastructure.analysis.ast_extractor import ASTExtractor
from infrastructure.analysis.pattern_detector import PatternDetector
from infrastructure.analysis.semantic_pattern_finder import SemanticPatternFinder
from infrastructure.ai.blueprint_analyzer import BlueprintAnalyzer
from application.services.blueprint_generator import BlueprintGenerator
from application.services.prompt_service import PromptService
from infrastructure.storage.temp_storage import TempStorage
from infrastructure.storage.storage_interface import IStorage
from config.constants import AnalysisStatus


class AnalysisService:
    """Service for orchestrating repository analysis."""

    def __init__(
        self,
        analysis_repo: IRepository[Analysis, str],
        repository_repo: IRepository[Repository, str],
        event_repo: IAnalysisEventRepository,
        structure_analyzer: StructureAnalyzer,
        embedding_generator: EmbeddingGenerator,
        ast_extractor: ASTExtractor,
        pattern_detector: PatternDetector,
        semantic_pattern_finder: SemanticPatternFinder,
        blueprint_analyzer: BlueprintAnalyzer,
        blueprint_generator: BlueprintGenerator,
        prompt_service: PromptService,
        temp_storage: TempStorage,
        persistent_storage: IStorage,
    ):
        """Initialize analysis service."""
        self._analysis_repo = analysis_repo
        self._repository_repo = repository_repo
        self._event_repo = event_repo
        self._structure_analyzer = structure_analyzer
        self._embedding_generator = embedding_generator
        self._ast_extractor = ast_extractor
        self._pattern_detector = pattern_detector
        self._semantic_pattern_finder = semantic_pattern_finder
        self._blueprint_analyzer = blueprint_analyzer
        self._blueprint_generator = blueprint_generator
        self._prompt_service = prompt_service
        self._temp_storage = temp_storage
        self._persistent_storage = persistent_storage

    async def _log_event(self, analysis_id: str, event_type: str, message: str, details: dict | None = None) -> None:
        """Log an analysis event."""
        event = AnalysisEvent.create(analysis_id, event_type, message, details)
        await self._event_repo.add(event)

    async def start_analysis(
        self,
        repository_id: str,
        prompt_config: dict[str, str] | None = None,
    ) -> Analysis:
        """Start analysis for a repository."""
        # Get repository
        repo = await self._repository_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundError("Repository", repository_id)

        # Create analysis
        analysis = Analysis.create(repository_id)
        analysis = await self._analysis_repo.add(analysis)

        # Log start event
        await self._log_event(analysis.id, "PHASE_START", f"Starting analysis for {repo.full_name}")

        # Start analysis (will be run in background worker)
        analysis.start()
        await self._analysis_repo.update(analysis)

        return analysis

    async def run_analysis(
        self,
        analysis_id: str,
        repo_path: Path,
        token: str,
        prompt_config: dict[str, str] | None = None,
    ) -> None:
        """Run the full analysis pipeline."""
        analysis = await self._analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise NotFoundError("Analysis", analysis_id)

        try:
            # Phase 1: Structure scan
            await self._log_event(analysis_id, "PHASE_START", "Phase 1: Scanning file structure")
            analysis.update_progress(10)
            await self._analysis_repo.update(analysis)
            structure_data = await self._structure_analyzer.analyze(repo_path)
            await self._log_event(analysis_id, "PHASE_END", "Phase 1 complete: File structure indexed")

            # Phase 2: Embedding generation
            await self._log_event(analysis_id, "PHASE_START", "Phase 2: Generating code embeddings")
            analysis.update_progress(20)
            await self._analysis_repo.update(analysis)
            await self._embedding_generator.generate_embeddings(
                repository_id=analysis.repository_id,
                repo_path=repo_path,
            )
            await self._log_event(analysis_id, "PHASE_END", "Phase 2 complete: Semantic index created")

            # Phase 3: AST extraction
            await self._log_event(analysis_id, "PHASE_START", "Phase 3: Extracting AST and code structure")
            analysis.update_progress(30)
            await self._analysis_repo.update(analysis)
            ast_data = await self._ast_extractor.extract_all(repo_path)
            await self._log_event(analysis_id, "PHASE_END", "Phase 3 complete: Code relationships mapped")

            # Phase 4: Pattern discovery (semantic + structural)
            await self._log_event(analysis_id, "PHASE_START", "Phase 4: Discovering architectural patterns")
            analysis.update_progress(50)
            await self._analysis_repo.update(analysis)
            patterns = await self._pattern_detector.detect_patterns(
                repository_id=analysis.repository_id,
                repo_path=repo_path,
                prompt_config=prompt_config,
            )
            await self._log_event(analysis_id, "PHASE_END", f"Phase 4 complete: Found {len(patterns) if patterns else 0} patterns")

            # Phase 5: AI analysis (hierarchical with custom prompts)
            await self._log_event(analysis_id, "PHASE_START", "Phase 5: Performing AI architectural analysis")
            analysis.update_progress(70)
            await self._analysis_repo.update(analysis)
            ai_analysis = await self._blueprint_analyzer.analyze(
                repository_id=analysis.repository_id,
                structure_data=structure_data,
                ast_data=ast_data,
                patterns=patterns,
                prompt_config=prompt_config,
            )
            await self._log_event(analysis_id, "PHASE_END", "Phase 5 complete: AI analysis finished")

            # Phase 6: Blueprint synthesis
            await self._log_event(analysis_id, "PHASE_START", "Phase 6: Synthesizing architecture blueprint")
            analysis.update_progress(90)
            await self._analysis_repo.update(analysis)
            blueprint_content = await self._blueprint_generator.generate(
                repository_id=analysis.repository_id,
                structure_data=structure_data,
                patterns=patterns,
                ai_analysis=ai_analysis,
                prompt_config=prompt_config,
            )
            
            # Save blueprint
            blueprint_path = f"blueprints/{analysis.repository_id}/blueprint.md"
            await self._persistent_storage.save(blueprint_path, blueprint_content)
            await self._log_event(analysis_id, "PHASE_END", "Phase 6 complete: Blueprint document generated")

            # Complete analysis
            await self._log_event(analysis_id, "INFO", "Analysis completed successfully")
            analysis.complete()
            await self._analysis_repo.update(analysis)

        except Exception as e:
            await self._log_event(analysis_id, "ERROR", f"Analysis failed: {str(e)}")
            analysis.fail(str(e))
            await self._analysis_repo.update(analysis)
            raise
