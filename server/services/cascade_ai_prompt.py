"""Prompt builder for AI-assisted hierarchical OKR cascading."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from server.services.cascade_ai_levels import LEVEL_CASCADE_GUIDANCE


PROMPT_VERSION = "cascade_v2"


def build_cascade_system_prompt() -> str:
    return (
        "You are an expert manufacturing OKR strategist specializing in hierarchical OKR cascading "
        "for cement/industrial companies.\n\n"
        "Your job: when a parent OKR becomes ACTIVE, invent a NEW child-level OKR with fresh "
        "objectives and key results appropriate for the next hierarchy level. "
        "Do NOT copy the parent objective verbatim or simply prefix parent key results.\n\n"
        "Return JSON only with this exact schema:\n"
        "{\n"
        '  "objective": "<new measurable objective for the child level>",\n'
        '  "description": "<2-4 sentences: how this child OKR decomposes the parent>",\n'
        '  "alignment_score": <float 0-100>,\n'
        '  "confidence": <float 0-1>,\n'
        '  "reasoning": "<how each KR supports the parent KRs>",\n'
        '  "key_results": [\n'
        '    {"title": "<NEW KR title — operational & level-specific>", "target": <number>, "unit": "%|MT|kcal/kg|hours|count|incidents"}\n'
        "  ]\n"
        "}\n\n"
        "Rules:\n"
        "- Provide 3-5 key results that are NEW — not renamed copies of parent KRs.\n"
        "- Each KR must be measurable at the child level (regional/plant/dept/team/individual).\n"
        "- Decompose parent KRs: if parent says 'increase efficiency 20%', child KRs might be "
        "kiln OEE, dispatch OTIF, energy kcal/kg, etc.\n"
        "- Use manufacturing context: cement, kiln, clinker, dispatch, logistics, safety TRIR/LTI.\n"
        "- Targets must be numeric and realistic for the scope.\n"
        "- Do not include markdown or prose outside JSON."
    )


def build_cascade_user_prompt(
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
) -> str:
    kr_lines = "\n".join(
        f"  - {kr.get('title')} (target {kr.get('target_value', kr.get('target'))} {kr.get('unit', '')})"
        for kr in parent_key_results
    )
    prev = ""
    if previous_okrs:
        prev = (
            "\nPrevious OKRs at this level (avoid duplicating titles):\n"
            + "\n".join(f"  - {t}" for t in previous_okrs[:5])
        )

    meta = json.dumps(scope_metadata or {}, default=str)
    level_guidance = LEVEL_CASCADE_GUIDANCE.get(
        child_level.upper(),
        "Generate operational key results appropriate for this hierarchy level.",
    )

    return (
        f"Organization: {org_name or 'Manufacturing'}\n"
        f"Parent level: {parent_level}\n"
        f"Child level: {child_level}\n"
        f"Scope unit: {scope_name}\n"
        f"Scope metadata: {meta}\n\n"
        f"=== PARENT OKR (already ACTIVE — do not copy verbatim) ===\n"
        f"Objective: {parent_objective}\n"
        f"Description: {parent_description or 'N/A'}\n"
        f"Parent Key Results:\n{kr_lines or '  (none)'}\n\n"
        f"=== CHILD LEVEL GUIDANCE ({child_level}) ===\n"
        f"{level_guidance}\n\n"
        f"=== YOUR TASK ===\n"
        f"Invent ONE new {child_level}-level OKR for '{scope_name}' that:\n"
        f"1. Aligns with the parent objective but uses fresh wording\n"
        f"2. Contains 3-5 NEW key results this {child_level} owner can directly control\n"
        f"3. Decomposes parent metrics into {child_level}-appropriate operational targets\n"
        f"{prev}"
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
