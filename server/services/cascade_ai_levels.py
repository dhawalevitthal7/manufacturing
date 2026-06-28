"""Level-specific guidance for AI cascade prompt building."""

from __future__ import annotations

# What each child level should OWN when cascading from a parent OKR.
LEVEL_CASCADE_GUIDANCE: dict[str, str] = {
    "REGION": (
        "Regional OKRs translate corporate strategy into regional execution. "
        "Key results should cover: dispatch/logistics performance, regional market share, "
        "cross-plant coordination, regional safety & compliance, and cost per tonne shipped. "
        "Decompose parent KRs into metrics a Regional Head can directly influence across plants."
    ),
    "PLANT": (
        "Plant OKRs focus on single-facility manufacturing execution. "
        "Key results should cover: kiln/production throughput, energy & fuel efficiency, "
        "quality/reject rate, plant OEE, maintenance downtime, and environmental compliance. "
        "Break regional targets into plant-specific operational metrics."
    ),
    "DEPARTMENT": (
        "Department OKRs focus on functional execution within one plant. "
        "Key results should cover: department output vs plan, process yield, "
        "cost per unit, cross-shift consistency, and department safety incidents. "
        "Translate plant goals into department-owned deliverables (Production, Maintenance, Quality, etc.)."
    ),
    "TEAM": (
        "Team OKRs focus on shift/crew performance. "
        "Key results should cover: shift output targets, first-pass quality, "
        "equipment uptime during shift, checklist compliance, and near-miss reporting. "
        "Make metrics actionable within one team's daily/weekly operating rhythm."
    ),
    "INDIVIDUAL": (
        "Individual OKRs assign personal accountability within a team. "
        "Key results should cover: personal output vs target, skill/certification completion, "
        "quality adherence, attendance/punctuality, and improvement suggestions implemented. "
        "Each KR must be measurable for one employee — never team-level aggregates."
    ),
}

# Rule-based KR templates when Azure OpenAI is unavailable (still level-specific, not copy-paste).
LEVEL_KR_TEMPLATES: dict[str, list[dict[str, str | float]]] = {
    "REGION": [
        {"title": "Achieve {scope} dispatch OTIF (on-time in-full)", "target": 92, "unit": "%"},
        {"title": "Reduce {scope} logistics cost per tonne by", "target": 8, "unit": "%"},
        {"title": "Improve {scope} cross-plant production coordination index to", "target": 85, "unit": "%"},
        {"title": "Maintain {scope} zero LTI (lost-time injuries)", "target": 0, "unit": "incidents"},
        {"title": "Increase {scope} dealer satisfaction score to", "target": 88, "unit": "%"},
    ],
    "PLANT": [
        {"title": "Achieve {scope} clinker production vs annual plan", "target": 105, "unit": "%"},
        {"title": "Reduce {scope} specific thermal energy consumption to", "target": 720, "unit": "kcal/kg"},
        {"title": "Improve {scope} plant OEE (overall equipment effectiveness) to", "target": 78, "unit": "%"},
        {"title": "Reduce {scope} unplanned downtime to below", "target": 4, "unit": "%"},
        {"title": "Achieve {scope} quality reject rate below", "target": 2.5, "unit": "%"},
    ],
    "DEPARTMENT": [
        {"title": "Meet {scope} department production plan attainment", "target": 98, "unit": "%"},
        {"title": "Reduce {scope} process yield loss to below", "target": 3, "unit": "%"},
        {"title": "Achieve {scope} department cost per unit reduction of", "target": 6, "unit": "%"},
        {"title": "Complete {scope} preventive maintenance compliance at", "target": 95, "unit": "%"},
        {"title": "Zero {scope} department safety violations", "target": 0, "unit": "incidents"},
    ],
    "TEAM": [
        {"title": "Achieve {scope} shift output vs daily target", "target": 100, "unit": "%"},
        {"title": "Maintain {scope} first-pass quality rate above", "target": 97, "unit": "%"},
        {"title": "Reduce {scope} shift equipment stoppages to under", "target": 2, "unit": "hours/shift"},
        {"title": "Complete {scope} daily safety checklist compliance at", "target": 100, "unit": "%"},
        {"title": "Report and close {scope} near-miss observations per month", "target": 5, "unit": "count"},
    ],
    "INDIVIDUAL": [
        {"title": "Achieve personal production output target of", "target": 100, "unit": "%"},
        {"title": "Maintain quality adherence score above", "target": 98, "unit": "%"},
        {"title": "Complete assigned skill/certification modules", "target": 2, "unit": "modules"},
        {"title": "Achieve attendance & punctuality rate of", "target": 96, "unit": "%"},
        {"title": "Submit and implement improvement suggestions", "target": 1, "unit": "count"},
    ],
}

LEVEL_OBJECTIVE_TEMPLATES: dict[str, str] = {
    "REGION": "Drive {scope} regional operational excellence aligned with «{parent}»",
    "PLANT": "Optimize {scope} plant manufacturing performance for «{parent}»",
    "DEPARTMENT": "Deliver {scope} department execution excellence supporting «{parent}»",
    "TEAM": "Achieve {scope} shift-level performance targets for «{parent}»",
    "INDIVIDUAL": "Personal contribution to team goal: «{parent}» at {scope}",
}
