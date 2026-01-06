"""Blueprint analyzer using Claude API."""
from typing import Any
import anthropic
from config.settings import get_settings
from application.services.prompt_service import PromptService
from config.constants import PromptCategory


class BlueprintAnalyzer:
    """Analyzes code using Claude API with custom prompts."""

    def __init__(self, prompt_service: PromptService):
        """Initialize blueprint analyzer."""
        settings = get_settings()
        try:
            self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            self._model = settings.default_ai_model
        except Exception:
            # If API key is invalid, set to None to skip AI analysis
            self._client = None
            self._model = None
        self._prompt_service = prompt_service

    async def analyze(
        self,
        repository_id: str,
        structure_data: dict[str, Any],
        ast_data: dict[str, Any],
        patterns: dict[str, Any],
        prompt_config: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform hierarchical AI analysis."""
        # If no client (invalid API key), return mock analysis
        if not self._client:
            return {
                "summary": "Mock AI analysis (Anthropic API not configured)",
                "architecture_style": "Unknown",
                "key_patterns": [],
                "recommendations": []
            }
        
        analysis = {}
        
        # Directory-level summaries
        analysis["directory_summaries"] = await self._analyze_directories(
            structure_data,
            ast_data,
            prompt_config,
        )
        
        # Pattern deep-dives
        analysis["pattern_analysis"] = await self._analyze_patterns(
            patterns,
            prompt_config,
        )
        
        # Principle evaluation
        analysis["principles"] = await self._evaluate_principles(
            structure_data,
            ast_data,
            prompt_config,
        )
        
        return analysis

    async def _analyze_directories(
        self,
        structure_data: dict[str, Any],
        ast_data: dict[str, Any],
        prompt_config: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Analyze directories with custom prompts using hierarchical summarization."""
        # Create a summarized version of structure_data (Cursor-like approach)
        structure_summary = self._summarize_structure(structure_data)
        ast_summary = self._summarize_ast(ast_data)
        
        # Get prompt for directory summary
        prompt_id = prompt_config.get(PromptCategory.DIRECTORY_SUMMARY) if prompt_config else None
        if prompt_id:
            prompt = await self._prompt_service.get_prompt(prompt_id)
            prompt_text = prompt.render({
                "structure_summary": structure_summary,
                "ast_summary": ast_summary,
            })
        else:
            prompt_text = f"""Analyze the directory structure and provide architectural insights.

Directory Structure Summary:
{structure_summary}

Code Structure Summary:
{ast_summary}

Provide a high-level architectural analysis focusing on:
1. Main architectural patterns
2. Key modules and their responsibilities
3. Technology stack and dependencies
4. Overall code organization"""
        
        # Call Claude
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt_text,
            }],
        )
        
        return {
            "summary": response.content[0].text,
        }
    
    def _summarize_structure(self, structure_data: dict[str, Any]) -> str:
        """Create a concise summary of structure data (Cursor-like approach)."""
        summary_parts = []
        
        # Technologies
        if structure_data.get("technologies"):
            summary_parts.append(f"Technologies: {', '.join(structure_data['technologies'])}")
        
        # Directory structure (only top-level)
        dir_structure = structure_data.get("directory_structure", {})
        if dir_structure:
            root_files = dir_structure.get("root_files", [])
            if root_files:
                summary_parts.append(f"Root files ({len(root_files)}): {', '.join(root_files[:10])}")
            
            src_structure = dir_structure.get("src_structure", {})
            if src_structure:
                subdirs = src_structure.get("subdirectories", [])
                if subdirs:
                    summary_parts.append(f"Main source directories: {', '.join(subdirs[:15])}")
        
        # File tree summary (not full tree)
        file_tree = structure_data.get("file_tree", [])
        if file_tree:
            # Count files by type
            file_counts = {}
            for item in file_tree:
                if item.get("type") == "file":
                    ext = item.get("extension", "")
                    file_counts[ext] = file_counts.get(ext, 0) + 1
            
            file_summary = ", ".join([f"{ext or 'no-ext'}: {count}" for ext, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]])
            summary_parts.append(f"File types: {file_summary}")
            summary_parts.append(f"Total files analyzed: {len([f for f in file_tree if f.get('type') == 'file'])}")
        
        return "\n".join(summary_parts) if summary_parts else "No structure data available"
    
    def _summarize_ast(self, ast_data: dict[str, Any]) -> str:
        """Create a concise summary of AST data (Cursor-like approach)."""
        summary_parts = []
        
        # Count files
        files = ast_data.get("files", {})
        if files:
            summary_parts.append(f"Code files analyzed: {len(files)}")
        
        # Summarize imports (top-level only)
        imports = ast_data.get("imports", {})
        if imports:
            # Get unique import patterns
            all_imports = set()
            for file_imports in imports.values():
                if isinstance(file_imports, list):
                    all_imports.update(file_imports[:5])  # Limit per file
            
            if all_imports:
                summary_parts.append(f"Key imports: {', '.join(list(all_imports)[:20])}")
        
        # Summarize functions/classes (counts only, not full details)
        functions = ast_data.get("functions", {})
        classes = ast_data.get("classes", {})
        
        if functions:
            total_functions = sum(len(f) if isinstance(f, list) else 1 for f in functions.values())
            summary_parts.append(f"Total functions: {total_functions}")
        
        if classes:
            total_classes = sum(len(c) if isinstance(c, list) else 1 for c in classes.values())
            summary_parts.append(f"Total classes: {total_classes}")
        
        return "\n".join(summary_parts) if summary_parts else "No AST data available"

    async def _analyze_patterns(
        self,
        patterns: dict[str, Any],
        prompt_config: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Analyze patterns with custom prompts using summarized data."""
        # Summarize patterns (Cursor-like approach)
        patterns_summary = self._summarize_patterns(patterns)
        
        # Get prompt for pattern analysis
        prompt_id = prompt_config.get(PromptCategory.PATTERNS) if prompt_config else None
        if prompt_id:
            prompt = await self._prompt_service.get_prompt(prompt_id)
            prompt_text = prompt.render({
                "patterns_found": patterns_summary,
            })
        else:
            prompt_text = f"""Analyze the architectural patterns found in this codebase:

{patterns_summary}

Provide insights on:
1. Architectural patterns and their implementation
2. Design patterns used
3. Code organization patterns
4. Potential improvements or anti-patterns"""
        
        # Call Claude
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt_text,
            }],
        )
        
        return {
            "analysis": response.content[0].text,
        }
    
    def _summarize_patterns(self, patterns: dict[str, Any]) -> str:
        """Create a concise summary of patterns (Cursor-like approach)."""
        summary_parts = []
        
        # Structural patterns
        structural = patterns.get("structural", {})
        if structural:
            pattern_types = list(structural.keys())[:10]  # Limit to 10 pattern types
            summary_parts.append(f"Structural patterns found: {', '.join(pattern_types)}")
        
        # Semantic patterns
        semantic = patterns.get("semantic", {})
        if semantic:
            if isinstance(semantic, dict):
                pattern_names = list(semantic.keys())[:10]
                summary_parts.append(f"Semantic patterns: {', '.join(pattern_names)}")
            else:
                summary_parts.append(f"Semantic patterns: {len(semantic) if isinstance(semantic, list) else 'various'}")
        
        # Combined patterns
        combined = patterns.get("combined", {})
        if combined:
            summary_parts.append(f"Combined pattern analysis: {len(combined)} key patterns identified")
        
        return "\n".join(summary_parts) if summary_parts else "No significant patterns detected"

    async def _evaluate_principles(
        self,
        structure_data: dict[str, Any],
        ast_data: dict[str, Any],
        prompt_config: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Evaluate principles with custom prompts using summarized data."""
        # Create summaries
        structure_summary = self._summarize_structure(structure_data)
        ast_summary = self._summarize_ast(ast_data)
        
        # Get prompt for principles
        prompt_id = prompt_config.get(PromptCategory.PRINCIPLES) if prompt_config else None
        if prompt_id:
            prompt = await self._prompt_service.get_prompt(prompt_id)
            prompt_text = prompt.render({
                "structure_summary": structure_summary,
                "ast_summary": ast_summary,
            })
        else:
            prompt_text = f"""Evaluate software engineering principles for this codebase:

{structure_summary}

{ast_summary}

Evaluate against principles like:
1. SOLID principles
2. DRY (Don't Repeat Yourself)
3. Separation of Concerns
4. Modularity and cohesion
5. Code maintainability"""
        
        # Call Claude
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4000,
            messages=[{
                "role": "user",
                "content": prompt_text,
            }],
        )
        
        return {
            "evaluation": response.content[0].text,
        }


