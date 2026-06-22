"""
AI Performance Review Agent

After employee self-review, the manager gathers OKR progress, check-ins,
self/manager inputs, and scoring — then generates an editable performance
narrative for employee + department head (promotion pipeline).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.models import User, ProgressSubmission, Objective, KeyResult
from server.performance_review_models import (
    ContinuousCheckin,
    EmployeePerformanceReview,
    PerformanceReviewCycle,
    ReviewSection,
    ReviewState,
    SectionType,
)
from server.services.employee_review_service import EmployeeReviewService, _state_str
from server.services.okr_review_integration import (
    build_okr_progress_snapshot,
    calculate_okr_achievement_score,
)
from server.services.review_scoring_service import ReviewScoringService
from server.services.manager_resolution import can_coach_employee
from server.services.okr_review_integration import attach_okr_context_to_review

logger = logging.getLogger(__name__)

AI_REVIEW_JSON_SCHEMA = """
Return JSON with keys:
- executive_summary (string, 2-3 sentences)
- okr_performance_analysis (string, paragraph referencing KR progress)
- self_review_synthesis (string)
- checkin_insights (string)
- strengths (array of strings, 3-5 items)
- development_areas (array of strings, 2-4 items)
- promotion_recommendation (READY | NEEDS_DEVELOPMENT | NOT_READY)
- promotion_rationale (string)
- recommended_rating (EXCEEDS_EXPECTATIONS | MEETS_EXPECTATIONS | BELOW_EXPECTATIONS | NEEDS_IMPROVEMENT)
- coaching_actions (array of strings, 2-3 items)
- risk_flags (array of strings, may be empty)
"""


class PerformanceReviewAgentService:
    def __init__(self, db: Session):
        self.db = db

    def gather_context(self, review_id: str) -> Dict[str, Any]:
        review = self._get_review(review_id)
        employee = self.db.query(User).filter(User.id == review.employee_id).first()
        manager = self.db.query(User).filter(User.id == review.manager_id).first()
        cycle = (
            self.db.query(PerformanceReviewCycle)
            .filter(PerformanceReviewCycle.id == review.review_cycle_id)
            .first()
        )
        dept_head = None
        if review.dept_head_reviewer_id:
            dept_head = self.db.query(User).filter(User.id == review.dept_head_reviewer_id).first()

        period_start = review.review_period_start or (cycle.start_date if cycle else None)
        period_end = review.review_period_end or (cycle.end_date if cycle else None)

        okr_snapshot = build_okr_progress_snapshot(self.db, review.employee_id, review.org_id)
        okr_score, okr_ids = calculate_okr_achievement_score(
            self.db, review.employee_id, review.org_id, review.okr_ids or None
        )

        self_section = self._section(review_id, SectionType.SELF)
        manager_section = self._section(review_id, SectionType.MANAGER)

        checkins = self._checkins_for_period(review.employee_id, period_start, period_end)

        scoring = ReviewScoringService(self.db)
        try:
            final_score, rating, components = scoring.calculate_final_score(review_id)
            score_summary = {
                "final_score": final_score,
                "rating": rating.value if hasattr(rating, "value") else rating,
                "components": components,
            }
        except Exception as exc:
            logger.warning("Score preview failed for review %s: %s", review_id, exc)
            score_summary = None

        quarter_label = cycle.name if cycle else "Current cycle"
        if cycle and cycle.start_date:
            quarter_label = f"{cycle.name} ({cycle.start_date.date()} – {cycle.end_date.date()})"

        return {
            "review_id": review_id,
            "cycle": {
                "name": cycle.name if cycle else None,
                "type": cycle.cycle_type.value if cycle and hasattr(cycle.cycle_type, "value") else None,
                "period_start": period_start.isoformat() if period_start else None,
                "period_end": period_end.isoformat() if period_end else None,
                "label": quarter_label,
            },
            "employee": {
                "id": review.employee_id,
                "name": employee.name if employee else "Employee",
                "role": employee.system_role if employee else None,
            },
            "manager": {"id": review.manager_id, "name": manager.name if manager else "Manager"},
            "dept_head": {
                "id": review.dept_head_reviewer_id,
                "name": dept_head.name if dept_head else None,
            },
            "requires_dept_moderation": review.requires_dept_moderation,
            "okr_snapshot": okr_snapshot,
            "okr_achievement_score": okr_score,
            "okr_ids": okr_ids,
            "self_review": self._section_dict(self_section),
            "manager_draft": self._section_dict(manager_section),
            "checkins": [self._checkin_dict(c) for c in checkins],
            "progress_submissions": self._progress_for_period(review.employee_id, period_start, period_end),
            "prior_reviews": self._prior_reviews(review.employee_id, review.org_id, review.id),
            "score_summary": score_summary,
            "current_state": _state_str(review.current_state),
        }

    def generate_ai_review(self, review_id: str, manager_id: str) -> Dict[str, Any]:
        review = self._get_review(review_id)
        self._authorize_agent_actor(review, manager_id)
        self._ensure_ready_for_agent(review, manager_id)

        attach_okr_context_to_review(self.db, review)
        context = self.gather_context(review_id)
        payload = self._call_ai(context)
        if payload.get("error"):
            payload = self._rule_based_review(context)

        review.ai_review_payload = payload
        review.ai_review_context_snapshot = context
        review.ai_review_status = "GENERATED"
        review.ai_review_generated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(review)

        EmployeeReviewService(self.db)._log_action(
            performance_review_id=review_id,
            action="AI_REVIEW_GENERATED",
            actor_user_id=manager_id,
            old_state=review.current_state,
            new_state=review.current_state,
        )
        return self._ai_review_response(review)

    def _authorize_agent_actor(self, review: EmployeePerformanceReview, actor_id: str) -> None:
        if not can_coach_employee(
            self.db, actor_id, review.employee_id, review.manager_id
        ):
            raise ValueError("Not authorized to run the review agent for this employee")

    def _ensure_ready_for_agent(
        self, review: EmployeePerformanceReview, actor_id: str
    ) -> None:
        state = _state_str(review.current_state)
        if state == ReviewState.DRAFT.value:
            review.current_state = ReviewState.SELF_SUBMITTED.value
            review.self_submitted_at = datetime.utcnow()
            if review.manager_id != actor_id:
                review.manager_id = actor_id
            self.db.flush()
            EmployeeReviewService(self.db)._log_action(
                performance_review_id=review.id,
                action="MANAGER_INITIATED_SELF_REVIEW_SKIP",
                actor_user_id=actor_id,
                old_state=ReviewState.DRAFT.value,
                new_state=ReviewState.SELF_SUBMITTED.value,
            )
        elif state != ReviewState.SELF_SUBMITTED.value:
            raise ValueError(
                f"Review agent requires DRAFT or SELF_SUBMITTED state, got {review.current_state}"
            )

    def update_manager_edits(self, review_id: str, manager_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        review = self._get_review(review_id)
        self._authorize_agent_actor(review, manager_id)
        if _state_str(review.current_state) not in (
            ReviewState.SELF_SUBMITTED.value,
            ReviewState.DRAFT.value,
        ):
            raise ValueError("Can only edit AI review before manager submission")

        base = dict(review.ai_review_payload or {})
        base.update({k: v for k, v in payload.items() if v is not None})
        review.ai_review_payload = base
        review.ai_review_status = "MANAGER_EDITED"
        self.db.commit()
        self.db.refresh(review)
        return self._ai_review_response(review)

    def submit_manager_review_with_agent(
        self,
        review_id: str,
        manager_id: str,
        behavioral_scores: Optional[Dict[str, int]] = None,
        manager_notes: Optional[str] = None,
        promotion_eligible: bool = False,
        attrition_risk: Optional[str] = None,
    ) -> EmployeePerformanceReview:
        review = self._get_review(review_id)
        self._authorize_agent_actor(review, manager_id)
        self._ensure_ready_for_agent(review, manager_id)
        if not review.ai_review_payload:
            raise ValueError("Generate the AI review before submitting to employee and dept head")

        payload = review.ai_review_payload
        narrative = self._build_employee_narrative(payload, manager_notes)
        promotion_rec = payload.get("promotion_recommendation", "NEEDS_DEVELOPMENT")

        review_svc = EmployeeReviewService(self.db)
        updated = review_svc.submit_manager_review(
            review_id=review_id,
            manager_id=manager_id,
            okr_outcomes_assessment=payload.get("okr_performance_analysis"),
            behavioral_scores=behavioral_scores or {},
            execution_quality_assessment=payload.get("self_review_synthesis"),
            manager_feedback=manager_notes or payload.get("executive_summary"),
            promotion_eligible=promotion_eligible or promotion_rec == "READY",
            promotion_recommended=promotion_rec == "READY",
            attrition_risk=attrition_risk,
        )

        updated.employee_performance_narrative = narrative
        updated.promotion_recommendation = promotion_rec
        updated.promotion_rationale = payload.get("promotion_rationale")
        updated.ai_review_status = "SUBMITTED"
        updated.shared_with_employee_at = datetime.utcnow()
        if updated.requires_dept_moderation and updated.dept_head_reviewer_id:
            updated.submitted_to_dept_head_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(updated)

        review_svc._log_action(
            performance_review_id=review_id,
            action="MANAGER_REVIEW_WITH_AI_SUBMITTED",
            actor_user_id=manager_id,
            old_state=ReviewState.SELF_SUBMITTED.value,
            new_state=updated.current_state,
            changes={
                "promotion_recommendation": promotion_rec,
                "shared_with_employee": True,
                "routed_to_dept_head": bool(updated.submitted_to_dept_head_at),
            },
        )
        return updated

    def get_ai_review(self, review_id: str) -> Dict[str, Any]:
        review = self._get_review(review_id)
        return self._ai_review_response(review)

    def _call_ai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from server.services.azure_openai_service import AzureOpenAIService, _ai_configured

            if not _ai_configured():
                return {"error": "AI not configured"}

            svc = AzureOpenAIService()
            prompt = (
                f"You are a manufacturing HR performance review agent. "
                f"Synthesize a fair, evidence-based quarterly review.\n"
                f"Cycle: {context['cycle']['label']}\n"
                f"Employee: {context['employee']['name']}\n"
                f"Data:\n{json.dumps(context, default=str)[:12000]}\n"
                f"{AI_REVIEW_JSON_SCHEMA}"
            )
            result = svc._complete_json(
                "You write structured performance reviews for manufacturing employees. "
                "Ground every claim in the provided OKR, check-in, and self-review data.",
                prompt,
            )
            if result.get("error"):
                return result
            return result
        except Exception as exc:
            logger.warning("AI review agent fallback: %s", exc)
            return {"error": str(exc)}

    def _rule_based_review(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic synthesis when Azure OpenAI is unavailable."""
        emp = context["employee"]["name"]
        okr = context["okr_snapshot"]
        avg = okr.get("avg_progress", 0)
        self_r = context.get("self_review") or {}
        checkins = context.get("checkins") or []
        progress = context.get("progress_submissions") or []

        strengths: List[str] = []
        dev: List[str] = []
        for obj in okr.get("objectives", []):
            if obj.get("progress", 0) >= 75:
                strengths.append(f"Strong progress on «{obj.get('title')}» ({obj.get('progress')}%)")
            elif obj.get("progress", 0) < 50:
                dev.append(f"Below-target progress on «{obj.get('title')}» ({obj.get('progress')}%)")

        if self_r.get("strengths"):
            strengths.append(f"Self-identified: {self_r['strengths'][:200]}")
        if checkins:
            moods = [c.get("employee_mood") for c in checkins if c.get("employee_mood")]
            strengths.append(f"Submitted {len(checkins)} weekly check-in(s) this cycle")

        if avg >= 80:
            rating = "EXCEEDS_EXPECTATIONS"
            promo = "READY"
        elif avg >= 65:
            rating = "MEETS_EXPECTATIONS"
            promo = "NEEDS_DEVELOPMENT"
        elif avg >= 50:
            rating = "BELOW_EXPECTATIONS"
            promo = "NEEDS_DEVELOPMENT"
        else:
            rating = "NEEDS_IMPROVEMENT"
            promo = "NOT_READY"

        return {
            "executive_summary": (
                f"{emp} achieved {avg}% blended OKR progress in {context['cycle']['label']}. "
                f"Self-review and check-in data support a {rating.replace('_', ' ').lower()} assessment."
            ),
            "okr_performance_analysis": (
                f"Reviewed {okr.get('objective_count', 0)} objective(s) with "
                f"{avg}% average KR-weighted progress."
            ),
            "self_review_synthesis": self_r.get("achievements") or "No self-review narrative provided.",
            "checkin_insights": (
                f"{len(checkins)} check-in(s) on file; "
                f"{len(progress)} progress submission(s) this cycle."
                if checkins or progress
                else "No check-ins or progress submissions this cycle."
            ),
            "strengths": strengths[:5] or ["Consistent participation in review process"],
            "development_areas": dev[:4] or ["Continue building measurable KR outcomes"],
            "promotion_recommendation": promo,
            "promotion_rationale": (
                f"Based on {avg}% OKR achievement and review-cycle evidence."
            ),
            "recommended_rating": rating,
            "coaching_actions": [
                "Align next-quarter KRs with department priorities",
                "Maintain weekly check-in cadence with manager",
            ],
            "risk_flags": dev[:2],
            "source": "rule_based",
        }

    def _build_employee_narrative(self, payload: Dict[str, Any], manager_notes: Optional[str]) -> str:
        sections = [
            ("Executive Summary", payload.get("executive_summary")),
            ("OKR Performance", payload.get("okr_performance_analysis")),
            ("Your Self-Review", payload.get("self_review_synthesis")),
            ("Check-In Insights", payload.get("checkin_insights")),
            ("Strengths", "\n".join(f"• {s}" for s in payload.get("strengths") or [])),
            ("Development Areas", "\n".join(f"• {d}" for d in payload.get("development_areas") or [])),
            ("Coaching Actions", "\n".join(f"• {a}" for a in payload.get("coaching_actions") or [])),
            ("Promotion Consideration", payload.get("promotion_rationale")),
        ]
        if manager_notes:
            sections.append(("Manager Notes", manager_notes))

        parts = [f"## {title}\n\n{body}" for title, body in sections if body]
        return "\n\n".join(parts)

    def _ai_review_response(self, review: EmployeePerformanceReview) -> Dict[str, Any]:
        return {
            "review_id": review.id,
            "ai_review_status": review.ai_review_status or "NONE",
            "ai_review_generated_at": (
                review.ai_review_generated_at.isoformat() if review.ai_review_generated_at else None
            ),
            "payload": review.ai_review_payload,
            "employee_performance_narrative": review.employee_performance_narrative,
            "promotion_recommendation": review.promotion_recommendation,
            "promotion_rationale": review.promotion_rationale,
            "shared_with_employee_at": (
                review.shared_with_employee_at.isoformat() if review.shared_with_employee_at else None
            ),
            "submitted_to_dept_head_at": (
                review.submitted_to_dept_head_at.isoformat() if review.submitted_to_dept_head_at else None
            ),
        }

    def _get_review(self, review_id: str) -> EmployeePerformanceReview:
        review = (
            self.db.query(EmployeePerformanceReview)
            .filter(EmployeePerformanceReview.id == review_id)
            .first()
        )
        if not review:
            raise ValueError(f"Review not found: {review_id}")
        return review

    def _section(self, review_id: str, section_type: SectionType) -> Optional[ReviewSection]:
        return (
            self.db.query(ReviewSection)
            .filter(
                ReviewSection.performance_review_id == review_id,
                ReviewSection.section_type == section_type,
            )
            .first()
        )

    def _section_dict(self, section: Optional[ReviewSection]) -> Optional[Dict[str, Any]]:
        if not section:
            return None
        return {
            "achievements": section.self_achievements,
            "okr_self_assessment": section.self_okr_assessment,
            "strengths": section.self_strengths,
            "challenges": section.self_challenges,
            "growth_areas": section.self_growth_areas,
            "evidence": section.self_evidence,
            "manager_okr_outcomes": section.manager_okr_outcomes,
            "manager_feedback": section.manager_feedback,
            "behavioral_scores": section.manager_behavioral_scores,
            "submitted_at": section.submitted_at.isoformat() if section.submitted_at else None,
        }

    def _checkins_for_period(
        self, employee_id: str, start: Optional[datetime], end: Optional[datetime]
    ) -> List[ContinuousCheckin]:
        q = self.db.query(ContinuousCheckin).filter(ContinuousCheckin.employee_id == employee_id)
        if start:
            q = q.filter(ContinuousCheckin.checkin_date >= start)
        if end:
            q = q.filter(ContinuousCheckin.checkin_date <= end)
        return q.order_by(ContinuousCheckin.checkin_date.desc()).limit(12).all()

    def _checkin_dict(self, c: ContinuousCheckin) -> Dict[str, Any]:
        mood = c.employee_mood.value if hasattr(c.employee_mood, "value") else c.employee_mood
        return {
            "week": c.checkin_week,
            "achievements": (c.achievements or "")[:300],
            "blockers": (c.blockers or "")[:200],
            "confidence_score": c.confidence_score,
            "engagement_score": c.engagement_score,
            "employee_mood": mood,
            "workflow_status": c.workflow_status or c.status,
            "manager_feedback": c.manager_feedback,
            "coaching_notes": c.coaching_notes,
            "action_items": c.action_items or [],
        }

    def _progress_for_period(
        self,
        employee_id: str,
        start: Optional[datetime],
        end: Optional[datetime],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        q = self.db.query(ProgressSubmission).filter(
            ProgressSubmission.submitted_by_id == employee_id
        )
        if start:
            q = q.filter(ProgressSubmission.created_at >= start)
        if end:
            q = q.filter(ProgressSubmission.created_at <= end)
        rows = q.order_by(ProgressSubmission.created_at.desc()).limit(limit).all()
        result: List[Dict[str, Any]] = []
        for ps in rows:
            kr_title = None
            obj_title = None
            if ps.key_result_id:
                kr = self.db.query(KeyResult).filter(KeyResult.id == ps.key_result_id).first()
                kr_title = kr.title if kr else None
                if kr:
                    obj = self.db.query(Objective).filter(Objective.id == kr.objective_id).first()
                    obj_title = obj.title if obj else None
            elif ps.objective_id:
                obj = self.db.query(Objective).filter(Objective.id == ps.objective_id).first()
                obj_title = obj.title if obj else None
            result.append(
                {
                    "status": ps.status,
                    "employee_value": ps.employee_value,
                    "employee_note": (ps.employee_note or "")[:200],
                    "manager_value": ps.manager_value,
                    "manager_note": (ps.manager_note or "")[:200],
                    "validation_level": ps.validation_level,
                    "key_result": kr_title,
                    "objective": obj_title,
                    "submitted_at": ps.created_at.isoformat() if ps.created_at else None,
                }
            )
        return result

    def _prior_reviews(
        self,
        employee_id: str,
        org_id: str,
        exclude_review_id: str,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        prior = (
            self.db.query(EmployeePerformanceReview)
            .filter(
                EmployeePerformanceReview.employee_id == employee_id,
                EmployeePerformanceReview.org_id == org_id,
                EmployeePerformanceReview.id != exclude_review_id,
            )
            .order_by(EmployeePerformanceReview.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "cycle_id": p.review_cycle_id,
                "state": _state_str(p.current_state),
                "final_score": p.final_score,
                "final_rating": (
                    p.final_rating.value if hasattr(p.final_rating, "value") else p.final_rating
                ),
                "promotion_recommendation": getattr(p, "promotion_recommendation", None),
            }
            for p in prior
        ]
