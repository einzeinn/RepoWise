"""
Session manager untuk menyimpan state per session.
Includes chat history dan context untuk Q&A Mentor.
"""

from typing import Dict, List, Any
from datetime import datetime
import uuid

class SessionData:
    """Represents a single analysis session with Q&A capability."""
    
    def __init__(self, session_id: str, repo_url: str):
        self.session_id = session_id
        self.repo_url = repo_url
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
        # Analysis results
        self.repository = None
        self.total_files = 0
        self.architecture_docs: Dict[str, str] = {}
        self.onboarding_guide = ""
        self.code_review: Dict[str, Any] = {}
        self.quality_score: int = 0
        self.quality_score_label: str = ""
        self.suggested_tasks = ""
        self.handoff_log: List[Dict[str, Any]] = []
        
        # Q&A history (Task 5)
        self.chat_history: List[Dict[str, str]] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "repo_url": self.repo_url,
            "repository": self.repository,
            "total_files": self.total_files,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "architecture_docs": self.architecture_docs,
            "onboarding_guide": self.onboarding_guide,
            "code_review": self.code_review,
            "quality_score": self.quality_score,
            "quality_score_label": self.quality_score_label,
            "suggested_tasks": self.suggested_tasks,
            "handoff_log": self.handoff_log,
            "chat_history": self.chat_history
        }


class SessionManager:
    """Manages all active sessions."""
    
    def __init__(self):
        self.sessions: Dict[str, SessionData] = {}
    
    def create_session(self, repo_url: str) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = SessionData(session_id, repo_url)
        return session_id
    
    def get_session(self, session_id: str) -> SessionData:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def save_analysis_result(self, session_id: str, result: Dict[str, Any]) -> None:
        """Save analysis results to session."""
        session = self.get_session(session_id)
        if not session:
            return
        
        session.repository = result.get("repository")
        session.total_files = result.get("total_files", 0)
        session.architecture_docs = result.get("architecture_docs", {})
        session.onboarding_guide = result.get("onboarding_guide", "")
        session.code_review = result.get("code_review", {})
        session.quality_score = result.get("quality_score", 0)
        session.quality_score_label = result.get("quality_score_label", "")
        session.suggested_tasks = result.get("suggested_tasks", "")
        session.handoff_log = result.get("handoff_log", [])
        session.updated_at = datetime.now().isoformat()
    
    def add_chat_message(self, session_id: str, role: str, content: str) -> None:
        """Add message to chat history."""
        session = self.get_session(session_id)
        if not session:
            return
        
        session.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        session.updated_at = datetime.now().isoformat()
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "session_id": s.session_id,
                "repository": s.repository,
                "created_at": s.created_at,
                "updated_at": s.updated_at
            }
            for s in self.sessions.values()
        ]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


# Global session manager instance
session_manager = SessionManager()
