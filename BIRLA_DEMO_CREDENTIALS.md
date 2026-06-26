# Birla Cement — Demo Login Credentials

**Organization:** Birla Cement  
**Domain:** `birlacement.test`  
**Password (all users):** `Test@1234`  
**Cycle:** Q2-2026  
**Users seeded:** 550  
**OKRs seeded:** 535 (all ACTIVE with approved KR progress)  

## Primary demo accounts (one per hierarchy level)

| Role | Email | Name | Demo focus |
|------|-------|------|------------|
| SUPER_ADMIN | `superadmin@birlacement.test` | System Admin | Admin panel, SUPER_ADMIN lifecycle override |
| CEO | `ceo@birlacement.test` | Vikram Mehta | Org OKR, constellation center, approve COO/CRO OKRs |
| COO | `coo@birlacement.test` | Arjun Malhotra | Approve Plant Head plant OKRs; validate plant KR progress |
| CRO | `cro@birlacement.test` | Kavita Rao | Approve Regional Head region OKRs; validate region KR progress |
| VP_OPERATIONS | `vp.manufacturing.west@birlacement.test` | Rahul Desai | West region cross-plant dashboard |
| REGIONAL_HEAD | `regionalhead.west@birlacement.test` | Ananya Desai | West region OKR (Awarpur, Rajashree, Dhar plants) |
| REGIONAL_HEAD | `regionalhead.north@birlacement.test` | Meera Singh | North region OKR (Hirmi, Roorkee, Kotputli) |
| PLANT_HEAD | `planthead.west2@birlacement.test` | Rajesh Iyer | Awarpur plant — full dept/team/individual OKR tree |
| PLANT_HEAD | `planthead.north1@birlacement.test` | Suresh Kumar | Hirmi plant head view |
| DEPT_HEAD | `hod.production.west2@birlacement.test` | Sanjay Kumar | Production dept OKR, approve manager OKRs |
| MANAGER | `manager.kiln.west2@birlacement.test` | Priya Nair | Kiln Shift A team, assign individual OKRs |
| TEAM_LEAD | `teamlead.shiftA.west2@birlacement.test` | Aarav Sharma | Shift A team OKR, validate employee progress |
| SUPERVISOR | `supervisor.shiftB.west2@birlacement.test` | Rohan Verma | Kiln Shift B supervisor, individual OKRs |
| EMPLOYEE | `employee.ccr1.west2@birlacement.test` | Sneha Patel | CCR operator — individual OKR + progress submit |
| EMPLOYEE | `employee.field1.west2@birlacement.test` | Deepa Joshi | Field operator — Shift B individual OKR |

## OKR data summary

| Level | Count |
|-------|-------|
| ORGANIZATION | 1 |
| REGION | 5 |
| PLANT | 14 |
| DEPARTMENT | 73 |
| TEAM | 144 |
| INDIVIDUAL | 298 |

## Reporting chain (approval routing)

```
CEO
 ├── COO → all Plant Heads → HODs → Managers/Team Leads/Supervisors → Employees
 └── CRO → all Regional Heads
```

## Re-seed command

```bash
python scripts/seed_birla_demo.py --reset
```
