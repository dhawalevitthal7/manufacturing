"""
OKR AI Agent for Manufacturing
Provides AI-assisted OKR creation, personalization, and validation
"""

from typing import Any, Dict, List, Optional
from server.services.azure_openai_service import get_azure_openai_service


class OKRAIAgent:
    """AI Agent for OKR operations"""

    def __init__(self):
        self.openai_service = get_azure_openai_service()
        self.conversation_history = {}

    def start_okr_creation_session(
        self,
        session_id: str,
        department_name: str,
        hierarchy_level: str,
        quarter: str = "Q2",
        year: int = 2026,
    ):
        """Initialize a new OKR creation conversation session"""
        self.conversation_history[session_id] = {
            "messages": [],
            "department": department_name,
            "level": hierarchy_level,
            "quarter": quarter,
            "year": year,
            "created_at": str(__import__("datetime").datetime.now()),
        }

    def suggest_okr(
        self,
        session_id: str,
        user_message: str,
        department_name: str,
        hierarchy_level: str,
        quarter: str = "Q2",
        year: int = 2026,
    ) -> Dict[str, Any]:
        """
        AI-assisted OKR creation through conversation
        
        Args:
            session_id: Unique session identifier
            user_message: User's natural language description
            department_name: Department/team name
            hierarchy_level: ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
            quarter: Target quarter
            year: Target year
            
        Returns:
            Response with AI suggestions and coaching
        """
        # Initialize session if not exists
        if session_id not in self.conversation_history:
            self.start_okr_creation_session(
                session_id, department_name, hierarchy_level, quarter, year
            )

        # Get conversation history
        history = self.conversation_history[session_id].get("messages", [])

        # Get AI suggestion
        response = self.openai_service.generate_okr_suggestion(
            department_name=department_name,
            hierarchy_level=hierarchy_level,
            message=user_message,
            conversation_history=history,
            quarter=quarter,
            year=year,
        )

        # Store in history
        self.conversation_history[session_id]["messages"].append(
            {"role": "user", "content": user_message}
        )
        if "reply" in response:
            self.conversation_history[session_id]["messages"].append(
                {"role": "assistant", "content": response.get("reply", "")}
            )

        return response

    def personalize_cascaded_okr(
        self,
        session_id: str,
        user_message: str,
        department_name: str,
        parent_objective: str,
        parent_key_results: List[Dict[str, Any]],
        quarter: str = "Q2",
        year: int = 2026,
    ) -> Dict[str, Any]:
        """
        Personalize a cascaded OKR from parent goal
        
        Args:
            session_id: Unique session identifier
            user_message: Employee's personalization request
            department_name: Department/team name
            parent_objective: Parent OKR objective
            parent_key_results: Parent OKR's key results
            quarter: Target quarter
            year: Target year
            
        Returns:
            Response with personalized OKR suggestion
        """
        # Initialize session if not exists
        if session_id not in self.conversation_history:
            self.start_okr_creation_session(
                session_id, department_name, "INDIVIDUAL", quarter, year
            )

        history = self.conversation_history[session_id].get("messages", [])

        response = self.openai_service.cascade_okr_suggestion(
            department_name=department_name,
            parent_objective=parent_objective,
            parent_key_results=parent_key_results,
            message=user_message,
            conversation_history=history,
            quarter=quarter,
            year=year,
        )

        # Store in history
        self.conversation_history[session_id]["messages"].append(
            {"role": "user", "content": user_message}
        )
        if "reply" in response:
            self.conversation_history[session_id]["messages"].append(
                {"role": "assistant", "content": response.get("reply", "")}
            )

        return response

    def validate_alignment(
        self,
        org_objective: str,
        org_key_results: List[Dict[str, Any]],
        department_objective: str,
        department_key_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validate alignment between department and organization OKRs
        
        Returns:
            Alignment report with gaps and recommendations
        """
        return self.openai_service.validate_okr_alignment(
            org_objective=org_objective,
            org_key_results=org_key_results,
            department_objective=department_objective,
            department_key_results=department_key_results,
        )

    def clear_session(self, session_id: str):
        """Clear conversation session"""
        if session_id in self.conversation_history:
            del self.conversation_history[session_id]

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of current session"""
        if session_id not in self.conversation_history:
            return {"error": "Session not found"}
        return self.conversation_history[session_id]


# Singleton instance
_okr_agent = None


def get_okr_ai_agent() -> OKRAIAgent:
    """Get or create OKR AI Agent instance"""
    global _okr_agent
    if _okr_agent is None:
        _okr_agent = OKRAIAgent()
    return _okr_agent
