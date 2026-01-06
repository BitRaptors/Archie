"""Blueprint generator."""
from typing import Any
from application.services.prompt_service import PromptService
from infrastructure.ai.blueprint_analyzer import BlueprintAnalyzer
from config.constants import PromptCategory


class BlueprintGenerator:
    """Generates architecture blueprints."""

    def __init__(
        self,
        prompt_service: PromptService,
        blueprint_analyzer: BlueprintAnalyzer,
    ):
        """Initialize blueprint generator."""
        self._prompt_service = prompt_service
        self._analyzer = blueprint_analyzer

    async def generate(
        self,
        repository_id: str,
        structure_data: dict[str, Any],
        patterns: dict[str, Any],
        ai_analysis: dict[str, Any],
        prompt_config: dict[str, str] | None = None,
    ) -> str:
        """Generate blueprint markdown."""
        # Summarize data to avoid token limits (Cursor-like approach)
        structure_summary = self._summarize_structure(structure_data)
        patterns_summary = self._summarize_patterns(patterns)
        analysis_summary = self._summarize_ai_analysis(ai_analysis)
        
        # Get blueprint synthesis prompt
        prompt_id = prompt_config.get(PromptCategory.BLUEPRINT_SYNTHESIS) if prompt_config else None
        
        if prompt_id:
            prompt = await self._prompt_service.get_prompt(prompt_id)
            synthesis_prompt = prompt.render({
                "repository_name": repository_id,
                "structure_summary": structure_summary,
                "patterns_found": patterns_summary,
                "ai_analysis": analysis_summary,
                "code_samples": "",
            })
        else:
            synthesis_prompt = f"""Generate a comprehensive architecture blueprint for repository: {repository_id}

Directory Structure:
{structure_summary}

Architectural Patterns:
{patterns_summary}

AI Analysis Summary:
{analysis_summary}

Format as markdown with sections:
1. Overview
2. Architecture Structure
3. Key Patterns and Design Decisions
4. Technology Stack
5. Code Organization
6. Recommendations
"""
        
        # Use analyzer to generate blueprint
        response = self._analyzer._client.messages.create(
            model=self._analyzer._model,
            max_tokens=4000,  # Set to 4000 to support Haiku (max 4096)
            messages=[{
                "role": "user",
                "content": synthesis_prompt,
            }],
        )
        
        return response.content[0].text
    
    def _summarize_structure(self, structure_data: dict[str, Any]) -> str:
        """Create a concise summary of structure data."""
        summary_parts = []
        
        if structure_data.get("technologies"):
            summary_parts.append(f"Technologies: {', '.join(structure_data['technologies'])}")
        
        dir_structure = structure_data.get("directory_structure", {})
        if dir_structure:
            root_files = dir_structure.get("root_files", [])
            if root_files:
                summary_parts.append(f"Root files ({len(root_files)}): {', '.join(root_files[:10])}")
            
            src_structure = dir_structure.get("src_structure", {})
            if src_structure:
                subdirs = src_structure.get("subdirectories", [])
                if subdirs:
                    summary_parts.append(f"Main directories: {', '.join(subdirs[:15])}")
        
        file_tree = structure_data.get("file_tree", [])
        if file_tree:
            file_counts = {}
            for item in file_tree:
                if item.get("type") == "file":
                    ext = item.get("extension", "")
                    file_counts[ext] = file_counts.get(ext, 0) + 1
            
            file_summary = ", ".join([f"{ext or 'no-ext'}: {count}" for ext, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]])
            summary_parts.append(f"File types: {file_summary}")
            summary_parts.append(f"Total files: {len([f for f in file_tree if f.get('type') == 'file'])}")
        
        return "\n".join(summary_parts) if summary_parts else "No structure data"
    
    def _summarize_patterns(self, patterns: dict[str, Any]) -> str:
        """Create a concise summary of patterns."""
        summary_parts = []
        
        structural = patterns.get("structural", {})
        if structural:
            pattern_types = list(structural.keys())[:10]
            summary_parts.append(f"Structural patterns: {', '.join(pattern_types)}")
        
        semantic = patterns.get("semantic", {})
        if semantic:
            if isinstance(semantic, dict):
                pattern_names = list(semantic.keys())[:10]
                summary_parts.append(f"Semantic patterns: {', '.join(pattern_names)}")
        
        combined = patterns.get("combined", {})
        if combined:
            summary_parts.append(f"Key combined patterns: {len(combined)} identified")
        
        return "\n".join(summary_parts) if summary_parts else "No patterns detected"
    
    def _summarize_ai_analysis(self, ai_analysis: dict[str, Any]) -> str:
        """Create a concise summary of AI analysis."""
        summary_parts = []
        
        if "directory_summaries" in ai_analysis:
            dir_summary = ai_analysis["directory_summaries"].get("summary", "")
            if dir_summary:
                # Truncate if too long
                summary_parts.append(f"Directory Analysis: {dir_summary[:500]}...")
        
        if "pattern_analysis" in ai_analysis:
            pattern_analysis = ai_analysis["pattern_analysis"].get("analysis", "")
            if pattern_analysis:
                summary_parts.append(f"Pattern Analysis: {pattern_analysis[:500]}...")
        
        if "principles" in ai_analysis:
            principles = ai_analysis["principles"].get("evaluation", "")
            if principles:
                summary_parts.append(f"Principles: {principles[:500]}...")
        
        return "\n".join(summary_parts) if summary_parts else "No AI analysis available"


