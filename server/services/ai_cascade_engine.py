"""
Generic AI Cascade Engine for hierarchical OKR cascading.

When a parent OKR becomes ACTIVE, generates AI_DRAFT child OKRs for the next
hierarchy level. Children never auto-activate — they follow review + parent approval.

Supports every adjacent level defined in CASCADE_CHILD_LEVEL (Org→Region→Plant→…→Individual).
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from server.database import SessionLocal, commit_with_retry
from server.models import KeyResult, Objective, OrgNode, Organization, User
from server.roles import (
    SystemRole,
    is_ai_cascade_enabled,
    next_cascade_child_level,
    normalize_role,
)
from server.services.audit_service import record_audit_event
from server.services.cascade_ai_service import CascadeAIService, suggestion_to_ai_metadata
from server.services.cascade_notification_service import (
    notify_ai_draft_ready,
    notify_parent_decision,
    notify_regenerated,
    notify_submitted_for_parent,
)
from server.services.objective_version_service import record_objective_version
from server.services.okr_lifecycle_service import (
    OKR_STATUS_ACTIVE,
    OKR_STATUS_AI_DRAFT,
    OKR_STATUS_AI_REJECTED,
    OKR_STATUS_PENDING_PARENT,
    OKR_STATUS_UNDER_REVIEW,
)

logger = logging.getLogger(__name__)

AUDIT_AI_CASCADE_GENERATE = "AI_CASCADE_GENERATE"
AUDIT_AI_CASCADE_REVIEW = "AI_CASCADE_REVIEW"
AUDIT_AI_CASCADE_SUBMIT = "AI_CASCADE_SUBMIT_PARENT"
AUDIT_AI_CASCADE_APPROVE = "AI_CASCADE_PARENT_APPROVE"
AUDIT_AI_CASCADE_REJECT = "AI_CASCADE_PARENT_REJECT"
AUDIT_AI_CASCADE_REGENERATE = "AI_CASCADE_REGENERATE"

# Role expected to own child OKRs at each level (for owner resolution).
CHILD_LEVEL_OWNER_ROLE: Dict[str, SystemRole] = {
    "REGION": SystemRole.REGIONAL_HEAD,
    "PLANT": SystemRole.PLANT_HEAD,
    "DEPARTMENT": SystemRole.DEPT_HEAD,
    "TEAM": SystemRole.TEAM_LEAD,
    "INDIVIDUAL": SystemRole.EMPLOYEE,
}


@dataclass
class CascadeTarget:
    """One scope unit at the child hierarchy level."""

    scope_id: str
    scope_name: str
    owner_id: str
    scope_metadata: Dict[str, Any]
    region_id: Optional[str] = None
    plant_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None


def schedule_cascade_for_active_okr(parent_objective_id: str, org_id: str) -> None:
    """Run cascade generation in a background thread after caller commits."""

    def _delayed_start() -> None:
        time.sleep(1.5)  # allow parent ACTIVE status to commit before cascade reads DB
        _run_cascade_background(parent_objective_id, org_id)

    thread = threading.Thread(
        target=_delayed_start,
        daemon=True,
        name=f"ai-cascade-{parent_objective_id[:8]}",
    )
    thread.start()


def _run_cascade_background(parent_objective_id: str, org_id: str) -> None:
    import time
    from sqlalchemy.exc import OperationalError

    last_exc: Exception | None = None
    for attempt in range(1, 6):
        db = SessionLocal()
        try:
            engine = AICascadeEngine(db)
            engine.generate_cascade_for_parent(parent_objective_id, org_id)
            commit_with_retry(db)
            logger.info(
                "AI cascade completed for parent %s (attempt %s)",
                parent_objective_id,
                attempt,
            )
            return
        except OperationalError as exc:
            last_exc = exc
            db.rollback()
            if "locked" in str(exc).lower() and attempt < 5:
                logger.warning(
                    "AI cascade DB locked (attempt %s/5), retrying…", attempt
                )
                time.sleep(1.5 * attempt)
                continue
            logger.exception("AI cascade background failed for %s: %s", parent_objective_id, exc)
            return
        except Exception as exc:
            db.rollback()
            logger.exception("AI cascade background failed for %s: %s", parent_objective_id, exc)
            return
        finally:
            db.close()
    if last_exc:
        logger.error(
            "AI cascade gave up after retries for %s: %s", parent_objective_id, last_exc
        )


class AICascadeEngine:
    def __init__(self, db: Session):
        self.db = db
        self.ai = CascadeAIService()

    def generate_cascade_for_parent(
        self, parent_objective_id: str, org_id: str
    ) -> List[str]:
        """Generate AI_DRAFT child OKRs for each child-scope target. Returns created IDs."""
        parent = (
            self.db.query(Objective)
            .filter(Objective.id == parent_objective_id, Objective.org_id == org_id)
            .first()
        )
        if not parent:
            raise ValueError("Parent objective not found")
        if (parent.okr_status or "").upper() != OKR_STATUS_ACTIVE:
            raise ValueError("Parent must be ACTIVE before cascade")
        if not parent.allows_cascade:
            return []

        parent_level = (parent.level or "").upper()
        if not is_ai_cascade_enabled(parent_level):
            logger.info("AI cascade disabled for parent level %s", parent_level)
            return []

        child_level = next_cascade_child_level(parent_level)
        if not child_level:
            return []

        parent.cascade_generation_status = "GENERATING"
        from server.database import flush_with_retry

        flush_with_retry(self.db)

        org = self.db.query(Organization).filter(Organization.id == org_id).first()
        targets = self._resolve_child_targets(org_id, parent_level, child_level, parent)
        parent_krs = self._parent_krs(parent)
        created_ids: List[str] = []

        for target in targets:
            if self._draft_exists(parent.id, child_level, target):
                continue

            previous = self._previous_titles(org_id, child_level, target)
            suggestion = self.ai.generate_child_okr(
                parent_objective=parent.title,
                parent_description=parent.description,
                parent_key_results=parent_krs,
                parent_level=parent_level,
                child_level=child_level,
                scope_name=target.scope_name,
                scope_metadata=target.scope_metadata,
                previous_okrs=previous,
                org_name=org.name if org else None,
            )

            obj = self._persist_ai_draft(
                parent=parent,
                child_level=child_level,
                target=target,
                suggestion=suggestion,
            )
            created_ids.append(obj.id)

            owner = self.db.query(User).filter(User.id == target.owner_id).first()
            if owner:
                notify_ai_draft_ready(self.db, okr=obj, parent=parent, owner=owner)
            record_objective_version(
                self.db,
                okr=obj,
                change_type="AI_GENERATED",
                changed_by_id=parent.owner_id,
            )

            record_audit_event(
                org_id=org_id,
                actor_user_id=parent.owner_id,
                action=AUDIT_AI_CASCADE_GENERATE,
                entity_type="OBJECTIVE",
                entity_id=obj.id,
                details={
                    "parent_id": parent.id,
                    "child_level": child_level,
                    "scope": target.scope_name,
                    "source": suggestion.get("source"),
                    "model": suggestion.get("model"),
                    "confidence": suggestion.get("confidence"),
                },
                db=self.db,
            )

            # Commit per draft — avoids long write locks that block OKR creation.
            try:
                commit_with_retry(self.db)
                parent = (
                    self.db.query(Objective)
                    .filter(Objective.id == parent_objective_id)
                    .first()
                )
            except Exception:
                self.db.rollback()
                raise

        if parent:
            parent.cascade_generation_status = "GENERATED" if created_ids else "NONE"
            commit_with_retry(self.db)
        return created_ids

    def _resolve_child_targets(
        self,
        org_id: str,
        parent_level: str,
        child_level: str,
        parent: Objective,
    ) -> List[CascadeTarget]:
        pl = (parent_level or "").upper()
        cl = (child_level or "").upper()

        if cl == "INDIVIDUAL":
            return self._targets_for_individuals(org_id, parent.team_id)

        if cl == "REGION":
            return self._targets_for_regions(org_id)

        scope_node_id: Optional[str] = None
        if cl == "PLANT":
            scope_node_id = parent.region_id
        elif cl == "DEPARTMENT":
            scope_node_id = parent.plant_id
        elif cl == "TEAM":
            scope_node_id = parent.department_id

        if not scope_node_id:
            logger.warning(
                "Parent OKR %s (level=%s) missing scope id for %s cascade",
                parent.id,
                pl,
                cl,
            )
            return []

        return self._targets_for_child_org_nodes(
            org_id, cl, scope_node_id, parent, cl
        )

    def _targets_for_child_org_nodes(
        self,
        org_id: str,
        node_type: str,
        parent_node_id: str,
        parent: Objective,
        child_level: str,
    ) -> List[CascadeTarget]:
        nodes = (
            self.db.query(OrgNode)
            .filter(
                OrgNode.org_id == org_id,
                OrgNode.node_type == node_type,
                OrgNode.parent_id == parent_node_id,
                OrgNode.is_active == True,
            )
            .all()
        )
        owner_role = CHILD_LEVEL_OWNER_ROLE.get(child_level)
        if not owner_role:
            return []

        targets: List[CascadeTarget] = []
        for node in nodes:
            owner_id = self._resolve_owner_for_scope(
                org_id, owner_role, head_user_id=node.head_user_id
            )
            if not owner_id:
                continue
            scope_ids = self._scope_ids_for_node(node, child_level, parent)
            meta = dict(node.node_metadata or {})
            meta["node_type"] = node_type
            targets.append(
                CascadeTarget(
                    scope_id=node.id,
                    scope_name=node.name,
                    owner_id=owner_id,
                    scope_metadata=meta,
                    region_id=scope_ids.get("region_id"),
                    plant_id=scope_ids.get("plant_id"),
                    department_id=scope_ids.get("department_id"),
                    team_id=scope_ids.get("team_id"),
                )
            )
        return targets

    def _scope_ids_for_node(
        self, node: OrgNode, child_level: str, parent: Objective
    ) -> Dict[str, str]:
        if child_level == "REGION":
            return {"region_id": node.id}
        if child_level == "PLANT":
            return {"region_id": parent.region_id or "", "plant_id": node.id}
        if child_level == "DEPARTMENT":
            return {
                "region_id": parent.region_id or "",
                "plant_id": parent.plant_id or "",
                "department_id": node.id,
            }
        if child_level == "TEAM":
            return {
                "region_id": parent.region_id or "",
                "plant_id": parent.plant_id or "",
                "department_id": parent.department_id or "",
                "team_id": node.id,
            }
        return {}

    def _targets_for_regions(self, org_id: str) -> List[CascadeTarget]:
        regions = (
            self.db.query(OrgNode)
            .filter(
                OrgNode.org_id == org_id,
                OrgNode.node_type == "REGION",
                OrgNode.is_active == True,
            )
            .all()
        )
        targets: List[CascadeTarget] = []
        for rn in regions:
            owner_id = self._resolve_owner_for_scope(
                org_id, SystemRole.REGIONAL_HEAD, region_node_id=rn.id, head_user_id=rn.head_user_id
            )
            if not owner_id:
                continue
            meta = dict(rn.node_metadata or {})
            meta["node_type"] = "REGION"
            targets.append(
                CascadeTarget(
                    scope_id=rn.id,
                    scope_name=rn.name,
                    owner_id=owner_id,
                    scope_metadata=meta,
                    region_id=rn.id,
                )
            )
        return targets

    def _targets_for_individuals(
        self, org_id: str, team_id: Optional[str]
    ) -> List[CascadeTarget]:
        from server.models import TeamMember

        if not team_id:
            return []
        members = (
            self.db.query(TeamMember)
            .filter(TeamMember.team_id == team_id, TeamMember.is_active == True)
            .all()
        )
        targets: List[CascadeTarget] = []
        for m in members:
            user = self.db.query(User).filter(User.id == m.user_id).first()
            if not user or not user.is_active:
                continue
            targets.append(
                CascadeTarget(
                    scope_id=user.id,
                    scope_name=user.name,
                    owner_id=user.id,
                    scope_metadata={"node_type": "INDIVIDUAL", "team_id": team_id},
                    team_id=team_id,
                )
            )
        return targets

    def _resolve_owner_for_scope(
        self,
        org_id: str,
        role: SystemRole,
        *,
        region_node_id: Optional[str] = None,
        head_user_id: Optional[str] = None,
    ) -> Optional[str]:
        if head_user_id:
            u = self.db.query(User).filter(User.id == head_user_id, User.is_active == True).first()
            if u:
                return u.id

        q = self.db.query(User).filter(
            User.org_id == org_id,
            User.is_active == True,
            User.system_role == role.value,
        )
        if region_node_id:
            q = q.filter(User.org_node_id == region_node_id)
        user = q.first()
        if user:
            return user.id

        # Fallback: any user with the role
        fallback = (
            self.db.query(User)
            .filter(User.org_id == org_id, User.is_active == True)
            .all()
        )
        for u in fallback:
            if normalize_role(u.system_role) == role:
                return u.id
        return None

    def _draft_exists(
        self, parent_id: str, child_level: str, target: CascadeTarget
    ) -> bool:
        q = self.db.query(Objective).filter(
            Objective.ai_generated_from_objective_id == parent_id,
            Objective.level == child_level,
            Objective.okr_status.in_(
                [OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW, OKR_STATUS_PENDING_PARENT, OKR_STATUS_ACTIVE]
            ),
        )
        if target.region_id:
            q = q.filter(Objective.region_id == target.region_id)
        elif target.plant_id:
            q = q.filter(Objective.plant_id == target.plant_id)
        elif target.department_id:
            q = q.filter(Objective.department_id == target.department_id)
        elif target.team_id and child_level == "TEAM":
            q = q.filter(Objective.team_id == target.team_id)
        elif child_level == "INDIVIDUAL":
            q = q.filter(Objective.owner_id == target.owner_id)
        return q.first() is not None

    def _apply_token_usage(self, obj: Objective, suggestion: Dict[str, Any]) -> None:
        tokens = suggestion.get("tokens")
        if isinstance(tokens, dict):
            obj.ai_prompt_tokens = tokens.get("prompt_tokens") or tokens.get("prompt")
            obj.ai_completion_tokens = tokens.get("completion_tokens") or tokens.get("completion")
            obj.ai_total_tokens = tokens.get("total_tokens") or tokens.get("total")
        elif isinstance(tokens, int):
            obj.ai_total_tokens = tokens

    def _persist_ai_draft(
        self,
        *,
        parent: Objective,
        child_level: str,
        target: CascadeTarget,
        suggestion: Dict[str, Any],
    ) -> Objective:
        obj = Objective(
            id=str(uuid.uuid4()),
            org_id=parent.org_id,
            owner_id=target.owner_id,
            assigned_by_id=None,
            parent_id=parent.id,
            cycle_id=parent.cycle_id,
            title=suggestion["objective"],
            description=suggestion.get("description"),
            level=child_level,
            status="ACTIVE",
            progress=0.0,
            region_id=target.region_id or parent.region_id,
            plant_id=target.plant_id or parent.plant_id,
            department_id=target.department_id or parent.department_id,
            team_id=target.team_id or parent.team_id,
            quarter=parent.quarter,
            year=parent.year,
            ai_generated=True,
            ai_metadata=suggestion_to_ai_metadata(suggestion, parent_id=parent.id),
            cascade_generation_status="GENERATED",
            ai_generated_from_objective_id=parent.id,
            ai_generation_version=1,
            ai_confidence=suggestion.get("confidence"),
            ai_generation_reason=suggestion.get("reasoning"),
            review_status=OKR_STATUS_AI_DRAFT,
            okr_status=OKR_STATUS_AI_DRAFT,
            creation_approval_status="PENDING",
            allows_cascade=True,
            kr_baseline_locked=False,
        )
        self._apply_token_usage(obj, suggestion)
        self.db.add(obj)
        self.db.flush()

        for kr_data in suggestion.get("key_results") or []:
            kr = KeyResult(
                id=str(uuid.uuid4()),
                objective_id=obj.id,
                title=kr_data["title"],
                target_value=float(kr_data.get("target", 100)),
                current_value=0.0,
                unit=kr_data.get("unit") or "%",
                weight=1.0,
                status="NOT_STARTED",
            )
            self.db.add(kr)

        self.db.flush()
        return obj

    def _parent_krs(self, parent: Objective) -> List[Dict[str, Any]]:
        krs = self.db.query(KeyResult).filter(KeyResult.objective_id == parent.id).all()
        return [
            {"title": kr.title, "target_value": kr.target_value, "unit": kr.unit}
            for kr in krs
        ]

    def _previous_titles(
        self, org_id: str, child_level: str, target: CascadeTarget
    ) -> List[str]:
        q = self.db.query(Objective.title).filter(
            Objective.org_id == org_id,
            Objective.level == child_level,
        )
        if target.region_id:
            q = q.filter(Objective.region_id == target.region_id)
        rows = q.limit(10).all()
        return [r[0] for r in rows if r[0]]

    # ── Review workflow ─────────────────────────────────────────────────────

    def start_review(self, okr: Objective, actor: User) -> Objective:
        self._assert_child_owner_or_admin(okr, actor)
        if okr.okr_status != OKR_STATUS_AI_DRAFT:
            raise ValueError(f"Cannot review OKR in status {okr.okr_status}")
        okr.okr_status = OKR_STATUS_UNDER_REVIEW
        okr.review_status = OKR_STATUS_UNDER_REVIEW
        okr.reviewed_by_id = actor.id
        okr.reviewed_at = datetime.utcnow()
        self.db.flush()
        return okr

    def update_ai_draft(
        self,
        okr: Objective,
        actor: User,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        key_results: Optional[List[Dict[str, Any]]] = None,
    ) -> Objective:
        self._assert_child_owner_or_admin(okr, actor)
        if okr.okr_status not in (OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW):
            raise ValueError("Can only edit AI draft or under-review OKRs")

        if title:
            okr.title = title.strip()
        if description is not None:
            okr.description = description

        if key_results is not None:
            assert_okr_allows_kr_edit_for_ai(okr)
            existing = (
                self.db.query(KeyResult).filter(KeyResult.objective_id == okr.id).all()
            )
            for kr in existing:
                self.db.delete(kr)
            for kr_data in key_results:
                self.db.add(
                    KeyResult(
                        id=str(uuid.uuid4()),
                        objective_id=okr.id,
                        title=kr_data["title"],
                        target_value=float(kr_data.get("target_value", kr_data.get("target", 100))),
                        current_value=float(kr_data.get("current_value", 0)),
                        unit=kr_data.get("unit") or "%",
                        weight=float(kr_data.get("weight", 1.0)),
                        status="NOT_STARTED",
                    )
                )

        okr.ai_generation_version = (okr.ai_generation_version or 1) + 1
        if okr.okr_status == OKR_STATUS_AI_DRAFT:
            okr.okr_status = OKR_STATUS_UNDER_REVIEW
            okr.review_status = OKR_STATUS_UNDER_REVIEW
        okr.rejection_reason = None
        okr.reviewed_by_id = actor.id
        okr.reviewed_at = datetime.utcnow()
        record_objective_version(self.db, okr=okr, change_type="EDIT", changed_by_id=actor.id)
        self.db.flush()
        return okr

    def submit_for_parent_approval(self, okr: Objective, actor: User) -> Objective:
        self._assert_child_owner_or_admin(okr, actor)
        if okr.okr_status not in (OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW):
            raise ValueError("OKR must be AI draft or under review to submit")

        parent = self._parent_objective(okr)
        if not parent:
            raise ValueError("Parent objective not found")

        okr.okr_status = OKR_STATUS_PENDING_PARENT
        okr.review_status = OKR_STATUS_PENDING_PARENT
        okr.submitted_for_parent_approval_at = datetime.utcnow()
        okr.rejection_reason = None
        okr.pending_approver_user_id = parent.owner_id
        okr.pending_approver_role = None
        self.db.flush()

        notify_submitted_for_parent(self.db, okr=okr, parent=parent, actor=actor)
        record_objective_version(
            self.db, okr=okr, change_type="SUBMIT", changed_by_id=actor.id
        )
        record_audit_event(
            org_id=okr.org_id,
            actor_user_id=actor.id,
            action=AUDIT_AI_CASCADE_SUBMIT,
            entity_type="OBJECTIVE",
            entity_id=okr.id,
            details={"parent_id": parent.id},
            db=self.db,
        )
        return okr

    def approve_by_parent(
        self, okr: Objective, actor: User, *, schedule_next_cascade: bool = True
    ) -> Objective:
        parent = self._parent_objective(okr)
        if not parent:
            raise ValueError("Parent not found")
        if okr.okr_status != OKR_STATUS_PENDING_PARENT:
            raise ValueError("OKR is not pending parent approval")
        if actor.id != parent.owner_id and normalize_role(actor.system_role) not in (
            SystemRole.CEO,
            SystemRole.SUPER_ADMIN,
        ):
            raise ValueError("Only the parent OKR owner may approve")

        # Activate without re-triggering cascade for child (child level may not be enabled).
        okr.okr_status = OKR_STATUS_ACTIVE
        okr.status = "ACTIVE"
        okr.review_status = OKR_STATUS_ACTIVE
        okr.approved_by_parent_id = actor.id
        okr.approved_at = datetime.utcnow()
        okr.pending_approver_user_id = None
        okr.kr_baseline_locked = True
        okr.creation_approval_status = "APPROVED"
        self.db.flush()

        notify_parent_decision(self.db, okr=okr, actor=actor, approved=True)
        record_objective_version(
            self.db, okr=okr, change_type="APPROVE", changed_by_id=actor.id
        )
        record_audit_event(
            org_id=okr.org_id,
            actor_user_id=actor.id,
            action=AUDIT_AI_CASCADE_APPROVE,
            entity_type="OBJECTIVE",
            entity_id=okr.id,
            details={"parent_id": parent.id},
            db=self.db,
        )

        # Cascade to next level after commit (delayed thread avoids read-before-commit race).
        if schedule_next_cascade:
            try:
                schedule_cascade_for_active_okr(okr.id, okr.org_id)
            except Exception:
                pass

        return okr

    def reject_by_parent(
        self, okr: Objective, actor: User, reason: str
    ) -> Objective:
        parent = self._parent_objective(okr)
        if not parent:
            raise ValueError("Parent not found")
        if okr.okr_status != OKR_STATUS_PENDING_PARENT:
            raise ValueError("OKR is not pending parent approval")
        if actor.id != parent.owner_id and normalize_role(actor.system_role) not in (
            SystemRole.CEO,
            SystemRole.SUPER_ADMIN,
        ):
            raise ValueError("Only the parent OKR owner may reject")

        okr.okr_status = OKR_STATUS_UNDER_REVIEW
        okr.review_status = OKR_STATUS_UNDER_REVIEW
        okr.rejection_reason = reason.strip()
        okr.pending_approver_user_id = None
        okr.submitted_for_parent_approval_at = None
        self.db.flush()

        notify_parent_decision(
            self.db, okr=okr, actor=actor, approved=False, reason=reason
        )
        record_objective_version(
            self.db, okr=okr, change_type="PARENT_RETURNED", changed_by_id=actor.id
        )
        record_audit_event(
            org_id=okr.org_id,
            actor_user_id=actor.id,
            action=AUDIT_AI_CASCADE_REJECT,
            entity_type="OBJECTIVE",
            entity_id=okr.id,
            details={"parent_id": parent.id, "reason": reason},
            db=self.db,
        )
        return okr

    def reject_ai_draft(self, okr: Objective, actor: User, reason: str) -> Objective:
        self._assert_child_owner_or_admin(okr, actor)
        if okr.okr_status not in (OKR_STATUS_AI_DRAFT, OKR_STATUS_UNDER_REVIEW):
            raise ValueError("Can only reject AI drafts under review")
        okr.okr_status = OKR_STATUS_AI_REJECTED
        okr.review_status = OKR_STATUS_AI_REJECTED
        okr.rejection_reason = reason.strip()
        self.db.flush()
        return okr

    def regenerate(self, okr: Objective, actor: User) -> Objective:
        """Regenerate an AI draft in place (same scope, new suggestion)."""
        self._assert_child_owner_or_admin(okr, actor)
        parent = self._parent_objective(okr)
        if not parent:
            raise ValueError("Parent objective missing")

        parent_krs = self._parent_krs(parent)
        scope_name = self._scope_name_for_okr(okr)

        suggestion = self.ai.generate_child_okr(
            parent_objective=parent.title,
            parent_description=parent.description,
            parent_key_results=parent_krs,
            parent_level=(parent.level or "").upper(),
            child_level=(okr.level or "").upper(),
            scope_name=scope_name,
            scope_metadata=self._scope_metadata_for_okr(okr),
            org_name=None,
        )

        okr.title = suggestion["objective"]
        okr.description = suggestion.get("description")
        okr.ai_metadata = suggestion_to_ai_metadata(suggestion, parent_id=parent.id)
        okr.ai_confidence = suggestion.get("confidence")
        okr.ai_generation_reason = suggestion.get("reasoning")
        okr.ai_generation_version = (okr.ai_generation_version or 1) + 1
        self._apply_token_usage(okr, suggestion)
        okr.okr_status = OKR_STATUS_AI_DRAFT
        okr.review_status = OKR_STATUS_AI_DRAFT
        okr.rejection_reason = None

        existing = self.db.query(KeyResult).filter(KeyResult.objective_id == okr.id).all()
        for kr in existing:
            self.db.delete(kr)
        for kr_data in suggestion.get("key_results") or []:
            self.db.add(
                KeyResult(
                    id=str(uuid.uuid4()),
                    objective_id=okr.id,
                    title=kr_data["title"],
                    target_value=float(kr_data.get("target", 100)),
                    current_value=0.0,
                    unit=kr_data.get("unit") or "%",
                    weight=1.0,
                    status="NOT_STARTED",
                )
            )

        notify_regenerated(self.db, okr=okr, actor=actor)
        record_objective_version(
            self.db, okr=okr, change_type="REGENERATE", changed_by_id=actor.id
        )
        record_audit_event(
            org_id=okr.org_id,
            actor_user_id=actor.id,
            action=AUDIT_AI_CASCADE_REGENERATE,
            entity_type="OBJECTIVE",
            entity_id=okr.id,
            details={"parent_id": parent.id, "version": okr.ai_generation_version},
            db=self.db,
        )
        self.db.flush()
        return okr

    def _parent_objective(self, okr: Objective) -> Optional[Objective]:
        pid = okr.ai_generated_from_objective_id or okr.parent_id
        if not pid:
            return None
        return self.db.query(Objective).filter(Objective.id == pid).first()

    def _scope_name_for_okr(self, okr: Objective) -> str:
        for node_id in (okr.region_id, okr.plant_id, okr.department_id, okr.team_id):
            if node_id:
                name = self._node_name(node_id)
                if name:
                    return name
        owner = self.db.query(User).filter(User.id == okr.owner_id).first()
        return owner.name if owner else okr.title

    def _scope_metadata_for_okr(self, okr: Objective) -> Dict[str, Any]:
        meta: Dict[str, Any] = {}
        if okr.ai_metadata:
            try:
                meta = json.loads(okr.ai_metadata)
            except json.JSONDecodeError:
                meta = {}
        meta["node_type"] = (okr.level or "").upper()
        return meta

    def _node_name(self, node_id: str) -> str:
        n = self.db.query(OrgNode).filter(OrgNode.id == node_id).first()
        return n.name if n else node_id

    def _assert_child_owner_or_admin(self, okr: Objective, actor: User) -> None:
        role = normalize_role(actor.system_role)
        if role in (SystemRole.SUPER_ADMIN, SystemRole.CEO):
            return
        if okr.owner_id != actor.id:
            raise ValueError("Only the assigned owner may act on this AI draft")


def assert_okr_allows_kr_edit_for_ai(okr: Objective) -> None:
    if okr.kr_baseline_locked:
        raise ValueError("Key results are locked on this OKR")


def ai_draft_to_dict(obj: Objective, db: Session) -> Dict[str, Any]:
    """Serialize AI cascade OKR for API responses."""
    parent = (
        db.query(Objective)
        .filter(Objective.id == (obj.ai_generated_from_objective_id or obj.parent_id))
        .first()
    )
    owner = db.query(User).filter(User.id == obj.owner_id).first()
    krs = db.query(KeyResult).filter(KeyResult.objective_id == obj.id).all()
    meta: Dict[str, Any] = {}
    if obj.ai_metadata:
        try:
            meta = json.loads(obj.ai_metadata)
        except json.JSONDecodeError:
            meta = {}

    return {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "level": obj.level,
        "okr_status": obj.okr_status,
        "review_status": obj.review_status,
        "ai_generated": bool(obj.ai_generated),
        "ai_confidence": obj.ai_confidence,
        "ai_generation_reason": obj.ai_generation_reason,
        "ai_generation_version": obj.ai_generation_version,
        "ai_prompt_tokens": getattr(obj, "ai_prompt_tokens", None),
        "ai_completion_tokens": getattr(obj, "ai_completion_tokens", None),
        "ai_total_tokens": getattr(obj, "ai_total_tokens", None),
        "alignment_score": meta.get("alignment_score"),
        "ai_metadata": meta,
        "parent_id": obj.parent_id,
        "parent_title": parent.title if parent else None,
        "parent_objective_id": obj.ai_generated_from_objective_id,
        "owner_id": obj.owner_id,
        "owner_name": owner.name if owner else None,
        "region_id": obj.region_id,
        "quarter": obj.quarter,
        "year": obj.year,
        "submitted_for_parent_approval_at": (
            obj.submitted_for_parent_approval_at.isoformat()
            if obj.submitted_for_parent_approval_at
            else None
        ),
        "rejection_reason": obj.rejection_reason,
        "created_at": obj.created_at.isoformat() if obj.created_at else None,
        "key_results": [
            {
                "id": kr.id,
                "title": kr.title,
                "target_value": kr.target_value,
                "current_value": kr.current_value,
                "unit": kr.unit,
                "weight": kr.weight,
            }
            for kr in krs
        ],
    }
