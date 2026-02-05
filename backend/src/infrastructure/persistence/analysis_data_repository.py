"""Analysis data repository implementation for storing debug/intermediate data."""
from typing import Any
from supabase import Client
from postgrest.exceptions import APIError


class SupabaseAnalysisDataRepository:
    """Supabase implementation of analysis data repository.
    
    Used to store and retrieve debug data collected during analysis phases.
    Data types include:
    - debug_gathered: Initial gathered data from codebase
    - debug_phase_{name}: Per-phase analysis data
    - debug_summary: Summary metrics
    """

    TABLE = "analysis_data"

    def __init__(self, client: Client):
        """Initialize analysis data repository."""
        self._client = client

    async def get_by_analysis_id(self, analysis_id: str) -> list[dict]:
        """Get all data entries for a specific analysis.
        
        Args:
            analysis_id: The analysis UUID
            
        Returns:
            List of data entries with data_type and data fields
        """
        try:
            result = await (
                self._client.table(self.TABLE)
                .select("*")
                .eq("analysis_id", analysis_id)
                .order("created_at", desc=False)
                .execute()
            )
            return result.data if result.data else []
        except APIError as e:
            if e.code == "204" or "204" in str(e):
                return []
            raise

    async def get_by_type(self, analysis_id: str, data_type: str) -> dict | None:
        """Get a specific data entry by analysis_id and data_type.
        
        Args:
            analysis_id: The analysis UUID
            data_type: The type of data (e.g., 'debug_gathered')
            
        Returns:
            The data entry or None if not found
        """
        try:
            result = await (
                self._client.table(self.TABLE)
                .select("*")
                .eq("analysis_id", analysis_id)
                .eq("data_type", data_type)
                .maybe_single()
                .execute()
            )
            return result.data if result and result.data else None
        except APIError as e:
            if e.code == "204" or "204" in str(e):
                return None
            raise

    async def upsert(self, analysis_id: str, data_type: str, data: dict) -> dict:
        """Insert or update a data entry.
        
        If an entry with the same analysis_id and data_type exists, it updates.
        Otherwise, creates a new entry.
        
        Args:
            analysis_id: The analysis UUID
            data_type: The type of data
            data: The JSONB data to store
            
        Returns:
            The created/updated entry
        """
        # Check if entry exists
        existing = await self.get_by_type(analysis_id, data_type)
        
        if existing:
            # Update existing entry
            result = await (
                self._client.table(self.TABLE)
                .update({"data": data})
                .eq("id", existing["id"])
                .execute()
            )
        else:
            # Insert new entry
            result = await (
                self._client.table(self.TABLE)
                .insert({
                    "analysis_id": analysis_id,
                    "data_type": data_type,
                    "data": data,
                })
                .execute()
            )
        
        return result.data[0] if result.data else {}

    async def delete_by_analysis_id(self, analysis_id: str) -> int:
        """Delete all data entries for an analysis.
        
        Args:
            analysis_id: The analysis UUID
            
        Returns:
            Number of entries deleted
        """
        result = await (
            self._client.table(self.TABLE)
            .delete()
            .eq("analysis_id", analysis_id)
            .execute()
        )
        return len(result.data) if result.data else 0

    async def delete_by_type(self, analysis_id: str, data_type: str) -> bool:
        """Delete a specific data entry.
        
        Args:
            analysis_id: The analysis UUID
            data_type: The type of data to delete
            
        Returns:
            True if deleted, False if not found
        """
        result = await (
            self._client.table(self.TABLE)
            .delete()
            .eq("analysis_id", analysis_id)
            .eq("data_type", data_type)
            .execute()
        )
        return len(result.data) > 0 if result.data else False
