"""
Handoff Log System for Task 6 — stores real-time history of every agent-to-agent handoff.
Not just the last status, but a full historical log with complete details.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json

class HandoffEntry:
    """Single handoff entry in the log."""
    
    def __init__(self, 
                 timestamp: str,
                 source_agent: str,
                 target_agent: Optional[str],
                 status: str,
                 message: str,
                 input_keys: List[str],
                 output_keys: List[str],
                 details: Dict[str, Any] = None):
        self.timestamp = timestamp
        self.source_agent = source_agent
        self.target_agent = target_agent
        self.status = status
        self.message = message
        self.input_keys = input_keys
        self.output_keys = output_keys
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "status": self.status,
            "message": self.message,
            "input_keys": self.input_keys,
            "output_keys": self.output_keys,
            "details": self.details
        }


class HandoffLog:
    """Comprehensive handoff log for a single session."""
    
    def __init__(self, session_id: str, repo_url: str):
        self.session_id = session_id
        self.repo_url = repo_url
        self.created_at = datetime.now().isoformat()
        self.entries: List[HandoffEntry] = []
        self.status = "in_progress"
        self.total_steps = 4  # Explorer -> Documenter -> Mentor -> TaskSuggester
        self.completed_steps = 0
    
    def log_handoff(self,
                    source_agent: str,
                    target_agent: Optional[str],
                    status: str,
                    message: str,
                    input_keys: List[str] = None,
                    output_keys: List[str] = None,
                    details: Dict[str, Any] = None) -> None:
        """
        Log a handoff between agents.
        
        Args:
            source_agent: The sending agent
            target_agent: The receiving agent (can be None for final results)
            status: "success", "error", "processing"
            message: Handoff description
            input_keys: Data keys sent
            output_keys: Data keys produced
            details: Additional detail information
        """
        
        timestamp = datetime.now().isoformat()
        entry = HandoffEntry(
            timestamp=timestamp,
            source_agent=source_agent,
            target_agent=target_agent,
            status=status,
            message=message,
            input_keys=input_keys or [],
            output_keys=output_keys or [],
            details=details or {}
        )
        
        self.entries.append(entry)
        
        if status == "success":
            self.completed_steps += 1
        
        # Update overall status
        if status == "error":
            self.status = "failed"
        elif self.completed_steps == self.total_steps:
            self.status = "completed"
    
    def get_entry(self, index: int) -> Optional[HandoffEntry]:
        """Get entry by index."""
        if 0 <= index < len(self.entries):
            return self.entries[index]
        return None
    
    def get_entries_for_agent(self, agent_name: str) -> List[HandoffEntry]:
        """Get all entries involving a specific agent."""
        return [e for e in self.entries if e.source_agent == agent_name or e.target_agent == agent_name]
    
    def get_latest_entry(self) -> Optional[HandoffEntry]:
        """Get latest entry."""
        return self.entries[-1] if self.entries else None
    
    def get_step_summary(self) -> Dict[str, Any]:
        """Get summary of all steps."""
        return {
            "session_id": self.session_id,
            "repo_url": self.repo_url,
            "created_at": self.created_at,
            "status": self.status,
            "progress": f"{self.completed_steps}/{self.total_steps}",
            "total_entries": len(self.entries),
            "entries": [e.to_dict() for e in self.entries]
        }
    
    def get_brief_summary(self) -> Dict[str, Any]:
        """Get brief summary (last entry of each agent)."""
        agents_seen = set()
        brief = []
        
        # Go backwards to get most recent entry per agent
        for entry in reversed(self.entries):
            if entry.source_agent not in agents_seen:
                brief.insert(0, entry.to_dict())
                agents_seen.add(entry.source_agent)
        
        return {
            "session_id": self.session_id,
            "status": self.status,
            "progress": f"{self.completed_steps}/{self.total_steps}",
            "last_update": self.entries[-1].timestamp if self.entries else None,
            "summary": brief
        }
    
    def export_json(self) -> str:
        """Export log as JSON string."""
        return json.dumps(self.get_step_summary(), indent=2)


class HandoffLogManager:
    """Manages handoff logs for multiple sessions."""
    
    def __init__(self):
        self.logs: Dict[str, HandoffLog] = {}
    
    def create_log(self, session_id: str, repo_url: str) -> HandoffLog:
        """Create new handoff log."""
        log = HandoffLog(session_id, repo_url)
        self.logs[session_id] = log
        return log
    
    def get_log(self, session_id: str) -> Optional[HandoffLog]:
        """Get log for a session."""
        return self.logs.get(session_id)
    
    def log_handoff(self,
                    session_id: str,
                    source_agent: str,
                    target_agent: Optional[str],
                    status: str,
                    message: str,
                    **kwargs) -> None:
        """Log handoff for a session."""
        log = self.get_log(session_id)
        if log:
            log.log_handoff(
                source_agent=source_agent,
                target_agent=target_agent,
                status=status,
                message=message,
                **kwargs
            )
    
    def get_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a session's handoffs."""
        log = self.get_log(session_id)
        if log:
            return log.get_step_summary()
        return None
    
    def get_brief_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get brief summary of a session."""
        log = self.get_log(session_id)
        if log:
            return log.get_brief_summary()
        return None
    
    def list_all_logs(self) -> List[Dict[str, Any]]:
        """List all handoff logs."""
        return [log.get_brief_summary() for log in self.logs.values()]


# Global manager instance
handoff_log_manager = HandoffLogManager()
