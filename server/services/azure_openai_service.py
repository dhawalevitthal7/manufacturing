"""
Azure OpenAI Service for Manufacturing OKR System
Handles AI-assisted OKR creation, validation, and progress tracking
"""

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://openai-04.openai.azure.com/"
)
# Set AZURE_OPENAI_API_KEY in the environment or a local .env file (never commit real keys).
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION",
    "2024-12-01-preview"
)
AZURE_OPENAI_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_DEPLOYMENT_NAME",
    "gpt-4o"
)


def _ai_configured() -> bool:
    return bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_API_KEY.strip())


def _friendly_ai_error(exc: Exception) -> str:
    msg = str(exc)
    if "401" in msg or "invalid subscription key" in msg.lower() or "access denied" in msg.lower():
        return (
            "Azure OpenAI is not configured correctly. Set AZURE_OPENAI_API_KEY, "
            "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_NAME in a .env file "
            "at the project root, then restart the server."
        )
    if not _ai_configured():
        return (
            "Azure OpenAI API key is missing. Add AZURE_OPENAI_API_KEY to your .env file "
            "and restart python main.py."
        )
    return "Sorry, I encountered an error. Please try again."


class AzureOpenAIService:
    """
    Wrapper around Azure OpenAI for Manufacturing OKR operations
    """

    def __init__(self):
        """Initialize Azure OpenAI client"""
        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'openai'. Install it with: pip install openai>=1.51.0"
            ) from exc

        if not _ai_configured():
            raise RuntimeError(
                "AZURE_OPENAI_API_KEY is not set. Create a .env file in the project root "
                "with your Azure OpenAI credentials (see AI_IMPLEMENTATION_SUMMARY.md)."
            )

        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )
        self.deployment = AZURE_OPENAI_DEPLOYMENT

    def _complete_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        Call Azure OpenAI with JSON response format
        Returns parsed JSON response
        """
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "{}").strip()
            return json.loads(content)
        except Exception as e:
            print(f"Azure OpenAI Error: {e}")
            return {"error": str(e)}

    def generate_okr_suggestion(
        self,
        department_name: str,
        hierarchy_level: str,
        message: str,
        conversation_history: List[Dict[str, str]] = None,
        quarter: str = "Q2",
        year: int = 2026,
    ) -> Dict[str, Any]:
        """
        Generate structured OKR data from natural language description
        Supports multi-turn conversation for refinement
        
        Args:
            department_name: Name of department/team
            hierarchy_level: ORGANIZATION, PLANT, DEPARTMENT, TEAM, INDIVIDUAL
            message: User's natural language OKR description
            conversation_history: Previous messages in conversation
            quarter: Target quarter (Q1-Q4)
            year: Target year
            
        Returns:
            JSON with keys: reply, has_suggestion, okr_suggestion
        """
        today = date.today().isoformat()
        
        # Get quarter end date
        quarter_end_dates = {
            "Q1": f"{year}-03-31",
            "Q2": f"{year}-06-30",
            "Q3": f"{year}-09-30",
            "Q4": f"{year}-12-31",
        }
        due_date = quarter_end_dates.get(quarter, f"{year}-06-30")

        system_prompt = (
            f"You are an expert OKR coach helping create {hierarchy_level}-level OKRs "
            f"for the '{department_name}' in {quarter}-{year}. Today's date is {today}.\n\n"
            "Your role:\n"
            "1. Engage in conversation to understand the manager's goals.\n"
            "2. Ask clarifying questions if objectives or targets are unclear.\n"
            "3. When ready, generate a complete OKR with 2-4 measurable key results.\n\n"
            "ALWAYS respond with JSON:\n"
            "{\n"
            '  "reply": "<your conversational response>",\n'
            '  "has_suggestion": true | false,\n'
            '  "okr_suggestion": {\n'
            '    "objective": "<clear objective>",\n'
            '    "quarter": "' + quarter + '",\n'
            '    "year": ' + str(year) + ',\n'
            '    "due_date": "' + due_date + '",\n'
            '    "key_results": [\n'
            '      { "title": "<measurable KR>", "target": <number>, "unit": "<%|pts|$|units>", "due_date": "' + due_date + '", "metric_type": "<HIGHER_IS_BETTER|LOWER_IS_BETTER|TARGET_MATCH|BOOLEAN|RANGE|MILESTONE>" }\n'
            "    ]\n"
            "  } | null\n"
            "}\n\n"
            "Rules:\n"
            "- Set has_suggestion=false and okr_suggestion=null when asking questions.\n"
            "- Set has_suggestion=true only when all details are clear.\n"
            "- Key result targets must be numeric with valid units (%, pts, $, units, etc.).\n"
            "- Due date format: YYYY-MM-DD.\n"
            "- Choose metric_type appropriately (e.g. Cost -> LOWER_IS_BETTER, Revenue -> HIGHER_IS_BETTER, Audit -> BOOLEAN). Default to HIGHER_IS_BETTER.\n"
            "- Keep reply concise and encouraging."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "{}").strip()
            return json.loads(content)
        except Exception as e:
            print(f"OKR suggestion error: {e}")
            return {
                "error": str(e),
                "reply": _friendly_ai_error(e),
                "has_suggestion": False,
                "okr_suggestion": None,
            }

    def cascade_okr_suggestion(
        self,
        department_name: str,
        parent_objective: str,
        parent_key_results: List[Dict[str, Any]],
        message: str,
        conversation_history: List[Dict[str, str]] = None,
        quarter: str = "Q2",
        year: int = 2026,
    ) -> Dict[str, Any]:
        """
        Help employee personalize a cascaded OKR from parent goal
        
        Returns JSON with keys: reply, has_suggestion, okr_suggestion
        """
        today = date.today().isoformat()
        quarter_end_dates = {
            "Q1": f"{year}-03-31",
            "Q2": f"{year}-06-30",
            "Q3": f"{year}-09-30",
            "Q4": f"{year}-12-31",
        }
        due_date = quarter_end_dates.get(quarter, f"{year}-06-30")

        kr_lines = "\n".join(
            f"  - {kr.get('title')} (target: {kr.get('target')} {kr.get('unit')})"
            for kr in parent_key_results
        )

        system_prompt = (
            f"You are an expert OKR coach helping an employee in '{department_name}' "
            f"personalize a cascaded goal for {quarter}-{year}. Today's date is {today}.\n\n"
            f"Parent OKR:\n"
            f"  Objective: {parent_objective}\n"
            f"  Key Results:\n{kr_lines}\n\n"
            "Your role:\n"
            "1. Help employee customize the objective and KRs to their role.\n"
            "2. Ask clarifying questions if needed.\n"
            "3. Generate a personal OKR aligned with parent goal.\n\n"
            "ALWAYS respond with JSON:\n"
            "{\n"
            '  "reply": "<conversational response>",\n'
            '  "has_suggestion": true | false,\n'
            '  "okr_suggestion": {\n'
            '    "objective": "<personalized objective>",\n'
            '    "quarter": "' + quarter + '",\n'
            '    "year": ' + str(year) + ',\n'
            '    "due_date": "' + due_date + '",\n'
            '    "key_results": [\n'
            '      { "title": "<measurable KR>", "target": <number>, "unit": "<unit>", "due_date": "' + due_date + '", "metric_type": "<HIGHER_IS_BETTER|LOWER_IS_BETTER|TARGET_MATCH|BOOLEAN|RANGE|MILESTONE>" }\n'
            "    ]\n"
            "  } | null\n"
            "}\n\n"
            "Rules:\n"
            "- Make OKR specific to employee's role and contribution.\n"
            "- Choose metric_type appropriately (e.g. Cost -> LOWER_IS_BETTER, Revenue -> HIGHER_IS_BETTER, Audit -> BOOLEAN). Default to HIGHER_IS_BETTER.\n"
            "- Keep reply encouraging and supportive."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            content = (response.choices[0].message.content or "{}").strip()
            return json.loads(content)
        except Exception as e:
            print(f"Cascade OKR error: {e}")
            return {"error": str(e), "reply": "Sorry, I encountered an error. Please try again."}

    def validate_okr_alignment(
        self,
        org_objective: str,
        org_key_results: List[Dict[str, Any]],
        department_objective: str,
        department_key_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compare department OKR alignment with organization OKR
        
        Returns JSON with keys: aligned, gaps, recommendation
        """
        system_prompt = (
            "You are an OKR alignment reviewer. Compare a department OKR to an organization OKR. "
            "Return JSON with keys: aligned (boolean), gaps (array), recommendation (string)."
        )

        user_prompt = (
            "Organization OKR:\n"
            f"  Objective: {org_objective}\n"
            f"  Key results: {json.dumps(org_key_results)}\n\n"
            "Department OKR:\n"
            f"  Objective: {department_objective}\n"
            f"  Key results: {json.dumps(department_key_results)}\n"
        )

        return self._complete_json(system_prompt, user_prompt)

    def auto_track_progress(
        self,
        objective_title: str,
        key_result_title: str,
        current_value: float,
        target_value: float,
        unit: str,
        historical_progress: List[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Generate auto-progress suggestions based on historical data
        
        Returns JSON with keys: predicted_progress, coaching_notes, confidence
        """
        today = date.today().isoformat()

        history_context = ""
        if historical_progress:
            history_lines = "\n".join(
                f"  {item.get('date', 'N/A')}: {item.get('value', 0)} {unit}"
                for item in historical_progress[-5:]  # Last 5 updates
            )
            history_context = f"\nHistorical Progress:\n{history_lines}\n"

        system_prompt = (
            "You are an AI assistant for OKR progress tracking. "
            "Based on current progress and history, suggest auto-tracking data. "
            "Return JSON with: predicted_progress (float 0-100), coaching_notes (string), confidence (0-1)."
        )

        user_prompt = (
            f"Today: {today}\n"
            f"Objective: {objective_title}\n"
            f"Key Result: {key_result_title}\n"
            f"Target: {target_value} {unit}\n"
            f"Current Value: {current_value} {unit}\n"
            f"Current Progress: {(current_value / target_value * 100) if target_value > 0 else 0:.1f}%\n"
            f"{history_context}"
            "Based on this data, suggest:\n"
            "1. Predicted progress percentage\n"
            "2. Brief coaching note\n"
            "3. Confidence level (0-1)"
        )

        return self._complete_json(system_prompt, user_prompt)

    def suggest_coaching(
        self,
        objective_title: str,
        progress_value: float,
        target_value: float,
        blockers: str = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        """
        Generate AI coaching suggestions for progress submission
        
        Returns JSON with keys: coaching_note, suggested_actions, sentiment
        """
        system_prompt = (
            "You are a supportive OKR coach providing brief, actionable coaching. "
            "Return JSON with: coaching_note (string), suggested_actions (array), sentiment (POSITIVE|NEUTRAL|CONCERNED)."
        )

        blocker_text = f"\nBlockers: {blockers}" if blockers else ""
        notes_text = f"\nNotes: {notes}" if notes else ""

        user_prompt = (
            f"Objective: {objective_title}\n"
            f"Target: {target_value}\n"
            f"Current: {progress_value}\n"
            f"Progress: {(progress_value / target_value * 100) if target_value > 0 else 0:.1f}%\n"
            f"{blocker_text}{notes_text}\n\n"
            "Provide encouraging coaching to keep the employee engaged."
        )

        return self._complete_json(system_prompt, user_prompt)


# Singleton instance
_azure_service = None


def get_azure_openai_service() -> AzureOpenAIService:
    """Get or create Azure OpenAI service instance"""
    global _azure_service
    if _azure_service is None:
        _azure_service = AzureOpenAIService()
    return _azure_service
