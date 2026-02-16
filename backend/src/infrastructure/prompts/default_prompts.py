"""Default analysis prompts - loaded from prompts.json."""
from infrastructure.prompts.prompt_loader import PromptLoader

# Global prompt loader instance
_prompt_loader = PromptLoader()


def get_default_prompts() -> list:
    """Get all prompts from prompts.json (all prompts are defaults now)."""
    return _prompt_loader.get_all_default_prompts()


