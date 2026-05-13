"""
Progress AI Agent for Manufacturing
Provides AI-assisted progress tracking, auto-updates, and coaching
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from server.services.azure_openai_service import get_azure_openai_service


class ProgressAIAgent:
    """AI Agent for Progress tracking and coaching"""

    def __init__(self):
        self.openai_service = get_azure_openai_service()

    def auto_track_progress(
        self,
        objective_title: str,
        key_result_title: str,
        current_value: float,
        target_value: float,
        unit: str,
        historical_progress: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate auto-progress suggestions based on historical data and trends
        
        Args:
            objective_title: Title of the objective
            key_result_title: Title of the key result
            current_value: Current progress value
            target_value: Target value to achieve
            unit: Unit of measurement (%, pts, $, units, etc.)
            historical_progress: List of historical progress points
            
        Returns:
            Auto-tracking data with predicted progress and coaching
        """
        response = self.openai_service.auto_track_progress(
            objective_title=objective_title,
            key_result_title=key_result_title,
            current_value=current_value,
            target_value=target_value,
            unit=unit,
            historical_progress=historical_progress,
        )
        
        return response

    def suggest_coaching(
        self,
        objective_title: str,
        progress_value: float,
        target_value: float,
        blockers: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate AI coaching suggestions for progress submission
        
        Args:
            objective_title: Title of the objective
            progress_value: Current progress value
            target_value: Target value
            blockers: Any blockers/challenges mentioned
            notes: Employee's notes on progress
            
        Returns:
            Coaching suggestions with actions and sentiment
        """
        response = self.openai_service.suggest_coaching(
            objective_title=objective_title,
            progress_value=progress_value,
            target_value=target_value,
            blockers=blockers,
            notes=notes,
        )
        
        return response

    def calculate_auto_progress(
        self,
        current_value: float,
        target_value: float,
    ) -> float:
        """
        Calculate auto-progress percentage
        
        Args:
            current_value: Current value
            target_value: Target value
            
        Returns:
            Progress percentage (0-100)
        """
        if target_value <= 0:
            return 0.0
        
        progress = min((current_value / target_value) * 100, 100.0)
        return round(progress, 2)

    def predict_completion(
        self,
        historical_progress: List[Dict[str, float]],
        target_value: float,
        days_remaining: int,
    ) -> Dict[str, Any]:
        """
        Predict if OKR will be completed based on trend
        
        Args:
            historical_progress: List of (date, value) tuples
            target_value: Target to achieve
            days_remaining: Days until end of quarter
            
        Returns:
            Prediction with likelihood and recommendation
        """
        if not historical_progress or len(historical_progress) < 2:
            return {
                "prediction": "INSUFFICIENT_DATA",
                "likelihood": None,
                "recommendation": "More data needed to predict completion",
            }

        # Simple trend analysis
        sorted_progress = sorted(historical_progress, key=lambda x: x.get("date", ""))
        
        if len(sorted_progress) >= 2:
            # Calculate velocity (change per period)
            first_value = sorted_progress[0].get("value", 0)
            last_value = sorted_progress[-1].get("value", 0)
            periods = len(sorted_progress) - 1
            
            if periods > 0:
                velocity = (last_value - first_value) / periods
                
                # Project to target
                if velocity > 0:
                    periods_to_target = (target_value - last_value) / velocity
                    likelihood = min((days_remaining / periods_to_target), 1.0) if periods_to_target > 0 else 0.0
                    
                    if likelihood >= 0.8:
                        prediction = "ON_TRACK"
                        recommendation = "Keep current pace to complete on time"
                    elif likelihood >= 0.5:
                        prediction = "AT_RISK"
                        recommendation = "May need acceleration to complete on time"
                    else:
                        prediction = "OFF_TRACK"
                        recommendation = "Significant effort needed to reach target"
                    
                    return {
                        "prediction": prediction,
                        "likelihood": round(likelihood, 2),
                        "recommendation": recommendation,
                        "velocity": velocity,
                        "projected_completion_value": round(last_value + (velocity * days_remaining), 2),
                    }

        return {
            "prediction": "INSUFFICIENT_DATA",
            "likelihood": None,
            "recommendation": "Unable to calculate trend",
        }

    def batch_auto_track(
        self,
        key_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Auto-track multiple key results in batch
        
        Args:
            key_results: List of key result dicts with title, current_value, target_value, unit
            
        Returns:
            List of auto-tracked updates
        """
        updates = []
        
        for kr in key_results:
            try:
                auto_data = self.auto_track_progress(
                    objective_title=kr.get("objective_title", ""),
                    key_result_title=kr.get("title", ""),
                    current_value=kr.get("current_value", 0),
                    target_value=kr.get("target_value", 100),
                    unit=kr.get("unit", "%"),
                    historical_progress=kr.get("historical_progress", None),
                )
                
                auto_data["kr_id"] = kr.get("id")
                auto_data["progress_percentage"] = self.calculate_auto_progress(
                    kr.get("current_value", 0),
                    kr.get("target_value", 100),
                )
                auto_data["timestamp"] = datetime.utcnow().isoformat()
                
                updates.append(auto_data)
            except Exception as e:
                print(f"Error auto-tracking KR {kr.get('id')}: {e}")
                updates.append({
                    "kr_id": kr.get("id"),
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                })

        return updates


# Singleton instance
_progress_agent = None


def get_progress_ai_agent() -> ProgressAIAgent:
    """Get or create Progress AI Agent instance"""
    global _progress_agent
    if _progress_agent is None:
        _progress_agent = ProgressAIAgent()
    return _progress_agent
