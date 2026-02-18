"""Seed analysis_prompts table from prompts.json.

Reads prompts.json (the single source of truth for prompt content) and
upserts each prompt into the analysis_prompts table. Existing rows are
updated; new rows are inserted.

Usage:
    cd backend && PYTHONPATH=src python scripts/seed_prompts.py
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def seed_prompts() -> None:
    """Read prompts.json and upsert into analysis_prompts table."""
    from infrastructure.persistence.db_factory import create_db, shutdown_db

    prompts_file = Path(__file__).parent.parent / "prompts.json"
    if not prompts_file.exists():
        print(f"Error: {prompts_file} not found")
        sys.exit(1)

    with open(prompts_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompts = data.get("prompts", {})
    if not prompts:
        print("No prompts found in prompts.json")
        sys.exit(1)

    print(f"Found {len(prompts)} prompts in prompts.json")

    db = await create_db()

    inserted = 0
    updated = 0

    for key, prompt_data in prompts.items():
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "name": prompt_data["name"],
            "category": prompt_data["category"],
            "prompt_template": prompt_data["prompt_template"],
            "variables": prompt_data.get("variables", []),
            "is_default": prompt_data.get("is_default", True),
            "key": key,
            "type": "prompt",
            "updated_at": now,
        }

        # Check if exists
        existing = await (
            db.table("analysis_prompts")
            .select("id")
            .eq("key", key)
            .maybe_single()
            .execute()
        )

        if existing and existing.data:
            # Update existing
            await (
                db.table("analysis_prompts")
                .update(row)
                .eq("key", key)
                .execute()
            )
            updated += 1
            print(f"  Updated: {key} ({prompt_data['name']})")
        else:
            # Insert new
            row["created_at"] = now
            await (
                db.table("analysis_prompts")
                .insert(row)
                .execute()
            )
            inserted += 1
            print(f"  Inserted: {key} ({prompt_data['name']})")

    print(f"\nDone: {inserted} inserted, {updated} updated")

    await shutdown_db()


if __name__ == "__main__":
    asyncio.run(seed_prompts())
