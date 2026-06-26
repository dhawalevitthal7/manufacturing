"""Prompt builder for AI-assisted hierarchical OKR cascading."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


PROMPT_VERSION = "cascade_v1"


def build_cascade_system_prompt() -> str:
    return (
        "You are an expert manufacturing OKR strategist. "
        "Generate a child-level OKR that aligns with a parent objective. "
        "Return JSON only with this exact schema:\n"
        "{\n"
        '  "objective": "<clear measurable objective>",\n'
        '  "description": "<2-3 sentences explaining regional/plant responsibility>",\n'
        '  "alignment_score": <float 0-100>,\n'
        '  "confidence": <float 0-1>,\n'
        '  "reasoning": "<brief summary of why this OKR supports the parent>",\n'
        '  "key_results": [\n'
        '    {"title": "<KR>", "target": <number>, "unit": "%|units|days|MT|INR Cr"}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Provide 3-5 key results.\n"
        "- Targets must be numeric.\n"
        "- Reflect manufacturing context (cement, dispatch, kiln, safety, cost).\n"
        "- Avoid duplicating the parent objective verbatim.\n"
        "- Do not include markdown or prose outside JSON."
    )


def build_cascade_user_prompt(
    *,
    parent_objective: str,
    parent_description: Optional[str],
    parent_key_results: List[Dict[str, Any]],
    child_level: str,
    scope_name: str,
    scope_metadata: Optional[Dict[str, Any]] = None,
    previous_okrs: Optional[List[str]] = None,
    org_name: Optional[str] = None,
) -> str:
    kr_lines = "\n".join(
        f"  - {kr.get('title')} (target {kr.get('target_value', kr.get('target'))} {kr.get('unit', '')})"
        for kr in parent_key_results
    )
    prev = ""
    if previous_okrs:
        prev = "Previous OKRs at this level (avoid duplicates):\n" + "\n".join(
            f"  - {t}" for t in previous_okrs[:5]
        )

    meta = json.dumps(scope_metadata or {}, default=str)

    return (
        f"Organization: {org_name or 'Manufacturing'}\n"
        f"Parent level: ORGANIZATION\n"
        f"Child level: {child_level}\n"
        f"Scope: {scope_name}\n"
        f"Scope metadata: {meta}\n\n"
        f"Parent Objective: {parent_objective}\n"
        f"Parent Description: {parent_description or 'N/A'}\n"
        f"Parent Key Results:\n{kr_lines or '  (none)'}\n\n"
        f"{prev}\n\n"
        f"Generate one {child_level}-level OKR for '{scope_name}' that cascades from the parent."
    )


def validate_cascade_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize and validate AI JSON response; raises ValueError on invalid."""
    if not payload or payload.get("error"):
        raise ValueError(payload.get("error") or "Empty AI response")

    objective = (payload.get("objective") or "").strip()
    if not objective:
        raise ValueError("AI response missing objective")

    krs = payload.get("key_results") or []
    if not isinstance(krs, list) or len(krs) < 1:
        raise ValueError("AI response must include at least one key result")

    normalized_krs: List[Dict[str, Any]] = []
    for kr in krs:
        title = (kr.get("title") or "").strip()
        if not title:
            continue
        try:
            target = float(kr.get("target", kr.get("target_value", 100)))
        except (TypeError, ValueError):
            target = 100.0
        unit = (kr.get("unit") or "%").strip()
        normalized_krs.append({"title": title, "target": target, "unit": unit})

    if not normalized_krs:
        raise ValueError("No valid key results in AI response")

    confidence = payload.get("confidence")
    try:
        confidence_f = float(confidence) if confidence is not None else 0.75
    except (TypeError, ValueError):
        confidence_f = 0.75

    alignment = payload.get("alignment_score")
    try:
        alignment_f = float(alignment) if alignment is not None else None
    except (TypeError, ValueError):
        alignment_f = None

    return {
        "objective": objective,
        "description": (payload.get("description") or "").strip(),
        "key_results": normalized_krs[:5],
        "confidence": round(min(1.0, max(0.0, confidence_f)), 2),
        "alignment_score": alignment_f,
        "reasoning": (payload.get("reasoning") or "").strip(),
        "prompt_version": PROMPT_VERSION,
    }
