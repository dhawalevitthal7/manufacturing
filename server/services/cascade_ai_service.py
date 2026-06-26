"""
AI service for hierarchical OKR cascading.

Generates structured child OKR suggestions via Azure OpenAI.
Never persists to the database — returns DTOs only.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

from server.services.cascade_ai_prompt import (
    PROMPT_VERSION,
    build_cascade_system_prompt,
    build_cascade_user_prompt,
    validate_cascade_response,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class CascadeAIService:
    """Generate child OKR suggestions from a parent objective."""

    def generate_child_okr(
        self,
        *,
        parent_objective: str,
        parent_description: Optional[str],
        parent_key_results: List[Dict[str, Any]],
        child_level: str,
        scope_name: str,
        scope_metadata: Optional[Dict[str, Any]] = None,
        previous_okrs: Optional[List[str]] = None,
        org_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call Azure OpenAI (with retries) or fall back to rule-based generation.
        Returns normalized suggestion DTO.
        """
        user_prompt = build_cascade_user_prompt(
            parent_objective=parent_objective,
            parent_description=parent_description,
            parent_key_results=parent_key_results,
            child_level=child_level,
            scope_name=scope_name,
            scope_metadata=scope_metadata,
            previous_okrs=previous_okrs,
            org_name=org_name,
        )

        last_error: Optional[str] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = self._call_ai(user_prompt)
                validated = validate_cascade_response(result)
                validated["source"] = "azure_openai"
                validated["model"] = result.get("_model")
                validated["tokens"] = result.get("_tokens")
                validated["attempt"] = attempt
                return validated
            except ValueError as exc:
                last_error = str(exc)
                logger.warning("Cascade AI validation failed (attempt %s): %s", attempt, exc)
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Cascade AI call failed (attempt %s): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * attempt)

        logger.info("Cascade AI fallback for scope=%s: %s", scope_name, last_error)
        return self._rule_based_suggestion(
            parent_objective=parent_objective,
            child_level=child_level,
            scope_name=scope_name,
            parent_key_results=parent_key_results,
        )

    def _call_ai(self, user_prompt: str) -> Dict[str, Any]:
        from server.services.azure_openai_service import _ai_configured

        if not _ai_configured():
            raise RuntimeError("Azure OpenAI not configured")

        from server.services.azure_openai_service import AzureOpenAIService

        svc = AzureOpenAIService()
        system = build_cascade_system_prompt()
        raw = svc._complete_json(system, user_prompt)
        if raw.get("error"):
            raise ValueError(raw["error"])
        raw["_model"] = getattr(svc, "deployment", None)
        return raw

    def _rule_based_suggestion(
        self,
        *,
        parent_objective: str,
        child_level: str,
        scope_name: str,
        parent_key_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Deterministic fallback when AI is unavailable."""
        child_title = f"{scope_name}: Execute {child_level.lower()} plan for «{parent_objective[:80]}»"
        krs: List[Dict[str, Any]] = []
        for i, pkr in enumerate(parent_key_results[:4]):
            pt = pkr.get("title") or f"Parent KR {i + 1}"
            krs.append(
                {
                    "title": f"{scope_name} — {pt}",
                    "target": 15.0 + i * 5,
                    "unit": pkr.get("unit") or "%",
                }
            )
        if not krs:
            krs = [
                {"title": f"Improve {scope_name} operational KPI", "target": 10, "unit": "%"},
                {"title": f"Reduce {scope_name} cost per unit", "target": 5, "unit": "%"},
                {"title": f"Achieve {scope_name} safety target", "target": 0, "unit": "incidents"},
            ]

        return {
            "objective": child_title,
            "description": (
                f"{child_level.title()} cascade of parent objective for {scope_name}. "
                f"Aligns execution with upstream strategy."
            ),
            "key_results": krs,
            "confidence": 0.55,
            "alignment_score": 72.0,
            "reasoning": "Rule-based cascade generated because AI was unavailable.",
            "prompt_version": PROMPT_VERSION,
            "source": "rule_based",
            "model": None,
            "tokens": None,
            "attempt": 0,
        }


def suggestion_to_ai_metadata(suggestion: Dict[str, Any], *, parent_id: str) -> str:
    """Serialize AI metadata for Objective.ai_metadata."""
    return json.dumps(
        {
            "parent_objective_id": parent_id,
            "prompt_version": suggestion.get("prompt_version", PROMPT_VERSION),
            "source": suggestion.get("source"),
            "model": suggestion.get("model"),
            "tokens": suggestion.get("tokens"),
            "alignment_score": suggestion.get("alignment_score"),
            "reasoning": suggestion.get("reasoning"),
            "attempt": suggestion.get("attempt"),
        }
    )
