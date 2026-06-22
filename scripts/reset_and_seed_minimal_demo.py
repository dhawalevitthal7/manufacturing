#!/usr/bin/env python3
"""
Remove UltraTech (and optionally ALL tenant data), then seed a minimal demo org
for testing OKRs, check-ins, and quarterly performance reviews.

Usage:
  python scripts/reset_and_seed_minimal_demo.py           # remove ultratech.com org only
  python scripts/reset_and_seed_minimal_demo.py --wipe-all  # clear entire DB, then seed

Password for every user: 123
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from server.database import SessionLocal, engine
from server.auth import get_password_hash
from server.models import (
    Organization,
    OrgNode,
    Plant,
    Department,
    Team,
    TeamMember,
    User,
    Cycle,
    Objective,
    KeyResult,
    ProgressUpdate,
    ReportingRelationship,
)
from server.performance_review_models import (
    PerformanceReviewCycle,
    ReviewCycleType,
    ReviewCycleStatus,
    ScoringConfiguration,
)
import server.performance_review_models  # noqa: F401 — register tables

PASSWORD = "123"
DOMAIN = "demo.local"


def gen_id() -> str:
    return str(uuid.uuid4())


def wipe_table(db: Session, table: str) -> None:
    try:
        db.execute(text(f"DELETE FROM {table}"))
    except Exception:
        pass


def wipe_all_data(db: Session) -> None:
    """Delete all application rows (SQLite). Order: children first."""
    tables = [
        "checkin_notifications",
        "checkin_escalations",
        "checkin_comments",
        "continuous_checkins",
        "review_audit_logs",
        "review_adjustments",
        "review_calculations",
        "review_sections",
        "employee_performance_reviews",
        "calibration_groups",
        "competency_assessments",
        "competencies",
        "competency_frameworks",
        "feedback_synthesis",
        "feedback_responses",
        "feedback_templates",
        "scoring_configurations",
        "perf_review_cycles",
        "reviews",
        "review_cycles",
        "kr_ingest_sources",
        "progress_updates",
        "progress_submissions",
        "key_results",
        "objectives",
        "reporting_relationships",
        "team_members",
        "module_access",
        "user_permission_profiles",
        "user_invitations",
        "audit_logs",
        "role_permission_rules",
        "users",
        "shifts",
        "teams",
        "departments",
        "plants",
        "org_nodes",
        "designations",
        "cycles",
        "dashboard_modules",
        "organizations",
    ]
    for t in tables:
        wipe_table(db, t)
    db.commit()
    print("[OK] Wiped all tenant data")


def remove_ultratech(db: Session) -> None:
    orgs = db.query(Organization).filter(
        Organization.domain.in_(["ultratech.com", "ultratech"])
    ).all()
    if not orgs:
        orgs = db.query(Organization).filter(Organization.name.ilike("%ultratech%")).all()
    if not orgs:
        print("No UltraTech organization found — use --wipe-all for full reset")
        return
    wipe_all_data(db)
    print(f"[OK] Removed {len(orgs)} UltraTech org(s) and all related data")


def add_reporting(db: Session, org_id: str, employee_id: str, manager_id: str) -> None:
    db.add(
        ReportingRelationship(
            org_id=org_id,
            employee_id=employee_id,
            manager_id=manager_id,
            relationship_type="DIRECT",
            is_active=True,
        )
    )


def create_okr_with_progress(
    db: Session,
    org_id: str,
    owner: User,
    level: str,
    title: str,
    kr_specs: list,
    cycle_id: str,
    parent_id: str | None = None,
    region_id: str | None = None,
    plant_id: str | None = None,
    department_id: str | None = None,
    team_id: str | None = None,
) -> Objective:
    obj = Objective(
        id=gen_id(),
        org_id=org_id,
        owner_id=owner.id,
        parent_id=parent_id,
        title=title,
        level=level,
        region_id=region_id,
        plant_id=plant_id,
        department_id=department_id,
        team_id=team_id,
        cycle_id=cycle_id,
        creation_approval_status="APPROVED",
        status="ACTIVE",
        okr_status="ACTIVE",
        progress=0.0,
        quarter="Q2",
        year=2026,
    )
    db.add(obj)
    db.flush()
    progresses = []
    for kr_title, target, current in kr_specs:
        kr = KeyResult(
            id=gen_id(),
            objective_id=obj.id,
            title=kr_title,
            target_value=target,
            current_value=current,
            unit="%",
            status="IN_PROGRESS" if current < target else "COMPLETED",
            weight=1.0,
        )
        db.add(kr)
        db.flush()
        db.add(
            ProgressUpdate(
                id=gen_id(),
                key_result_id=kr.id,
                submitted_by_id=owner.id,
                previous_value=0.0,
                new_value=current,
                notes="Demo seed progress",
                status="APPROVED",
                progress_source="MANUAL",
            )
        )
        progresses.append((current / target * 100) if target else 0)
    obj.progress = round(sum(progresses) / len(progresses), 1) if progresses else 0
    db.flush()
    return obj


def seed_minimal(db: Session) -> dict:
    """Minimal: 2 regions, 1 plant each, 1 Production dept, 1 team, 1 lead + 2 employees per team."""
    creds = {}
    now = datetime.now(timezone.utc)
    cycle_start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    cycle_end = (now + timedelta(days=60)).strftime("%Y-%m-%d")
    freeze = (now + timedelta(days=55)).strftime("%Y-%m-%d")

    org = Organization(
        id=gen_id(),
        name="Demo Manufacturing Co",
        domain=DOMAIN,
        industry="Manufacturing",
        size="SMALL",
        setup_completed=True,
    )
    db.add(org)
    db.flush()
    org_id = org.id

    root = OrgNode(
        id=org_id,
        org_id=org_id,
        parent_id=None,
        node_type="ORGANIZATION",
        name=org.name,
        path=org_id,
        depth=0,
        is_active=True,
    )
    db.add(root)

    okr_cycle = Cycle(
        id=gen_id(),
        org_id=org_id,
        name="Q2-2026",
        cycle_type="QUARTERLY",
        start_date=cycle_start,
        end_date=cycle_end,
        freeze_date=freeze,
        status="ACTIVE",
        applies_to_levels=[0, 1, 2, 3, 4, 5],
    )
    db.add(okr_cycle)
    db.flush()

    def user(name: str, email: str, role: str, **kw) -> User:
        u = User(
            id=gen_id(),
            org_id=org_id,
            email=email,
            password_hash=get_password_hash(PASSWORD),
            name=name,
            system_role=role,
            is_active=True,
            **kw,
        )
        db.add(u)
        db.flush()
        creds[email] = {"name": name, "role": role, "password": PASSWORD}
        return u

    admin = user("System Admin", f"admin@{DOMAIN}", "SUPER_ADMIN")
    ceo = user("Alex CEO", f"ceo@{DOMAIN}", "CEO")
    hr = user("Priya HR", f"hr@{DOMAIN}", "HR_HEAD")
    root.head_user_id = ceo.id

    regions_cfg = [
        ("North Region", "north", "north.rh"),
        ("South Region", "south", "south.rh"),
    ]
    region_nodes = {}
    regional_heads = {}

    for rname, slug, email_slug in regions_cfg:
        rn = OrgNode(
            id=gen_id(),
            org_id=org_id,
            parent_id=org_id,
            node_type="REGION",
            name=rname,
            code=slug.upper(),
            path=f"{org_id}.{gen_id()}",
            depth=1,
            is_active=True,
        )
        db.add(rn)
        db.flush()
        rn.path = f"{org_id}.{rn.id}"
        region_nodes[slug] = rn
        rh = user(f"{rname} Head", f"{email_slug}@{DOMAIN}", "REGIONAL_HEAD")
        rn.head_user_id = rh.id
        rh.org_node_id = rn.id
        regional_heads[slug] = rh
        add_reporting(db, org_id, rh.id, ceo.id)

    plants = {}
    plant_heads = {}
    departments = {}
    managers = {}
    teams_by_plant = {}
    team_leads = {}
    employees = {}

    for slug in ("north", "south"):
        rn = region_nodes[slug]
        pname = f"{slug.title()} Plant"
        plant = Plant(
            id=gen_id(),
            org_id=org_id,
            name=pname,
            code=f"{slug.upper()}-P1",
            location=pname,
            is_active=True,
        )
        db.add(plant)
        db.flush()
        pn = OrgNode(
            id=plant.id,
            org_id=org_id,
            parent_id=rn.id,
            node_type="PLANT",
            name=pname,
            code=plant.code,
            path=f"{rn.path}.{plant.id}",
            depth=2,
            is_active=True,
        )
        db.add(pn)
        db.flush()
        ph = user(f"{pname} Head", f"{slug}.plant@{DOMAIN}", "PLANT_HEAD", plant_id=plant.id)
        pn.head_user_id = ph.id
        plants[slug] = plant
        plant_heads[slug] = ph
        add_reporting(db, org_id, ph.id, regional_heads[slug].id)

        dept = Department(
            id=gen_id(),
            org_id=org_id,
            plant_id=plant.id,
            name="Production",
            dept_type="PRODUCTION",
            is_active=True,
        )
        db.add(dept)
        db.flush()
        dn = OrgNode(
            id=dept.id,
            org_id=org_id,
            parent_id=plant.id,
            node_type="DEPARTMENT",
            name=dept.name,
            path=f"{pn.path}.{dept.id}",
            depth=3,
            is_active=True,
        )
        db.add(dn)
        db.flush()
        dh = user(f"{pname} Production Head", f"{slug}.prod.dept@{DOMAIN}", "DEPT_HEAD", plant_id=plant.id, department_id=dept.id)
        dn.head_user_id = dh.id
        departments[slug] = dept
        add_reporting(db, org_id, dh.id, ph.id)

        mgr = user(f"{pname} Production Manager", f"{slug}.prod.mgr@{DOMAIN}", "MANAGER", plant_id=plant.id, department_id=dept.id)
        managers[slug] = mgr
        add_reporting(db, org_id, mgr.id, dh.id)

        team_specs = [
            ("Team A", "lead", ("emp1", "emp2"), True),
            ("Team B", "lead.b", ("emp.b1",), True),
            ("Team C", "lead.c", ("emp.c1",), False),
        ]
        plant_teams = []
        plant_employees = []
        primary_lead = None

        for team_name, lead_suffix, emp_suffixes, _create_team_okr in team_specs:
            team = Team(id=gen_id(), org_id=org_id, department_id=dept.id, name=team_name, is_active=True)
            db.add(team)
            db.flush()
            tn = OrgNode(
                id=team.id,
                org_id=org_id,
                parent_id=dept.id,
                node_type="TEAM",
                name=team.name,
                path=f"{dn.path}.{team.id}",
                depth=4,
                is_active=True,
            )
            db.add(tn)
            db.flush()

            lead_email = f"{slug}.prod.{lead_suffix}@{DOMAIN}"
            lead = user(
                f"{pname} {team_name} Lead",
                lead_email,
                "TEAM_LEAD",
                plant_id=plant.id,
                department_id=dept.id,
                team_id=team.id,
            )
            team.lead_id = lead.id
            tn.head_user_id = lead.id
            add_reporting(db, org_id, lead.id, mgr.id)
            if lead_suffix == "lead":
                primary_lead = lead

            emps = []
            for idx, emp_suffix in enumerate(emp_suffixes, start=1):
                e = user(
                    f"{pname} {team_name} Employee {idx}",
                    f"{slug}.{emp_suffix}@{DOMAIN}",
                    "EMPLOYEE",
                    plant_id=plant.id,
                    department_id=dept.id,
                    team_id=team.id,
                    org_node_id=tn.id,
                )
                db.add(TeamMember(org_id=org_id, team_id=team.id, user_id=e.id, is_team_lead=False, is_active=True))
                add_reporting(db, org_id, e.id, mgr.id)
                emps.append(e)

            plant_teams.append((team, lead, emps, _create_team_okr))
            plant_employees.extend(emps)

        teams_by_plant[slug] = plant_teams
        team_leads[slug] = primary_lead
        employees[slug] = plant_employees

    db.flush()

    # OKRs — one per level with progress
    org_okr = create_okr_with_progress(
        db, org_id, ceo, "ORGANIZATION",
        "Drive enterprise production excellence",
        [("Revenue growth %", 20, 12), ("Group OEE %", 95, 78)],
        okr_cycle.id,
    )

    region_okrs = {}
    for slug, rn in region_nodes.items():
        region_okrs[slug] = create_okr_with_progress(
            db, org_id, regional_heads[slug], "REGION",
            f"{rn.name} — regional output targets",
            [("Regional throughput %", 100, 65), ("Safety index", 100, 92)],
            okr_cycle.id,
            parent_id=org_okr.id,
            region_id=rn.id,
        )

    for slug, plant in plants.items():
        pn = db.query(OrgNode).filter(OrgNode.id == plant.id).first()
        create_okr_with_progress(
            db, org_id, plant_heads[slug], "PLANT",
            f"{plant.name} — plant reliability",
            [("Plant uptime %", 99, 88), ("Cost per ton", 100, 72)],
            okr_cycle.id,
            parent_id=region_okrs[slug].id,
            region_id=region_nodes[slug].id,
            plant_id=plant.id,
        )

    for slug, dept in departments.items():
        dh = db.query(User).filter(User.email == f"{slug}.prod.dept@{DOMAIN}").first()
        create_okr_with_progress(
            db, org_id, dh, "DEPARTMENT",
            "Production department — weekly output",
            [("Dept utilization %", 95, 70), ("Scrap rate reduction %", 30, 18)],
            okr_cycle.id,
            parent_id=None,
            plant_id=plants[slug].id,
            department_id=dept.id,
        )

    for slug in ("north", "south"):
        dept = departments[slug]
        plant = plants[slug]
        for team, lead, emps, with_team_okr in teams_by_plant[slug]:
            if with_team_okr:
                create_okr_with_progress(
                    db, org_id, lead, "TEAM",
                    f"{team.name} — shift execution",
                    [("Shift targets met %", 100, 55), ("5S audit score", 100, 80)],
                    okr_cycle.id,
                    team_id=team.id,
                    department_id=dept.id,
                    plant_id=plant.id,
                )
            for e in emps:
                create_okr_with_progress(
                    db, org_id, e, "INDIVIDUAL",
                    f"{e.name} — individual goals",
                    [("Personal output units", 500, 320), ("Quality pass rate %", 99, 94)],
                    okr_cycle.id,
                    team_id=team.id,
                    department_id=dept.id,
                    plant_id=plant.id,
                )

    # Performance review cycle + reviews for all employees
    pr_start = now - timedelta(days=90)
    pr_end = now + timedelta(days=30)
    perf_cycle = PerformanceReviewCycle(
        id=gen_id(),
        org_id=org_id,
        cycle_type=ReviewCycleType.QUARTERLY,
        name="Q2-2026 Performance Review",
        start_date=pr_start,
        end_date=pr_end,
        submission_start=now - timedelta(days=14),
        submission_end=now + timedelta(days=21),
        status=ReviewCycleStatus.ACTIVE,
    )
    db.add(perf_cycle)
    db.add(ScoringConfiguration(org_id=org_id))
    db.flush()

    from server.services.employee_review_service import EmployeeReviewService
    from server.services.okr_review_integration import attach_okr_context_to_review

    review_svc = EmployeeReviewService(db)
    review_count = 0
    for u in db.query(User).filter(User.org_id == org_id, User.system_role == "EMPLOYEE").all():
        rel = db.query(ReportingRelationship).filter(
            ReportingRelationship.employee_id == u.id,
            ReportingRelationship.relationship_type == "DIRECT",
        ).first()
        if not rel:
            continue
        try:
            rev = review_svc.create_performance_review(
                org_id=org_id,
                employee_id=u.id,
                manager_id=rel.manager_id,
                review_cycle_id=perf_cycle.id,
                review_period_start=pr_start,
                review_period_end=pr_end,
            )
            attach_okr_context_to_review(db, rev)
            review_count += 1
        except ValueError:
            pass

    db.commit()

    creds["_meta"] = {
        "org_id": org_id,
        "okr_cycle_id": okr_cycle.id,
        "perf_cycle_id": perf_cycle.id,
        "reviews_created": review_count,
    }
    return creds


def write_credentials_file(creds: dict) -> None:
    path = Path(__file__).parent.parent / "DEMO_MINIMAL_CREDENTIALS.md"
    lines = [
        "# Demo Manufacturing — Minimal Test Data",
        "",
        "**Password for all users:** `123`",
        "",
        "## Org",
        f"- Name: Demo Manufacturing Co",
        f"- Domain: `{DOMAIN}`",
        "",
        "## Structure",
        "- 1 CEO, 2 Regions, 2 Plants, 2 Production departments",
        "- 1 Manager + 3 Teams (A/B/C) per Production department",
        "- 1 Team Lead + employees per team (~23 users total)",
        "- OKRs at every level with sample progress",
        "- Quarterly performance review cycle active",
        "",
        "## Login accounts",
        "",
        "| Email | Role | Use for |",
        "|-------|------|---------|",
    ]
    order = [
        (f"admin@{DOMAIN}", "SUPER_ADMIN", "Admin"),
        (f"ceo@{DOMAIN}", "CEO", "Org OKR"),
        (f"hr@{DOMAIN}", "HR_HEAD", "Calibration / publish"),
        (f"north.rh@{DOMAIN}", "REGIONAL_HEAD", "Regional OKR (dashboard)"),
        (f"south.rh@{DOMAIN}", "REGIONAL_HEAD", "Regional OKR (dashboard)"),
        (f"north.plant@{DOMAIN}", "PLANT_HEAD", "Plant OKR"),
        (f"south.plant@{DOMAIN}", "PLANT_HEAD", "Plant OKR"),
        (f"north.prod.dept@{DOMAIN}", "DEPT_HEAD", "Dept moderation / escalation"),
        (f"south.prod.dept@{DOMAIN}", "DEPT_HEAD", "Dept moderation"),
        (f"north.prod.mgr@{DOMAIN}", "MANAGER", "Check-in inbox + manager review"),
        (f"south.prod.mgr@{DOMAIN}", "MANAGER", "Check-in inbox"),
        (f"north.prod.lead@{DOMAIN}", "TEAM_LEAD", "Team OKR"),
        (f"south.prod.lead@{DOMAIN}", "TEAM_LEAD", "Team OKR"),
        (f"north.emp1@{DOMAIN}", "EMPLOYEE", "Check-in + self review"),
        (f"north.emp2@{DOMAIN}", "EMPLOYEE", "Check-in + self review"),
        (f"south.emp1@{DOMAIN}", "EMPLOYEE", "Check-in + self review"),
        (f"south.emp2@{DOMAIN}", "EMPLOYEE", "Check-in + self review"),
    ]
    for email, role, use in order:
        lines.append(f"| `{email}` | {role} | {use} |")
    meta = creds.get("_meta", {})
    lines.extend([
        "",
        "## IDs (for API debugging)",
        f"- org_id: `{meta.get('org_id', '')}`",
        f"- okr_cycle_id: `{meta.get('okr_cycle_id', '')}`",
        f"- perf_review_cycle_id: `{meta.get('perf_cycle_id', '')}`",
        f"- performance reviews created: {meta.get('reviews_created', 0)}",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Wrote {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe-all", action="store_true", help="Delete ALL data in DB (not only UltraTech)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.wipe_all:
            wipe_all_data(db)
        else:
            remove_ultratech(db)

        print("\n" + "=" * 60)
        print("Seeding minimal demo org...")
        print("=" * 60)
        creds = seed_minimal(db)
        write_credentials_file(creds)
        print("\n[DONE] Done. Open DEMO_MINIMAL_CREDENTIALS.md and DEMO_TESTING_GUIDE.md")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
