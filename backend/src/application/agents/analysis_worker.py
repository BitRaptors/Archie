"""Analysis worker for observing codebase architecture."""
import logging
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from application.agents.base_worker import BaseWorker
from domain.entities.architecture_rule import ArchitectureRule
from domain.entities.worker_assignment import WorkerAssignment
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class AnalysisWorker(BaseWorker):
    """Worker that analyzes codebase and extracts architecture through pure observation.
    
    This worker:
    - Does NOT categorize into predefined patterns (MVC, Clean Architecture, etc.)
    - DOES observe actual file organization
    - DOES document what each file/module does
    - DOES map dependency relationships
    - DOES identify conventions from observed patterns
    - DOES detect boundaries between components
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None,
        prompt_loader: PromptLoader,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize analysis worker."""
        super().__init__(ai_client, prompt_loader, model)
    
    async def execute(
        self,
        assignment: WorkerAssignment,
        repo_path: Path,
    ) -> dict[str, Any]:
        """Execute analysis assignment.
        
        Args:
            assignment: Work assignment with files to analyze
            repo_path: Path to repository
            
        Returns:
            Dictionary with observations and extracted rules
        """
        assignment.start()
        
        try:
            # Read assigned files
            file_contents = await self.read_files(
                assignment.files,
                repo_path,
                max_chars_per_file=15_000,
            )
            
            if not file_contents:
                return {
                    "observations": {},
                    "rules": [],
                    "error": "No files could be read",
                }
            
            # Build dependency graph
            dependency_graph = self._build_dependency_graph(file_contents)
            
            # Phase 1: Observe structure
            structure_observations = await self._observe_structure(
                file_contents,
                dependency_graph,
            )
            
            # Phase 2: Extract rules from observations
            rules = await self._extract_rules(
                structure_observations,
                repo_path,
            )
            
            result = {
                "observations": structure_observations,
                "rules": [self._rule_to_dict(r) for r in rules],
                "files_analyzed": len(file_contents),
                "dependency_graph": dependency_graph,
            }
            
            assignment.complete(result)
            return result
            
        except Exception as e:
            logger.error(f"Analysis worker failed: {e}")
            assignment.fail(str(e))
            return {
                "observations": {},
                "rules": [],
                "error": str(e),
            }
    
    async def _observe_structure(
        self,
        file_contents: dict[str, str],
        dependency_graph: dict[str, dict[str, list[str]]],
    ) -> dict[str, Any]:
        """Observe structure through pure observation (no predefined patterns).
        
        Args:
            file_contents: File contents to analyze
            dependency_graph: Dependency relationships
            
        Returns:
            Observations dictionary
        """
        # Get the prompt from prompts.json
        prompt_template = self._prompt_loader.get_prompt_by_key("worker_observe_structure")
        
        if not prompt_template:
            # Fallback if prompt not found
            logger.warning("worker_observe_structure prompt not found, using fallback")
            prompt_template = self._get_fallback_prompt()
        
        # Format file contents for prompt
        formatted_files = self._format_files_for_prompt(file_contents)
        
        # Format dependency graph
        import json
        dep_graph_str = json.dumps(dependency_graph, indent=2)
        
        # Build prompt
        if hasattr(prompt_template, 'render'):
            prompt = prompt_template.render({
                "file_contents": formatted_files,
                "dependency_graph": dep_graph_str,
            })
        else:
            # Handle string template
            prompt = str(prompt_template).format(
                file_contents=formatted_files,
                dependency_graph=dep_graph_str,
            )
        
        # Call AI
        response = await self._call_ai(prompt, max_tokens=4000)
        
        if not response:
            # Return basic observations without AI
            return self._basic_observations(file_contents, dependency_graph)
        
        # Extract JSON from response
        observations = self._extract_json_from_response(response)
        
        if observations:
            return observations
        
        # Fallback to basic observations
        return self._basic_observations(file_contents, dependency_graph)
    
    def _get_fallback_prompt(self) -> str:
        """Get fallback prompt if prompts.json entry not found."""
        return """Analyze this code and describe ONLY what you observe.

## Code to Analyze
{file_contents}

## Import/Dependency Graph
{dependency_graph}

## Your Task

Describe ONLY what you observe. Do NOT:
- Categorize into known architecture patterns (MVC, Clean Architecture, etc.)
- Assume what the developers intended
- Prescribe what should be different

DO:
- Describe the actual file organization
- Describe what each module/file is responsible for
- Describe the dependency relationships (what imports what)
- Describe any conventions you observe in naming, structure, or patterns
- Describe boundaries between components (if any exist)

## Output Format

Return a JSON object:
```json
{{
  "file_purposes": {{"path/to/file.py": "Description"}},
  "dependencies": {{"path/to/file.py": {{"imports": [], "imported_by": []}}}},
  "observed_conventions": ["Convention description"],
  "observed_boundaries": [{{"boundary": "Description", "intermediary": "..."}}]
}}
```"""
    
    def _basic_observations(
        self,
        file_contents: dict[str, str],
        dependency_graph: dict[str, dict[str, list[str]]],
    ) -> dict[str, Any]:
        """Create basic observations without AI.
        
        Args:
            file_contents: File contents
            dependency_graph: Dependency graph
            
        Returns:
            Basic observations
        """
        file_purposes = {}
        for path, content in file_contents.items():
            # Infer purpose from filename and first few lines
            lines = content.split("\n")[:10]
            
            # Check for docstring
            purpose = "Unknown purpose"
            for line in lines:
                if line.strip().startswith('"""') or line.strip().startswith("'''"):
                    purpose = line.strip().strip('"\'')[:100]
                    break
                elif line.strip().startswith("#"):
                    purpose = line.strip("#").strip()[:100]
                    break
            
            file_purposes[path] = purpose
        
        # Observe conventions from file names
        conventions = []
        
        # Check for test file convention
        test_files = [p for p in file_contents if "test" in p.lower()]
        if test_files:
            conventions.append(f"Test files follow naming pattern (found {len(test_files)} test files)")
        
        # Check for directory organization
        dirs = set()
        for path in file_contents:
            parts = path.split("/")
            if len(parts) > 1:
                dirs.add(parts[0])
        
        if dirs:
            conventions.append(f"Code organized into directories: {', '.join(sorted(dirs))}")
        
        return {
            "file_purposes": file_purposes,
            "dependencies": dependency_graph,
            "observed_conventions": conventions,
            "observed_boundaries": [],
        }
    
    async def _extract_rules(
        self,
        observations: dict[str, Any],
        repo_path: Path,
    ) -> list[ArchitectureRule]:
        """Extract architecture rules from observations.
        
        Args:
            observations: Observations from _observe_structure
            repo_path: Repository path
            
        Returns:
            List of architecture rules
        """
        # Get the prompt
        prompt_template = self._prompt_loader.get_prompt_by_key("worker_extract_rules")
        
        import json
        observations_str = json.dumps(observations, indent=2)
        repo_context = str(repo_path.name)
        
        if prompt_template and hasattr(prompt_template, 'render'):
            prompt = prompt_template.render({
                "observations": observations_str,
                "repository_context": repo_context,
            })
        elif prompt_template:
            prompt = str(prompt_template).format(
                observations=observations_str,
                repository_context=repo_context,
            )
        else:
            prompt = f"""Convert these observations into structured architecture rules.

## Observations
{observations_str}

## Repository Context
{repo_context}

## Output Format
Return a JSON array of rules with: rule_type, rule_id, name, description, rule_data, confidence, source_files"""
        
        # Call AI
        response = await self._call_ai(prompt, max_tokens=4000)
        
        if not response:
            return self._basic_rules(observations)
        
        # Extract rules from response
        rules_data = self._extract_json_from_response(response)
        
        if not rules_data:
            return self._basic_rules(observations)
        
        if isinstance(rules_data, dict) and "rules" in rules_data:
            rules_data = rules_data["rules"]
        
        if not isinstance(rules_data, list):
            return self._basic_rules(observations)
        
        # Convert to ArchitectureRule objects
        rules = []
        for rule_dict in rules_data:
            try:
                rule = ArchitectureRule.create_learned_rule(
                    repository_id="",  # Will be set by orchestrator
                    rule_type=rule_dict.get("rule_type", "convention"),
                    rule_id=rule_dict.get("rule_id", f"rule-{len(rules)}"),
                    name=rule_dict.get("name", "Unnamed Rule"),
                    rule_data=rule_dict.get("rule_data", {}),
                    description=rule_dict.get("description"),
                    confidence=float(rule_dict.get("confidence", 0.8)),
                    source_files=rule_dict.get("source_files", []),
                )
                rules.append(rule)
            except Exception as e:
                logger.warning(f"Failed to create rule: {e}")
        
        return rules
    
    def _basic_rules(self, observations: dict[str, Any]) -> list[ArchitectureRule]:
        """Create basic rules from observations without AI.
        
        Args:
            observations: Observations dictionary
            
        Returns:
            List of basic rules
        """
        rules = []
        
        # Create purpose rules from file_purposes
        file_purposes = observations.get("file_purposes", {})
        for file_path, purpose in file_purposes.items():
            if purpose and purpose != "Unknown purpose":
                rule = ArchitectureRule.create_learned_rule(
                    repository_id="",
                    rule_type="purpose",
                    rule_id=f"purpose-{file_path.replace('/', '-').replace('.', '-')}",
                    name=f"Purpose of {file_path}",
                    rule_data={
                        "file": file_path,
                        "purpose": purpose,
                    },
                    confidence=0.7,
                    source_files=[file_path],
                )
                rules.append(rule)
        
        # Create dependency rules
        dependencies = observations.get("dependencies", {})
        for file_path, deps in dependencies.items():
            if deps.get("imports"):
                rule = ArchitectureRule.create_learned_rule(
                    repository_id="",
                    rule_type="dependency",
                    rule_id=f"dep-{file_path.replace('/', '-').replace('.', '-')}",
                    name=f"Dependencies of {file_path}",
                    rule_data={
                        "file": file_path,
                        "imports": deps.get("imports", []),
                        "imported_by": deps.get("imported_by", []),
                    },
                    confidence=0.9,  # Dependency info is factual
                    source_files=[file_path],
                )
                rules.append(rule)
        
        # Create convention rules
        conventions = observations.get("observed_conventions", [])
        for i, convention in enumerate(conventions):
            rule = ArchitectureRule.create_learned_rule(
                repository_id="",
                rule_type="convention",
                rule_id=f"conv-{i}",
                name=f"Convention: {convention[:50]}",
                rule_data={
                    "pattern": convention,
                },
                confidence=0.7,
            )
            rules.append(rule)
        
        return rules
    
    def _rule_to_dict(self, rule: ArchitectureRule) -> dict[str, Any]:
        """Convert rule to dictionary.
        
        Args:
            rule: Architecture rule
            
        Returns:
            Dictionary representation
        """
        return {
            "rule_type": rule.rule_type,
            "rule_id": rule.rule_id,
            "name": rule.name,
            "description": rule.description,
            "rule_data": rule.rule_data,
            "confidence": rule.confidence,
            "source_files": rule.source_files,
        }
