"""Debug data collector for analysis pipeline."""
from typing import Any, Dict, List
import json
from datetime import datetime

class DebugCollector:
    """Collects and stores debug information during the analysis process.
    
    This information includes:
    1. Gathered data (structure, dependencies, config files)
    2. Exact prompts sent to AI
    3. Truncation metrics
    4. RAG retrieval results
    """
    
    def __init__(self):
        # keyed by analysis_id: { "gathered": {...}, "phases": [...], "summary": {...} }
        self._debug_data: Dict[str, Dict[str, Any]] = {}

    def get_data(self, analysis_id: str) -> Dict[str, Any]:
        """Get debug data for a specific analysis."""
        return self._debug_data.get(analysis_id, {
            "gathered": {},
            "phases": [],
            "summary": {}
        })

    def capture_gathered_data(self, analysis_id: str, data: Dict[str, Any]) -> None:
        """Capture the initial gathered data from the codebase."""
        if analysis_id not in self._debug_data:
            self._debug_data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        self._debug_data[analysis_id]["gathered"] = {
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

    def capture_phase_data(self, analysis_id: str, phase_name: str, gathered: Dict[str, Any], sent: Dict[str, Any], rag_retrieved: Dict[str, Any] = None) -> None:
        """Capture data for a specific analysis phase."""
        if analysis_id not in self._debug_data:
            self._debug_data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        phase_info = {
            "phase": phase_name,
            "timestamp": datetime.utcnow().isoformat(),
            "gathered": gathered,
            "sent_to_ai": sent,
            "rag_retrieved": rag_retrieved or {}
        }
        
        self._debug_data[analysis_id]["phases"].append(phase_info)
        self._update_summary(analysis_id)

    def capture_rag_stats(self, analysis_id: str, stats: Dict[str, Any]) -> None:
        """Update RAG indexing statistics."""
        if analysis_id not in self._debug_data:
            self._debug_data[analysis_id] = {"gathered": {}, "phases": [], "summary": {}}
            
        if "gathered" not in self._debug_data[analysis_id]:
            self._debug_data[analysis_id]["gathered"] = {}
            
        self._debug_data[analysis_id]["gathered"]["rag_indexing"] = stats
        self._update_summary(analysis_id)

    def _update_summary(self, analysis_id: str) -> None:
        """Update the overall summary for the analysis."""
        if analysis_id not in self._debug_data:
            return
            
        phases = self._debug_data[analysis_id]["phases"]
        gathered = self._debug_data[analysis_id]["gathered"]
        
        # Calculate some high-level metrics
        total_chars_sent = 0
        for phase in phases:
            sent = phase.get("sent_to_ai", {})
            for key, val in sent.items():
                if isinstance(val, dict) and "char_count" in val:
                    total_chars_sent += val["char_count"]
                elif key == "full_prompt":
                    total_chars_sent += len(val)
                    
        self._debug_data[analysis_id]["summary"] = {
            "phase_count": len(phases),
            "total_chars_sent": total_chars_sent,
            "last_updated": datetime.utcnow().isoformat()
        }

# Global instance for easy access across services
debug_collector = DebugCollector()

