"""Service for syncing reference blueprints from DOCS/ into the database."""
import logging
from pathlib import Path
from typing import Any

from application.services.architecture_extractor import ArchitectureExtractor
from domain.entities.architecture_rule import ArchitectureRule
from domain.interfaces.repositories import IArchitectureRuleRepository

logger = logging.getLogger(__name__)


# Mapping from DOCS file names to blueprint IDs
BLUEPRINT_MAPPING = {
    "PYTHON_ARCHITECTURE_BLUEPRINT.md": "python-backend",
    "FRONTEND_ARCHITECTURE_BLUEPRINT.md": "nextjs-frontend",
}


class ReferenceBlueprintSync:
    """Syncs reference blueprints from DOCS/ directory into the database.
    
    This tool reads markdown blueprints from the DOCS/ directory,
    extracts structured rules using the ArchitectureExtractor,
    and stores them in the architecture_rules table.
    """
    
    def __init__(
        self,
        docs_dir: Path,
        architecture_rule_repo: IArchitectureRuleRepository,
        extractor: ArchitectureExtractor | None = None,
    ):
        """Initialize sync service.
        
        Args:
            docs_dir: Path to DOCS/ directory containing blueprints
            architecture_rule_repo: Repository for storing rules
            extractor: Optional extractor (creates one if not provided)
        """
        self._docs_dir = docs_dir
        self._repo = architecture_rule_repo
        self._extractor = extractor or ArchitectureExtractor()
    
    async def sync_all(self) -> dict[str, Any]:
        """Sync all reference blueprints from DOCS/.
        
        Returns:
            Summary of sync operation
        """
        results = {
            "synced": [],
            "failed": [],
            "total_rules": 0,
        }
        
        # Find all blueprint files
        for file_name, blueprint_id in BLUEPRINT_MAPPING.items():
            blueprint_path = self._docs_dir / file_name
            
            if not blueprint_path.exists():
                # Check in subdirectories
                for subdir in ["backend", "frontend"]:
                    alt_path = self._docs_dir / subdir / file_name
                    if alt_path.exists():
                        blueprint_path = alt_path
                        break
            
            if blueprint_path.exists():
                try:
                    count = await self.sync_blueprint(blueprint_path, blueprint_id)
                    results["synced"].append({
                        "blueprint_id": blueprint_id,
                        "file": str(blueprint_path),
                        "rules_count": count,
                    })
                    results["total_rules"] += count
                except Exception as e:
                    logger.error(f"Failed to sync {blueprint_id}: {e}")
                    results["failed"].append({
                        "blueprint_id": blueprint_id,
                        "file": str(blueprint_path),
                        "error": str(e),
                    })
            else:
                logger.warning(f"Blueprint file not found: {file_name}")
                results["failed"].append({
                    "blueprint_id": blueprint_id,
                    "file": file_name,
                    "error": "File not found",
                })
        
        # Also scan for any other markdown files in DOCS
        await self._scan_additional_blueprints(results)
        
        logger.info(
            f"Sync complete: {len(results['synced'])} blueprints, "
            f"{results['total_rules']} rules"
        )
        
        return results
    
    async def sync_blueprint(
        self,
        blueprint_path: Path,
        blueprint_id: str,
    ) -> int:
        """Sync a single blueprint file.
        
        Args:
            blueprint_path: Path to the blueprint file
            blueprint_id: ID to use for this blueprint
            
        Returns:
            Number of rules extracted and stored
        """
        logger.info(f"Syncing blueprint: {blueprint_id} from {blueprint_path}")
        
        # Read blueprint content
        content = blueprint_path.read_text(encoding="utf-8")
        
        # Delete existing rules for this blueprint
        deleted_count = await self._repo.delete_by_blueprint_id(blueprint_id)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} existing rules for {blueprint_id}")
        
        # Extract rules
        rules = await self._extractor.extract_from_blueprint(content, blueprint_id)
        
        # Store rules
        stored_count = 0
        for rule in rules:
            try:
                await self._repo.add(rule)
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store rule {rule.rule_id}: {e}")
        
        logger.info(f"Stored {stored_count} rules for {blueprint_id}")
        
        return stored_count
    
    async def _scan_additional_blueprints(self, results: dict[str, Any]) -> None:
        """Scan for additional blueprint files not in the mapping.
        
        Args:
            results: Results dictionary to update
        """
        # Look for other markdown files that might be blueprints
        for md_file in self._docs_dir.rglob("*.md"):
            # Skip index files and already processed
            if md_file.name.startswith("_"):
                continue
            
            # Check if this is a blueprint file
            file_name = md_file.name
            if file_name in BLUEPRINT_MAPPING:
                continue
            
            # Check if it looks like a blueprint
            content = md_file.read_text(encoding="utf-8")
            if self._looks_like_blueprint(content):
                # Generate blueprint ID from filename
                blueprint_id = md_file.stem.lower().replace("_", "-").replace(" ", "-")
                
                # Skip if already synced
                if any(r["blueprint_id"] == blueprint_id for r in results["synced"]):
                    continue
                
                try:
                    count = await self.sync_blueprint(md_file, blueprint_id)
                    results["synced"].append({
                        "blueprint_id": blueprint_id,
                        "file": str(md_file),
                        "rules_count": count,
                    })
                    results["total_rules"] += count
                except Exception as e:
                    logger.warning(f"Failed to sync additional blueprint {blueprint_id}: {e}")
    
    def _looks_like_blueprint(self, content: str) -> bool:
        """Check if content looks like an architecture blueprint.
        
        Args:
            content: File content
            
        Returns:
            True if it looks like a blueprint
        """
        # Check for common blueprint indicators
        indicators = [
            "# Architecture",
            "## Layer",
            "## Pattern",
            "## Principle",
            "Architecture Blueprint",
            "Layer Architecture",
            "Design Patterns",
        ]
        
        content_lower = content.lower()
        matches = sum(1 for ind in indicators if ind.lower() in content_lower)
        
        return matches >= 2


async def create_sync_cli():
    """CLI function for syncing blueprints."""
    import argparse
    import asyncio
    
    from supabase import create_client
    
    from config.settings import settings
    from infrastructure.persistence.supabase_adapter import SupabaseAdapter
    from infrastructure.persistence.architecture_rule_repository import (
        ArchitectureRuleRepository,
    )
    
    parser = argparse.ArgumentParser(description="Sync reference blueprints to database")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent.parent / "DOCS",
        help="Path to DOCS directory",
    )
    parser.add_argument(
        "--blueprint-id",
        type=str,
        help="Sync only a specific blueprint",
    )
    
    args = parser.parse_args()
    
    # Create Supabase client and wrap in adapter
    client = create_client(settings.supabase_url, settings.supabase_key)
    db = SupabaseAdapter(client)
    
    # Create repository
    repo = ArchitectureRuleRepository(db)
    
    # Create sync service
    sync = ReferenceBlueprintSync(args.docs_dir, repo)
    
    if args.blueprint_id:
        # Sync specific blueprint
        for file_name, bid in BLUEPRINT_MAPPING.items():
            if bid == args.blueprint_id:
                path = args.docs_dir / file_name
                count = await sync.sync_blueprint(path, bid)
                print(f"Synced {count} rules for {bid}")
                return
        print(f"Unknown blueprint ID: {args.blueprint_id}")
    else:
        # Sync all
        results = await sync.sync_all()
        print(f"Synced {len(results['synced'])} blueprints with {results['total_rules']} total rules")
        if results["failed"]:
            print(f"Failed: {len(results['failed'])} blueprints")
            for f in results["failed"]:
                print(f"  - {f['blueprint_id']}: {f['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(create_sync_cli())
