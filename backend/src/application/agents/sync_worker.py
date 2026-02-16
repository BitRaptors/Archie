"""Sync worker for detecting changes and triggering incremental updates."""
import logging
import subprocess
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from application.agents.base_worker import BaseWorker
from domain.entities.worker_assignment import WorkerAssignment
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class SyncWorker(BaseWorker):
    """Worker that detects changes and triggers incremental updates.
    
    This worker:
    - Uses git to detect file changes
    - Identifies which architecture rules might be affected
    - Recommends full re-analysis vs incremental update
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None,
        prompt_loader: PromptLoader,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize sync worker."""
        super().__init__(ai_client, prompt_loader, model)
    
    async def execute(
        self,
        assignment: WorkerAssignment,
        repo_path: Path,
    ) -> dict[str, Any]:
        """Execute sync assignment.
        
        Args:
            assignment: Work assignment
            repo_path: Path to repository
            
        Returns:
            Dictionary with change detection results
        """
        assignment.start()
        
        try:
            # Get comparison point from context
            since_commit = assignment.context.get("since_commit")
            since_timestamp = assignment.context.get("since_timestamp")
            
            # Detect changes
            if since_commit:
                changes = await self._detect_changes_since_commit(repo_path, since_commit)
            elif since_timestamp:
                changes = await self._detect_changes_since_time(repo_path, since_timestamp)
            else:
                # Get all uncommitted changes
                changes = await self._detect_uncommitted_changes(repo_path)
            
            # Analyze impact
            existing_rules = assignment.context.get("rules", [])
            affected_rules = self._identify_affected_rules(changes, existing_rules)
            
            # Determine recommendation
            recommendation = self._get_recommendation(changes, affected_rules)
            
            result = {
                "changed_files": changes.get("files", []),
                "added_files": changes.get("added", []),
                "modified_files": changes.get("modified", []),
                "deleted_files": changes.get("deleted", []),
                "affected_rules": affected_rules,
                "recommendation": recommendation,
                "total_changes": len(changes.get("files", [])),
            }
            
            assignment.complete(result)
            return result
            
        except Exception as e:
            logger.error(f"Sync worker failed: {e}")
            assignment.fail(str(e))
            return {
                "error": str(e),
                "changed_files": [],
                "recommendation": "full_analysis",
            }
    
    async def _detect_changes_since_commit(
        self,
        repo_path: Path,
        since_commit: str,
    ) -> dict[str, list[str]]:
        """Detect changes since a specific commit.
        
        Args:
            repo_path: Repository path
            since_commit: Commit hash to compare from
            
        Returns:
            Dictionary with change lists
        """
        try:
            # Get diff against commit
            result = subprocess.run(
                ["git", "diff", "--name-status", since_commit],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            return self._parse_diff_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.warning("Git diff timed out")
            return {"files": [], "added": [], "modified": [], "deleted": []}
        except Exception as e:
            logger.warning(f"Git diff failed: {e}")
            return {"files": [], "added": [], "modified": [], "deleted": []}
    
    async def _detect_changes_since_time(
        self,
        repo_path: Path,
        since_timestamp: str,
    ) -> dict[str, list[str]]:
        """Detect changes since a specific time.
        
        Args:
            repo_path: Repository path
            since_timestamp: ISO timestamp
            
        Returns:
            Dictionary with change lists
        """
        try:
            # Get commits since timestamp
            result = subprocess.run(
                ["git", "log", f"--since={since_timestamp}", "--name-status", "--oneline"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            return self._parse_log_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.warning("Git log timed out")
            return {"files": [], "added": [], "modified": [], "deleted": []}
        except Exception as e:
            logger.warning(f"Git log failed: {e}")
            return {"files": [], "added": [], "modified": [], "deleted": []}
    
    async def _detect_uncommitted_changes(
        self,
        repo_path: Path,
    ) -> dict[str, list[str]]:
        """Detect uncommitted changes.
        
        Args:
            repo_path: Repository path
            
        Returns:
            Dictionary with change lists
        """
        try:
            # Get status
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            return self._parse_status_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.warning("Git status timed out")
            return {"files": [], "added": [], "modified": [], "deleted": []}
        except Exception as e:
            logger.warning(f"Git status failed: {e}")
            return {"files": [], "added": [], "modified": [], "deleted": []}
    
    def _parse_diff_output(self, output: str) -> dict[str, list[str]]:
        """Parse git diff --name-status output.
        
        Args:
            output: Git diff output
            
        Returns:
            Parsed changes
        """
        files = []
        added = []
        modified = []
        deleted = []
        
        for line in output.strip().split("\n"):
            if not line:
                continue
            
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            
            status, file_path = parts
            files.append(file_path)
            
            if status.startswith("A"):
                added.append(file_path)
            elif status.startswith("M"):
                modified.append(file_path)
            elif status.startswith("D"):
                deleted.append(file_path)
        
        return {
            "files": files,
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }
    
    def _parse_log_output(self, output: str) -> dict[str, list[str]]:
        """Parse git log --name-status output.
        
        Args:
            output: Git log output
            
        Returns:
            Parsed changes
        """
        files = set()
        added = set()
        modified = set()
        deleted = set()
        
        for line in output.strip().split("\n"):
            if not line or not line[0] in "AMD":
                continue
            
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            
            status, file_path = parts
            files.add(file_path)
            
            if status.startswith("A"):
                added.add(file_path)
            elif status.startswith("M"):
                modified.add(file_path)
            elif status.startswith("D"):
                deleted.add(file_path)
        
        return {
            "files": list(files),
            "added": list(added),
            "modified": list(modified),
            "deleted": list(deleted),
        }
    
    def _parse_status_output(self, output: str) -> dict[str, list[str]]:
        """Parse git status --porcelain output.
        
        Args:
            output: Git status output
            
        Returns:
            Parsed changes
        """
        files = []
        added = []
        modified = []
        deleted = []
        
        for line in output.strip().split("\n"):
            if not line or len(line) < 4:
                continue
            
            status = line[:2]
            file_path = line[3:]
            files.append(file_path)
            
            if "A" in status or "?" in status:
                added.append(file_path)
            elif "M" in status:
                modified.append(file_path)
            elif "D" in status:
                deleted.append(file_path)
        
        return {
            "files": files,
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }
    
    def _identify_affected_rules(
        self,
        changes: dict[str, list[str]],
        existing_rules: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify which rules might be affected by changes.
        
        Args:
            changes: Change lists
            existing_rules: Existing architecture rules
            
        Returns:
            List of affected rules
        """
        affected = []
        changed_files = set(changes.get("files", []))
        
        for rule in existing_rules:
            source_files = rule.get("source_files", [])
            rule_data = rule.get("rule_data", {})
            
            # Check if any source file changed
            if source_files:
                if set(source_files) & changed_files:
                    affected.append({
                        "rule_id": rule.get("rule_id"),
                        "rule_type": rule.get("rule_type"),
                        "reason": "source_file_changed",
                    })
                    continue
            
            # Check if rule_data references changed files
            rule_file = rule_data.get("file")
            if rule_file and rule_file in changed_files:
                affected.append({
                    "rule_id": rule.get("rule_id"),
                    "rule_type": rule.get("rule_type"),
                    "reason": "referenced_file_changed",
                })
                continue
            
            # Check imports
            imports = rule_data.get("imports", [])
            if imports and set(imports) & changed_files:
                affected.append({
                    "rule_id": rule.get("rule_id"),
                    "rule_type": rule.get("rule_type"),
                    "reason": "imported_file_changed",
                })
        
        return affected
    
    def _get_recommendation(
        self,
        changes: dict[str, list[str]],
        affected_rules: list[dict[str, Any]],
    ) -> str:
        """Get recommendation for how to handle changes.
        
        Args:
            changes: Change information
            affected_rules: Rules affected by changes
            
        Returns:
            Recommendation string
        """
        total_changes = len(changes.get("files", []))
        added_files = len(changes.get("added", []))
        deleted_files = len(changes.get("deleted", []))
        affected_count = len(affected_rules)
        
        # If many files changed, recommend full analysis
        if total_changes > 20:
            return "full_analysis"
        
        # If many files added/deleted, recommend full analysis
        if added_files > 5 or deleted_files > 5:
            return "full_analysis"
        
        # If many rules affected, recommend full analysis
        if affected_count > 10:
            return "full_analysis"
        
        # If some changes but not too many
        if total_changes > 0:
            return "incremental_update"
        
        # No changes
        return "no_action"
