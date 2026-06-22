"""AI review agent — context gathering and rule-based synthesis."""

import pytest

from server.services.performance_review_agent_service import PerformanceReviewAgentService


def test_rule_based_review_from_context():
    context = {
        "employee": {"name": "Alex Operator"},
        "cycle": {"label": "Q2-2026"},
        "okr_snapshot": {
            "avg_progress": 79.5,
            "objective_count": 1,
            "objectives": [{"title": "Individual goals", "progress": 79.5}],
        },
        "self_review": {"achievements": "Hit weekly targets", "strengths": "Reliability"},
        "checkins": [{"employee_mood": "POSITIVE"}],
    }
    svc = PerformanceReviewAgentService.__new__(PerformanceReviewAgentService)
    result = svc._rule_based_review(context)

    assert result["executive_summary"]
    assert result["promotion_recommendation"] in ("READY", "NEEDS_DEVELOPMENT", "NOT_READY")
    assert result["recommended_rating"]
    assert len(result["strengths"]) >= 1
    assert result["source"] == "rule_based"
