#!/usr/bin/env python3
"""
Smoke-test checklist for Corporate Committee + Universal OKR Creation Approval.

Run after re-seeding Birla demo:
  python scripts/reset_and_seed_minimal_demo.py   # or seed_birla_demo reset
  python scripts/verify_corporate_committee_okr.py

Requires backend at http://localhost:8000 (or API_BASE env).
"""

from __future__ import annotations

import os
import sys

import requests

API_BASE = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
PASSWORD = "Test@1234"
DOMAIN = "birlacement.test"

CHECKS: list[tuple[str, bool, str]] = []


def login(email: str) -> dict:
    r = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if not token:
        raise RuntimeError(f"No token for {email}")
    return {"Authorization": f"Bearer {token}"}


def get_user(headers: dict) -> dict:
    r = requests.get(f"{API_BASE}/api/auth/me", headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def create_okr(headers: dict, payload: dict) -> dict:
    r = requests.post(f"{API_BASE}/api/okrs", json=payload, headers=headers, timeout=30)
    if r.status_code >= 400:
        raise RuntimeError(f"Create OKR failed: {r.status_code} {r.text}")
    return r.json()


def approve_okr(headers: dict, okr_id: str) -> dict:
    r = requests.post(
        f"{API_BASE}/api/okrs/hierarchy/{okr_id}/approve",
        json={"approval_notes": "Smoke test approve"},
        headers=headers,
        timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Approve failed: {r.status_code} {r.text}")
    return r.json()


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print(f"Corporate Committee OKR smoke tests → {API_BASE}\n")

    try:
        mgr_h = login(f"manager.kiln.west2@{DOMAIN}")
        hod_h = login(f"hod.production.west2@{DOMAIN}")
        emp_h = login(f"employee.ccr1.west2@{DOMAIN}")
        ph_h = login(f"planthead.west2@{DOMAIN}")
        coo_h = login(f"coo@{DOMAIN}")
        cro_h = login(f"cro@{DOMAIN}")
        rh_h = login(f"regionalhead.west@{DOMAIN}")
        ceo_h = login(f"ceo@{DOMAIN}")
    except Exception as e:
        print(f"Login failed (re-seed Birla demo?): {e}")
        return 1

    mgr = get_user(mgr_h)
    emp = get_user(emp_h)

    # 1. Manager → Individual OKR for employee
    try:
        okr = create_okr(mgr_h, {
            "title": "Smoke: Manager Individual OKR",
            "level": "INDIVIDUAL",
            "owner_id": emp["id"],
            "description": "Universal approval test",
        })
        record(
            "Manager Individual OKR → PENDING_APPROVAL",
            okr.get("okr_status") == "PENDING_APPROVAL",
            f"status={okr.get('okr_status')} approver={okr.get('pending_approver_name')}",
        )
        hod_pending = requests.get(
            f"{API_BASE}/api/okrs/pending-lifecycle-approval", headers=hod_h, timeout=30
        ).json()
        record(
            "Dept Head sees creation queue",
            any(o["id"] == okr["id"] for o in hod_pending),
        )
        my_emp = requests.get(f"{API_BASE}/api/okrs/my", headers=emp_h, timeout=30).json()
        emp_okr = next((o for o in my_emp if o["id"] == okr["id"]), None)
        record(
            "Employee sees OKR but not ACTIVE",
            emp_okr is not None and emp_okr.get("okr_status") == "PENDING_APPROVAL",
        )
        approve_okr(hod_h, okr["id"])
        my_emp2 = requests.get(f"{API_BASE}/api/okrs/my", headers=emp_h, timeout=30).json()
        emp_okr2 = next((o for o in my_emp2 if o["id"] == okr["id"]), None)
        record(
            "After Dept Head approve → Employee ACTIVE",
            emp_okr2 and emp_okr2.get("okr_status") == "ACTIVE",
        )
    except Exception as e:
        record("Manager → Individual flow", False, str(e))

    # 2. Plant Head → Plant OKR → COO approves
    try:
        plant_okr = create_okr(ph_h, {
            "title": "Smoke: Plant OKR",
            "level": "PLANT",
            "description": "COO approval test",
        })
        record(
            "Plant OKR approver is COO",
            plant_okr.get("pending_approver_role") == "COO",
            plant_okr.get("pending_approver_name", ""),
        )
        approve_okr(coo_h, plant_okr["id"])
        record("COO approved Plant OKR", True)
    except Exception as e:
        record("Plant Head → COO flow", False, str(e))

    # 3. Regional Head → Region OKR → CRO approves
    try:
        region_okr = create_okr(rh_h, {
            "title": "Smoke: Region OKR",
            "level": "REGION",
            "description": "CRO approval test",
        })
        record(
            "Region OKR approver is CRO",
            region_okr.get("pending_approver_role") == "CRO",
            region_okr.get("pending_approver_name", ""),
        )
        approve_okr(cro_h, region_okr["id"])
        record("CRO approved Region OKR", True)
    except Exception as e:
        record("Regional Head → CRO flow", False, str(e))

    # 4. CEO org OKR stays DRAFT (publish bypass)
    try:
        org_okr = create_okr(ceo_h, {
            "title": "Smoke: Org OKR",
            "level": "ORGANIZATION",
            "description": "CEO publish test",
        })
        record(
            "CEO org OKR not auto-pending",
            org_okr.get("okr_status") == "DRAFT",
            f"status={org_okr.get('okr_status')}",
        )
    except Exception as e:
        record("CEO org OKR DRAFT", False, str(e))

    print()
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    total = len(CHECKS)
    print(f"Result: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
