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

from server.services.cascade_ai_levels import (
    LEVEL_CASCADE_GUIDANCE,
    LEVEL_KR_TEMPLATES,
    LEVEL_OBJECTIVE_TEMPLATES,
)
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
        parent_level: str,
        child_level: str,
        scope_name: str,
        scope_metadata: Optional[Dict[str, Any]] = None,
        previous_okrs: Optional[List[str]] = None,
        org_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call Azure OpenAI (with retries) or fall back to level-specific rule-based generation.
        Returns normalized suggestion DTO with NEW child-level content (not parent copy-paste).
        """
        user_prompt = build_cascade_user_prompt(
            parent_objective=parent_objective,
            parent_description=parent_description,
            parent_key_results=parent_key_results,
            parent_level=parent_level,
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
            parent_description=parent_description,
            parent_level=parent_level,
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
        parent_description: Optional[str],
        parent_level: str,
        child_level: str,
        scope_name: str,
        parent_key_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Level-specific deterministic fallback when Azure OpenAI is unavailable.
        Generates NEW operational KRs — does not prefix parent KR titles.
        """
        cl = (child_level or "").upper()
        parent_short = (parent_objective or "")[:80]

        obj_tpl = LEVEL_OBJECTIVE_TEMPLATES.get(
            cl, "Execute {child} plan for «{parent}» at {scope}"
        )
        child_title = obj_tpl.format(
            scope=scope_name,
            parent=parent_short,
            child=cl.title(),
        )

        kr_templates = LEVEL_KR_TEMPLATES.get(cl, LEVEL_KR_TEMPLATES["DEPARTMENT"])
        krs: List[Dict[str, Any]] = []
        for tpl in kr_templates[:4]:
            title = str(tpl["title"]).format(scope=scope_name)
            krs.append(
                {
                    "title": title,
                    "target": float(tpl["target"]),
                    "unit": str(tpl["unit"]),
                }
            )

        # Enrich description with parent KR decomposition hint
        parent_kr_summary = ", ".join(
            (kr.get("title") or "")[:40] for kr in parent_key_results[:3]
        )
        guidance = LEVEL_CASCADE_GUIDANCE.get(cl, "")
        description = (
            f"This {cl}-level OKR decomposes the {parent_level} objective «{parent_short}» "
            f"into operational targets owned by {scope_name}. "
            f"{guidance[:200]}..."
            if guidance
            else f"Operational cascade for {scope_name} supporting parent goal."
        )

        reasoning = (
            f"Rule-based {cl} cascade: parent KRs ({parent_kr_summary or 'n/a'}) were decomposed "
            f"into {cl.lower()}-specific operational metrics for {scope_name}. "
            f"Configure Azure OpenAI for richer AI-generated suggestions."
        )

        return {
            "objective": child_title,
            "description": description,
            "key_results": krs,
            "confidence": 0.62,
            "alignment_score": 78.0,
            "reasoning": reasoning,
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
