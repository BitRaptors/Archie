"""Seed default prompts from prompts.json into the database."""
import json
import logging
from pathlib import Path
from domain.entities.analysis_prompt import AnalysisPrompt
from infrastructure.persistence.prompt_repository import PromptRepository

logger = logging.getLogger(__name__)


async def seed_default_prompts(
    prompt_repo: PromptRepository,
    prompts_file: Path | None = None,
) -> int:
    """Seed default prompts from prompts.json if the DB is empty.

    Args:
        prompt_repo: The prompt repository to seed into.
        prompts_file: Path to prompts.json. Defaults to ``backend/prompts.json``.

    Returns:
        Number of prompts inserted (0 if already populated).
    """
    existing_count = await prompt_repo.count_defaults()
    if existing_count > 0:
        logger.info(
            "Prompt seeder: %d default prompts already exist, skipping seed",
            existing_count,
        )
        return 0

    if prompts_file is None:
        prompts_file = Path(__file__).parent.parent.parent.parent / "prompts.json"

    if not prompts_file.exists():
        logger.warning("Prompt seeder: %s not found, skipping seed", prompts_file)
        return 0

    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompts_data = data.get("prompts", {})
    count = 0

    for key, prompt_data in prompts_data.items():
        prompt = AnalysisPrompt.create(
            name=prompt_data["name"],
            category=prompt_data["category"],
            prompt_template=prompt_data["prompt_template"],
            variables=prompt_data.get("variables", []),
            is_default=True,
            key=key,
            description=prompt_data.get("description"),
        )
        await prompt_repo.add(prompt)
        count += 1

    logger.info("Prompt seeder: inserted %d default prompts from prompts.json", count)
    return count
