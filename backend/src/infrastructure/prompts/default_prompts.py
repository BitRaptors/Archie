"""Default analysis prompts."""
from domain.entities.analysis_prompt import AnalysisPrompt
from config.constants import PromptCategory


def get_default_prompts() -> list[AnalysisPrompt]:
    """Get all default prompts."""
    return [
        AnalysisPrompt.create(
            name="Structure Analysis",
            category=PromptCategory.STRUCTURE,
            prompt_template="""Analyze the file structure of the repository {repository_name}.

Repository URL: {repository_url}
Technology Stack: {technology_stack}

Please analyze:
1. Directory organization patterns
2. File naming conventions
3. Module structure
4. Technology stack usage

Provide a comprehensive structure analysis.""",
            variables=["repository_name", "repository_url", "technology_stack"],
            is_default=True,
        ),
        AnalysisPrompt.create(
            name="Pattern Discovery",
            category=PromptCategory.PATTERNS,
            prompt_template="""Analyze the codebase and identify all architectural patterns.

Repository: {repository_name}
Patterns Found: {patterns_found}

Focus on:
- Context+Hook patterns
- Query hooks
- Service Registry patterns
- Repository patterns
- Component patterns

Document pattern frequency and variations.""",
            variables=["repository_name", "patterns_found"],
            is_default=True,
        ),
        AnalysisPrompt.create(
            name="Principle Adherence",
            category=PromptCategory.PRINCIPLES,
            prompt_template="""Evaluate adherence to architectural principles.

Repository: {repository_name}
Violations Found: {violations_found}

Check:
- SOLID principles
- Layer boundaries
- Dependency inversion
- Single responsibility
- Open/closed principle

Provide principle adherence analysis.""",
            variables=["repository_name", "violations_found"],
            is_default=True,
        ),
        AnalysisPrompt.create(
            name="Blueprint Synthesis",
            category=PromptCategory.BLUEPRINT_SYNTHESIS,
            prompt_template="""Generate a comprehensive architecture blueprint.

Repository: {repository_name}
Structure Summary: {structure_summary}
Patterns: {patterns_found}
Code Samples: {code_samples}

Create a blueprint with:
1. Structure section
2. Patterns section
3. Principles section
4. Implementation guide

Format as markdown.""",
            variables=["repository_name", "structure_summary", "patterns_found", "code_samples"],
            is_default=True,
        ),
    ]


