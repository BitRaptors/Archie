"""Architecture orchestrator for coordinating worker agents."""
import asyncio
import logging
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from application.agents.analysis_worker import AnalysisWorker
from application.agents.sync_worker import SyncWorker
from application.agents.token_scanner import TokenScanner, ScanResult
from application.agents.validation_worker import ValidationWorker
from domain.entities.architecture_rule import ArchitectureRule
from domain.entities.validation_result import ValidationReport, ValidationResult
from domain.entities.worker_assignment import (
    OrchestrationPlan,
    WorkerAssignment,
    WorkerType,
)
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class ArchitectureOrchestrator:
    """Orchestrates architecture analysis using specialized worker agents.
    
    The orchestrator:
    - Plans the workflow based on repository size
    - Spawns workers in parallel where possible
    - Synthesizes results from all workers
    - Stores final results
    
    Does NOT:
    - Read codebase files directly (delegates to workers)
    - Make architectural decisions (workers do this)
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None,
        prompt_loader: PromptLoader,
        model: str = "claude-sonnet-4-20250514",
        worker_budget: int = 150_000,
    ):
        """Initialize orchestrator.
        
        Args:
            ai_client: Anthropic client for AI calls
            prompt_loader: Loader for prompts
            model: AI model to use
            worker_budget: Token budget per worker
        """
        self._ai_client = ai_client
        self._prompt_loader = prompt_loader
        self._model = model
        self._worker_budget = worker_budget
        
        # Initialize scanner and workers
        self._scanner = TokenScanner()
        self._analysis_worker = AnalysisWorker(ai_client, prompt_loader, model)
        self._validation_worker = ValidationWorker(ai_client, prompt_loader, model)
        self._sync_worker = SyncWorker(ai_client, prompt_loader, model)
    
    async def analyze_repository(
        self,
        repo_path: Path,
        repository_id: str,
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """Analyze a repository and extract architecture rules.
        
        Args:
            repo_path: Path to the repository
            repository_id: ID of the repository in database
            analysis_id: Optional analysis ID for tracking
            
        Returns:
            Dictionary with analysis results including extracted rules
        """
        logger.info(f"Starting architecture analysis for {repo_path}")
        
        # Step 1: Scan repository
        scan_result = await self._scanner.scan(repo_path)
        logger.info(f"Scanned {scan_result.total_files} files, {scan_result.total_tokens:,} tokens")
        
        # Step 2: Plan work distribution
        plan = self._plan_analysis(scan_result, repository_id)
        logger.info(f"Created plan with {len(plan.assignments)} worker assignments")
        
        # Step 3: Execute workers in parallel
        results = await self._execute_analysis_workers(plan, repo_path)
        
        # Step 4: Synthesize results
        synthesized = self._synthesize_results(results, repository_id, analysis_id)
        
        logger.info(f"Analysis complete: {len(synthesized['rules'])} rules extracted")
        
        return synthesized
    
    async def validate_files(
        self,
        repo_path: Path,
        repository_id: str,
        file_paths: list[str],
        rules: list[ArchitectureRule],
    ) -> ValidationReport:
        """Validate files against architecture rules.
        
        Args:
            repo_path: Path to repository
            repository_id: Repository ID
            file_paths: Files to validate
            rules: Rules to validate against
            
        Returns:
            ValidationReport with results
        """
        logger.info(f"Validating {len(file_paths)} files against {len(rules)} rules")
        
        # Create validation assignment
        assignment = WorkerAssignment.create_validation_assignment(
            files=file_paths,
            context={
                "rules": [r.to_dict() for r in rules],
            },
        )
        
        # Execute validation
        result = await self._validation_worker.execute(assignment, repo_path)
        
        # Convert to ValidationReport
        validation_results = []
        for result_dict in result.get("results", []):
            validation_results.append(
                ValidationResult(
                    file_path=result_dict["file_path"],
                    is_valid=result_dict["is_valid"],
                    violations=[],  # Simplified for now
                    rules_checked=result_dict.get("rules_checked", 0),
                )
            )
        
        return ValidationReport.create(repository_id, validation_results)
    
    async def detect_changes(
        self,
        repo_path: Path,
        repository_id: str,
        since_commit: str | None = None,
        existing_rules: list[ArchitectureRule] | None = None,
    ) -> dict[str, Any]:
        """Detect changes and determine if re-analysis is needed.
        
        Args:
            repo_path: Path to repository
            repository_id: Repository ID
            since_commit: Optional commit to compare from
            existing_rules: Existing architecture rules
            
        Returns:
            Dictionary with change detection results
        """
        logger.info(f"Detecting changes in {repo_path}")
        
        # Create sync assignment
        assignment = WorkerAssignment.create_sync_assignment(
            context={
                "since_commit": since_commit,
                "rules": [r.to_dict() for r in (existing_rules or [])],
            },
        )
        
        # Execute sync
        result = await self._sync_worker.execute(assignment, repo_path)
        
        return result
    
    def _plan_analysis(
        self,
        scan_result: ScanResult,
        repository_id: str,
    ) -> OrchestrationPlan:
        """Plan how to distribute analysis work.
        
        Args:
            scan_result: Result from token scanner
            repository_id: Repository ID
            
        Returns:
            Orchestration plan
        """
        # Get file assignments based on token budgets
        file_groups = self._scanner.plan_assignments(
            scan_result,
            budget_per_worker=self._worker_budget,
        )
        
        # Create worker assignments
        assignments = []
        for files in file_groups:
            assignment = WorkerAssignment.create_analysis_assignment(
                files=files,
                token_budget=self._worker_budget,
                focus_areas=["purpose", "dependency", "convention", "boundary"],
            )
            assignments.append(assignment)
        
        return OrchestrationPlan.create(
            repository_id=repository_id,
            total_files=scan_result.total_files,
            total_tokens=scan_result.total_tokens,
            assignments=assignments,
        )
    
    async def _execute_analysis_workers(
        self,
        plan: OrchestrationPlan,
        repo_path: Path,
    ) -> list[dict[str, Any]]:
        """Execute analysis workers in parallel.
        
        Args:
            plan: Orchestration plan
            repo_path: Repository path
            
        Returns:
            List of worker results
        """
        # Execute workers in parallel (up to 4 at a time)
        semaphore = asyncio.Semaphore(4)
        
        async def execute_with_semaphore(assignment: WorkerAssignment) -> dict[str, Any]:
            async with semaphore:
                return await self._analysis_worker.execute(assignment, repo_path)
        
        tasks = [
            execute_with_semaphore(assignment)
            for assignment in plan.assignments
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Worker {i} failed: {result}")
                plan.assignments[i].fail(str(result))
            else:
                valid_results.append(result)
        
        return valid_results
    
    def _synthesize_results(
        self,
        worker_results: list[dict[str, Any]],
        repository_id: str,
        analysis_id: str | None,
    ) -> dict[str, Any]:
        """Synthesize results from all workers.
        
        Args:
            worker_results: Results from all workers
            repository_id: Repository ID
            analysis_id: Analysis ID
            
        Returns:
            Synthesized results
        """
        all_rules = []
        all_observations = {}
        total_files_analyzed = 0
        
        for result in worker_results:
            if "error" in result:
                continue
            
            # Collect rules
            rules_data = result.get("rules", [])
            for rule_dict in rules_data:
                rule = ArchitectureRule.create_learned_rule(
                    repository_id=repository_id,
                    analysis_id=analysis_id,
                    rule_type=rule_dict.get("rule_type", "convention"),
                    rule_id=rule_dict.get("rule_id", ""),
                    name=rule_dict.get("name", ""),
                    rule_data=rule_dict.get("rule_data", {}),
                    description=rule_dict.get("description"),
                    confidence=rule_dict.get("confidence", 0.8),
                    source_files=rule_dict.get("source_files", []),
                )
                all_rules.append(rule)
            
            # Collect observations
            observations = result.get("observations", {})
            for key, value in observations.items():
                if key not in all_observations:
                    all_observations[key] = {}
                if isinstance(value, dict):
                    all_observations[key].update(value)
                elif isinstance(value, list):
                    if key not in all_observations or not isinstance(all_observations[key], list):
                        all_observations[key] = []
                    all_observations[key].extend(value)
            
            total_files_analyzed += result.get("files_analyzed", 0)
        
        # Deduplicate rules by rule_id
        seen_rule_ids = set()
        unique_rules = []
        for rule in all_rules:
            if rule.rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule.rule_id)
                unique_rules.append(rule)
        
        return {
            "repository_id": repository_id,
            "analysis_id": analysis_id,
            "rules": unique_rules,
            "observations": all_observations,
            "total_files_analyzed": total_files_analyzed,
            "total_rules": len(unique_rules),
            "workers_executed": len(worker_results),
        }
