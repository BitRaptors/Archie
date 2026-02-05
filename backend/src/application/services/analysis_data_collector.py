"""Analysis data collector for pipeline with Supabase persistence."""
from typing import Any, Dict
from datetime import datetime, timezone
from infrastructure.persistence.analysis_data_repository import SupabaseAnalysisDataRepository


class AnalysisDataCollector:
    """Collects and stores analysis data during the analysis process.
    
    This information includes:
    1. Gathered data (structure, dependencies, config files)
    2. Exact prompts sent to AI
    3. Truncation metrics
    4. RAG retrieval results
    
    Data is persisted to Supabase so it can be accessed across processes (worker -> API).
    """
    
    def __init__(self):
        # In-memory cache keyed by analysis_id for performance during analysis
        self._data: Dict[str, Dict[str, Any]] = {}
        # Repository for Supabase persistence (initialized later)
        self._repository: SupabaseAnalysisDataRepository | None = None
        self._initialized = False
    
    def initialize(self, supabase_client) -> None:
        """Initialize the collector with a Supabase client.
        
        Must be called before any async operations.
        
        Args:
            supabase_client: The Supabase async client
        """
        self._repository = SupabaseAnalysisDataRepository(supabase_client)
        self._initialized = True
    
    @property
    def is_initialized(self) -> bool:
        """Check if the collector has been initialized."""
        return self._initialized and self._repository is not None

    async def get_data(self, analysis_id: str) -> Dict[str, Any]:
        """Get analysis data for a specific analysis.
        
        First checks memory cache, then loads from Supabase if not found.
        If cached data has no phases, reloads from Supabase (handles cross-process data).
        
        Args:
            analysis_id: The analysis UUID
            
        Returns:
            Analysis data dict with gathered, phases, and summary
        """
        # Check memory cache first
        if analysis_id in self._data:
            cached = self._data[analysis_id]
            # If cached data has no phases, try reloading from Supabase
            # This handles the case where worker saved data but API has stale cache
            if not cached.get("phases") and self.is_initialized:
                data = await self._load_from_supabase(analysis_id)
                if data.get("phases"):
                    self._data[analysis_id] = data
                    return data
            return cached
        
        # Load from Supabase if initialized
        if self.is_initialized:
            data = await self._load_from_supabase(analysis_id)
            # Cache in memory for future access
            if data.get("phases") or data.get("gathered"):
                self._data[analysis_id] = data
            return data
        
        # Return empty structure if not initialized
        return {"gathered": {}, "phases": [], "summary": {}}
    
    async def _load_from_supabase(self, analysis_id: str) -> Dict[str, Any]:
        """Load analysis data from Supabase.
        
        Reconstructs the data structure from multiple rows in analysis_data table.
        """
        if not self._repository:
            return {"gathered": {}, "phases": [], "summary": {}}
        
        try:
            rows = await self._repository.get_by_analysis_id(analysis_id)
            
            result = {"gathered": {}, "phases": [], "summary": {}}
            
            for row in rows:
                data_type = row.get("data_type", "")
                data = row.get("data", {})
                
                if data_type == "gathered":
                    result["gathered"] = data
                elif data_type == "summary":
                    result["summary"] = data
                elif data_type.startswith("phase_"):
                    # Phase data is stored with the phase info in data
                    result["phases"].append(data)
            
            # Sort phases by timestamp if present
            result["phases"].sort(key=lambda p: p.get("timestamp", ""))
            
            return result
        except Exception as e:
            print(f"Warning: Could not load analysis data for {analysis_id}: {e}")
            return {"gathered": {}, "phases": [], "summary": {}}
    
    async def _save_to_supabase(self, analysis_id: str, data_type: str, data: Dict[str, Any]) -> None:
        """Save analysis data to Supabase."""
        if not self._repository:
            return
        
        try:
            await self._repository.upsert(analysis_id, data_type, data)
        except Exception as e:
            print(f"Warning: Could not save analysis data ({data_type}) for {analysis_id}: {e}")

    async def capture_gathered_data(self, analysis_id: str, data: Dict[str, Any]) -> None:
        """Capture the initial gathered data from the codebase."""
        if analysis_id not in self._data:
            self._data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        gathered = {
            "file_tree": {
                "full_content": data.get("file_tree_raw", ""),
                "char_count": len(data.get("file_tree_raw", ""))
            },
            "dependencies": {
                "full_content": data.get("dependencies_raw", ""),
                "char_count": len(data.get("dependencies_raw", ""))
            },
            "config_files": {
                "files": [
                    {"name": name, "content": content, "char_count": len(content)}
                    for name, content in data.get("config_files", {}).items()
                ],
                "total_chars": sum(len(c) for c in data.get("config_files", {}).values())
            },
            "code_samples": {
                "files": [
                    {"name": name, "content": content, "char_count": len(content)}
                    for name, content in data.get("code_samples", {}).items()
                ],
                "total_chars": sum(len(c) for c in data.get("code_samples", {}).values())
            },
            "rag_indexing": data.get("rag_indexing", {})
        }
        
        self._data[analysis_id]["gathered"] = gathered
        
        # Persist to Supabase
        if self.is_initialized:
            await self._save_to_supabase(analysis_id, "gathered", gathered)

    async def capture_phase_data(
        self, 
        analysis_id: str, 
        phase_name: str, 
        gathered: Dict[str, Any], 
        sent: Dict[str, Any], 
        rag_retrieved: Dict[str, Any] = None
    ) -> None:
        """Capture data for a specific analysis phase."""
        if analysis_id not in self._data:
            self._data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        phase_info = {
            "phase": phase_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "gathered": gathered,
            "sent_to_ai": sent,
            "rag_retrieved": rag_retrieved or {}
        }
        
        self._data[analysis_id]["phases"].append(phase_info)
        self._update_summary(analysis_id)
        
        # Persist to Supabase - use unique key per phase
        if self.is_initialized:
            await self._save_to_supabase(analysis_id, f"phase_{phase_name}", phase_info)
            # Also update summary
            await self._save_to_supabase(
                analysis_id, 
                "summary", 
                self._data[analysis_id]["summary"]
            )

    async def capture_rag_stats(self, analysis_id: str, stats: Dict[str, Any]) -> None:
        """Update RAG indexing statistics."""
        if analysis_id not in self._data:
            self._data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        if "gathered" not in self._data[analysis_id]:
            self._data[analysis_id]["gathered"] = {}
            
        self._data[analysis_id]["gathered"]["rag_indexing"] = stats
        self._update_summary(analysis_id)
        
        # Persist updated gathered data to Supabase
        if self.is_initialized:
            await self._save_to_supabase(
                analysis_id, 
                "gathered", 
                self._data[analysis_id]["gathered"]
            )

    def _update_summary(self, analysis_id: str) -> None:
        """Update the overall summary for the analysis."""
        if analysis_id not in self._data:
            return
            
        phases = self._data[analysis_id]["phases"]
        
        # Calculate some high-level metrics
        total_chars_sent = 0
        for phase in phases:
            sent = phase.get("sent_to_ai", {})
            for key, val in sent.items():
                if isinstance(val, dict) and "char_count" in val:
                    total_chars_sent += val["char_count"]
                elif key == "full_prompt":
                    total_chars_sent += len(val)
                    
        self._data[analysis_id]["summary"] = {
            "phase_count": len(phases),
            "total_chars_sent": total_chars_sent,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }


# Global instance for easy access across services
analysis_data_collector = AnalysisDataCollector()
