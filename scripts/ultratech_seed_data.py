#!/usr/bin/env python3
"""
UltraTech Cement Manufacturing - Comprehensive Data Seed
Populates organization, regions, plants, departments, teams, users, OKRs, and progress data
"""

import uuid
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from server.database import SessionLocal
from server.models import (
    Organization, OrgNode, Plant, Department, Team, User, Shift,
    Objective, KeyResult, ProgressUpdate, Cycle, ReportingRelationship,
    ProgressSubmission, Designation
)
from server.auth import get_password_hash as hash_password
import json


def gen_id():
    return str(uuid.uuid4())


class UltraTechSeeder:
    def __init__(self, db: Session):
        self.db = db
        self.users_data = []
        self.credentials = {}
        self.org_id = None
        
    def create_organization(self):
        """Create UltraTech organization"""
        org = Organization(
            id=gen_id(),
            name="UltraTech Cement",
            domain="ultratech.com",
            industry="Manufacturing - Cement",
            size="LARGE",
            setup_completed=True
        )
        self.org_id = org.id
        self.db.add(org)
        self.db.flush()
        print(f"✓ Created organization: {org.name} (ID: {org.id})")
        return org

    def create_org_root_node(self, org):
        """Create organization root node"""
        root = OrgNode(
            id=org.id,
            org_id=org.id,
            parent_id=None,
            node_type="ORGANIZATION",
            name=org.name,
            path=org.id,
            depth=0,
            is_active=True
        )
        self.db.add(root)
        self.db.flush()
        return root

    def create_user(self, name, email, system_role, plant_id=None, department_id=None, team_id=None):
        """Create a user with password=123"""
        user = User(
            id=gen_id(),
            org_id=self.org_id,
            email=email,
            password_hash=hash_password("123"),
            name=name,
            system_role=system_role,
            is_active=True,
            plant_id=plant_id,
            department_id=department_id,
            team_id=team_id
        )
        self.db.add(user)
        self.db.flush()
        
        # Store credentials
        self.credentials[email] = {
            "name": name,
            "email": email,
            "password": "123",
            "role": system_role,
            "user_id": user.id
        }
        self.users_data.append(user)
        print(f"  ✓ Created user: {name} ({email}) as {system_role}")
        return user

    def create_designation(self, name, level, category):
        """Create a designation"""
        designation = Designation(
            id=gen_id(),
            org_id=self.org_id,
            name=name,
            level=level,
            category=category,
            is_active=True
        )
        self.db.add(designation)
        self.db.flush()
        return designation

    def create_cycle(self, name, cycle_type, start_date, end_date, freeze_date):
        """Create an OKR cycle"""
        cycle = Cycle(
            id=gen_id(),
            org_id=self.org_id,
            name=name,
            cycle_type=cycle_type,
            start_date=start_date,
            end_date=end_date,
            freeze_date=freeze_date,
            status="ACTIVE",
            applies_to_levels=[0, 1, 2, 3, 4, 5]
        )
        self.db.add(cycle)
        self.db.flush()
        return cycle

    def create_region(self, name, parent_node, head_user_id=None):
        """Create a region node"""
        region = OrgNode(
            id=gen_id(),
            org_id=self.org_id,
            parent_id=parent_node.id,
            node_type="REGION",
            name=name,
            code=name[:3].upper(),
            head_user_id=head_user_id,
            path=f"{parent_node.path}.{gen_id()}",
            depth=1,
            is_active=True
        )
        self.db.add(region)
        self.db.flush()
        print(f"  ✓ Created region: {name}")
        return region

    def create_plant(self, name, code, org_id, region_id=None):
        """Create a plant"""
        plant = Plant(
            id=gen_id(),
            org_id=org_id,
            name=name,
            code=code,
            location=f"{name} Location",
            is_active=True
        )
        self.db.add(plant)
        self.db.flush()
        
        # Also create plant node in org_nodes
        plant_path = f"{self.org_id}.{plant.id}" if not region_id else f"{self.org_id}.{region_id}.{plant.id}"
        plant_node = OrgNode(
            id=plant.id,
            org_id=org_id,
            parent_id=region_id or self.org_id,
            node_type="PLANT",
            name=name,
            code=code,
            path=plant_path,
            depth=2 if region_id else 1,
            is_active=True
        )
        self.db.add(plant_node)
        self.db.flush()
        print(f"    ✓ Created plant: {name} ({code})")
        return plant

    def create_department(self, name, plant_id, dept_type, org_id):
        """Create a department"""
        dept = Department(
            id=gen_id(),
            org_id=org_id,
            plant_id=plant_id,
            name=name,
            dept_type=dept_type,
            is_active=True
        )
        self.db.add(dept)
        self.db.flush()
        
        # Create department node
        dept_node = OrgNode(
            id=dept.id,
            org_id=org_id,
            parent_id=plant_id,
            node_type="DEPARTMENT",
            name=name,
            path=f"{self.org_id}.{plant_id}.{dept.id}",
            depth=2,
            is_active=True,
            node_metadata={"dept_type": dept_type}
        )
        self.db.add(dept_node)
        self.db.flush()
        print(f"      ✓ Created department: {name} ({dept_type})")
        return dept

    def create_team(self, name, department_id, org_id, lead_id=None):
        """Create a team"""
        team = Team(
            id=gen_id(),
            org_id=org_id,
            department_id=department_id,
            name=name,
            lead_id=lead_id,
            is_active=True
        )
        self.db.add(team)
        self.db.flush()
        
        # Create team node
        team_node = OrgNode(
            id=team.id,
            org_id=org_id,
            parent_id=department_id,
            node_type="TEAM",
            name=name,
            path=f"{self.org_id}.{department_id}.{team.id}",
            depth=3,
            head_user_id=lead_id,
            is_active=True
        )
        self.db.add(team_node)
        self.db.flush()
        print(f"        ✓ Created team: {name}")
        return team

    def create_objective(self, title, owner_id, level, plant_id=None, department_id=None, team_id=None, cycle_id=None, region_id=None):
        """Create an objective (OKR)"""
        quarter = None
        year = None
        if cycle_id:
            cycle = self.db.query(Cycle).filter(Cycle.id == cycle_id).first()
            if cycle:
                cycle_start = datetime.fromisoformat(cycle.start_date)
                quarter = f"Q{((cycle_start.month - 1) // 3) + 1}"
                year = cycle_start.year

        obj = Objective(
            id=gen_id(),
            org_id=self.org_id,
            owner_id=owner_id,
            title=title,
            level=level,
            plant_id=plant_id,
            region_id=region_id,
            department_id=department_id,
            team_id=team_id,
            cycle_id=cycle_id,
            creation_approval_status="APPROVED",
            status="ACTIVE",
            progress=0.0,
            okr_status="ACTIVE",
            quarter=quarter,
            year=year,
        )
        self.db.add(obj)
        self.db.flush()
        return obj

    def create_key_result(self, objective_id, title, target_value=100.0, current_value=0.0):
        """Create a key result"""
        kr = KeyResult(
            id=gen_id(),
            objective_id=objective_id,
            title=title,
            target_value=target_value,
            current_value=current_value,
            unit="%",
            status="IN_PROGRESS",
            weight=1.0
        )
        self.db.add(kr)
        self.db.flush()
        return kr

    def create_progress_update(self, key_result_id, submitted_by_id, new_value, notes=""):
        """Create a progress update"""
        progress = ProgressUpdate(
            id=gen_id(),
            key_result_id=key_result_id,
            submitted_by_id=submitted_by_id,
            previous_value=0.0,
            new_value=new_value,
            notes=notes,
            status="APPROVED",
            validation_level="MANAGER",
            progress_source="MANUAL"
        )
        self.db.add(progress)
        self.db.flush()
        return progress

    def create_shift(self, name, plant_id, supervisor_id, start_time, end_time):
        """Create a shift"""
        shift = Shift(
            id=gen_id(),
            org_id=self.org_id,
            plant_id=plant_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            supervisor_id=supervisor_id,
            is_active=True
        )
        self.db.add(shift)
        self.db.flush()
        return shift

    def seed(self):
        """Main seeding function"""
        print("\n" + "="*80)
        print("🏭 SEEDING ULTRATECH CEMENT MANUFACTURING SYSTEM")
        print("="*80 + "\n")

        # Create organization and root node
        org = self.create_organization()
        root_node = self.create_org_root_node(org)
        self.db.commit()

        # Create quarterly cycles (2025 + current planning quarter)
        cycles_2025 = [
            self.create_cycle("Q1-2025", "QUARTERLY", "2025-01-01", "2025-03-31", "2025-03-20"),
            self.create_cycle("Q2-2025", "QUARTERLY", "2025-04-01", "2025-06-30", "2025-06-20"),
            self.create_cycle("Q3-2025", "QUARTERLY", "2025-07-01", "2025-09-30", "2025-09-20"),
            self.create_cycle("Q4-2025", "QUARTERLY", "2025-10-01", "2025-12-31", "2025-12-20"),
        ]
        for old_cycle in cycles_2025:
            old_cycle.status = "CLOSED"

        cycle = self.create_cycle(
            name="Q1-2026",
            cycle_type="QUARTERLY",
            start_date="2026-01-01",
            end_date="2026-03-31",
            freeze_date="2026-03-20"
        )
        cycle.status = "ACTIVE"
        all_cycles = cycles_2025 + [cycle]
        self.db.commit()

        # ===== LEVEL 1: ADMIN & CEO =====
        print("\n📋 Creating Admin & CEO Level...")
        admin = self.create_user("Admin User", "admin@ultratech.com", "SUPER_ADMIN")
        ceo = self.create_user("Rajesh Kumar", "ceo@ultratech.com", "CEO")
        self.db.commit()

        # Update org root node with CEO as head
        root_node.head_user_id = ceo.id
        self.db.commit()

        # ===== LEVEL 2: REGIONS & REGION HEADS =====
        print("\n🗺️  Creating Regions...")
        
        region_data = [
            ("North Region", "NTH"),
            ("South Region", "STH"),
            ("East Region", "EST"),
            ("West Region", "WST")
        ]
        
        regions = {}
        region_heads = {}
        
        for region_name, code in region_data:
            region_head = self.create_user(
                f"{region_name} Head",
                f"{region_name.split()[0].lower()}head@ultratech.com",
                "VP_OPERATIONS"
            )
            region = self.create_region(region_name, root_node, head_user_id=region_head.id)
            region_head.org_node_id = region.id
            regions[region_name] = region
            region_heads[region_name] = region_head
        
        self.db.commit()

        # ===== LEVEL 3: PLANTS & PLANT HEADS =====
        print("\n🏭 Creating Plants...")
        
        plants_config = {
            "North Region": [
                ("Sutlej Plant", "PLT-NTH-001"),
                ("Himachal Plant", "PLT-NTH-002"),
            ],
            "South Region": [
                ("Karnataka Plant", "PLT-STH-001"),
                ("Tamil Nadu Plant", "PLT-STH-002"),
            ],
            "East Region": [
                ("Odisha Plant", "PLT-EST-001"),
                ("Jharkhand Plant", "PLT-EST-002"),
            ],
            "West Region": [
                ("Gujarat Plant", "PLT-WST-001"),
                ("Rajasthan Plant", "PLT-WST-002"),
            ]
        }
        
        plants_by_region = {}
        plant_heads = {}
        
        for region_name, plant_list in plants_config.items():
            plants_by_region[region_name] = {}
            for plant_name, code in plant_list:
                plant_head = self.create_user(
                    f"{plant_name} Head",
                    f"{plant_name.replace(' ', '').lower()}head@ultratech.com",
                    "PLANT_HEAD"
                )
                plant = self.create_plant(
                    plant_name, code, org.id,
                    region_id=regions[region_name].id
                )
                
                # Update plant node with plant head
                plant_node = self.db.query(OrgNode).filter(OrgNode.id == plant.id).first()
                plant_node.head_user_id = plant_head.id
                plant_head.org_node_id = plant.id
                plant_head.plant_id = plant.id
                
                plants_by_region[region_name][plant_name] = plant
                plant_heads[plant_name] = plant_head
        
        self.db.commit()

        # ===== LEVEL 4: DEPARTMENTS & DEPARTMENT HEADS =====
        print("\n🏢 Creating Departments...")
        
        dept_types = [
            ("Production", "PRODUCTION"),
            ("Quality Assurance", "QUALITY"),
            ("Maintenance & Engineering", "MAINTENANCE"),
            ("Administration", "ADMIN"),
            ("Human Resources", "HR")
        ]
        
        departments_by_plant = {}
        dept_heads = {}
        
        for region_name, plants_dict in plants_by_region.items():
            for plant_name, plant in plants_dict.items():
                departments_by_plant[plant_name] = {}
                
                for dept_name, dept_type in dept_types:
                    dept_head = self.create_user(
                        f"{plant_name} {dept_name} Head",
                        f"{plant_name.replace(' ', '').lower()}{dept_name.replace(' ', '').lower()}@ultratech.com",
                        "DEPT_HEAD"
                    )
                    
                    dept = self.create_department(
                        f"{plant_name} - {dept_name}",
                        plant.id,
                        dept_type,
                        org.id
                    )
                    
                    # Update department node with dept head
                    dept_node = self.db.query(OrgNode).filter(OrgNode.id == dept.id).first()
                    dept_node.head_user_id = dept_head.id
                    dept_head.org_node_id = dept.id
                    dept_head.department_id = dept.id
                    dept_head.plant_id = plant.id
                    
                    departments_by_plant[plant_name][dept_name] = dept
                    dept_heads[f"{plant_name}-{dept_name}"] = dept_head
        
        self.db.commit()

        # ===== LEVEL 5: TEAMS & TEAM LEADS =====
        print("\n👥 Creating Teams...")
        
        teams_by_dept = {}
        team_leads = {}
        
        for plant_name, depts_dict in departments_by_plant.items():
            teams_by_dept[plant_name] = {}
            
            for dept_name, dept in depts_dict.items():
                teams_by_dept[plant_name][dept_name] = {}
                
                # Each department has 2-3 teams
                team_count = 3 if dept_name == "Production" else 2
                
                for i in range(1, team_count + 1):
                    team_lead = self.create_user(
                        f"{plant_name} {dept_name} Team-{i} Lead",
                        f"{plant_name.replace(' ', '').lower()}{dept_name.replace(' ', '').lower()}tl{i}@ultratech.com",
                        "TEAM_LEAD"
                    )
                    
                    team = self.create_team(
                        f"{plant_name} {dept_name} Team-{i}",
                        dept.id,
                        org.id,
                        lead_id=team_lead.id
                    )
                    
                    teams_by_dept[plant_name][dept_name][f"Team-{i}"] = team
                    team_leads[f"{plant_name}-{dept_name}-Team-{i}"] = team_lead
        
        self.db.commit()

        # ===== LEVEL 6: MANAGERS & SUPERVISORS =====
        print("\n👔 Creating Managers & Supervisors...")
        
        managers = {}
        supervisors = {}
        
        for plant_name, teams_dict in teams_by_dept.items():
            managers[plant_name] = {}
            supervisors[plant_name] = {}
            
            for dept_name, teams in teams_dict.items():
                managers[plant_name][dept_name] = []
                supervisors[plant_name][dept_name] = []
                
                for team_name in teams.keys():
                    # Create manager
                    manager = self.create_user(
                        f"{plant_name} {dept_name} {team_name} Manager",
                        f"{plant_name.replace(' ', '').lower()}{dept_name.replace(' ', '').lower()}{team_name.replace('-', '')}mgr@ultratech.com",
                        "MANAGER"
                    )
                    managers[plant_name][dept_name].append(manager)
                    
                    # Create supervisors under each team
                    for j in range(1, 3):  # 2 supervisors per team
                        supervisor = self.create_user(
                            f"{plant_name} {dept_name} {team_name} Supervisor-{j}",
                            f"{plant_name.replace(' ', '').lower()}{dept_name.replace(' ', '').lower()}{team_name.replace('-', '')}sup{j}@ultratech.com",
                            "SUPERVISOR"
                        )
                        supervisors[plant_name][dept_name].append(supervisor)
        
        self.db.commit()

        # ===== LEVEL 7: EMPLOYEES =====
        print("\n👨‍💼 Creating Employees...")
        
        employees = {}
        
        for plant_name, supervisors_dict in supervisors.items():
            employees[plant_name] = {}
            
            for dept_name, sup_list in supervisors_dict.items():
                employees[plant_name][dept_name] = []
                
                # Create 5 employees per department
                for i in range(1, 6):
                    emp_name = f"Employee-{i} {dept_name}"
                    emp_email = f"{plant_name.replace(' ', '').lower()}{dept_name.replace(' ', '').lower()}emp{i}@ultratech.com"
                    
                    employee = self.create_user(
                        emp_name,
                        emp_email,
                        "EMPLOYEE"
                    )
                    employees[plant_name][dept_name].append(employee)
        
        self.db.commit()

        # ===== CREATE SHIFTS =====
        print("\n⏰ Creating Shifts...")
        for plant_name, sup_dict in supervisors.items():
            plant = list(plants_by_region.values())[0].get(plant_name) or \
                   list(plants_by_region.values())[1].get(plant_name) or \
                   list(plants_by_region.values())[2].get(plant_name) or \
                   list(plants_by_region.values())[3].get(plant_name)
            
            if plant:
                for sup_list in sup_dict.values():
                    for sup in sup_list[:1]:  # Only first supervisor
                        self.create_shift(
                            f"{plant_name} Morning Shift",
                            plant.id,
                            sup.id,
                            "06:00",
                            "14:00"
                        )
        self.db.commit()

        # ===== CREATE OKRs =====
        print("\n🎯 Creating OKRs & Key Results...")
        
        # Organization level OKR for CEO
        org_okr = self.create_objective(
            title="Achieve Production Excellence & Growth",
            owner_id=ceo.id,
            level="ORGANIZATION",
            cycle_id=random.choice(all_cycles).id
        )
        
        kr1 = self.create_key_result(org_okr.id, "Increase production capacity by 25%", target_value=25.0, current_value=0.0)
        kr2 = self.create_key_result(org_okr.id, "Achieve 98% operational efficiency", target_value=98.0, current_value=0.0)
        kr3 = self.create_key_result(org_okr.id, "Reduce quality defects by 40%", target_value=40.0, current_value=0.0)
        
        self.db.commit()

        # Plant level OKRs
        for region_name, plants_dict in plants_by_region.items():
            for plant_name, plant in plants_dict.items():
                plant_head = plant_heads[plant_name]
                
                plant_okr = self.create_objective(
                    title=f"{plant_name} - Production & Safety Excellence",
                    owner_id=plant_head.id,
                    level="PLANT",
                    plant_id=plant.id,
                    region_id=regions[region_name].id,
                    cycle_id=random.choice(all_cycles).id
                )
                
                self.create_key_result(plant_okr.id, "Achieve 99% on-time delivery", target_value=99.0, current_value=45.0)
                self.create_key_result(plant_okr.id, "Zero lost-time incidents", target_value=0.0, current_value=0.0)
                self.create_key_result(plant_okr.id, "Improve energy efficiency by 15%", target_value=15.0, current_value=5.0)
        
        self.db.commit()

        # Department level OKRs
        for plant_name, depts_dict in departments_by_plant.items():
            for dept_name, dept in depts_dict.items():
                dept_head = dept_heads.get(f"{plant_name}-{dept_name}")
                
                if dept_head:
                    if dept_name == "Production":
                        title = f"{dept_name} - Output & Efficiency Targets"
                        kr_titles = [
                            "Achieve 95% capacity utilization",
                            "Reduce downtime to <5%",
                            "Improve yield by 8%"
                        ]
                    elif dept_name == "Quality Assurance":
                        title = f"{dept_name} - Quality & Compliance"
                        kr_titles = [
                            "Maintain 99.5% quality score",
                            "Complete 100% compliance audits",
                            "Reduce rework by 30%"
                        ]
                    elif dept_name == "Maintenance & Engineering":
                        title = f"{dept_name} - Reliability & Maintenance"
                        kr_titles = [
                            "Achieve 96% equipment uptime",
                            "Reduce maintenance costs by 20%",
                            "Complete preventive maintenance 100%"
                        ]
                    else:
                        title = f"{dept_name} - Operations"
                        kr_titles = [
                            "Achieve all department targets",
                            "Maintain 100% compliance"
                        ]
                    
                    dept_okr = self.create_objective(
                        title=title,
                        owner_id=dept_head.id,
                        level="DEPARTMENT",
                        department_id=dept.id,
                        cycle_id=random.choice(all_cycles).id
                    )
                    
                    for kr_title in kr_titles:
                        target = 95.0 if "Achieve" in kr_title else 30.0
                        self.create_key_result(dept_okr.id, kr_title, target_value=target, current_value=0.0)
        
        self.db.commit()

        # Team level OKRs
        for plant_name, teams_dict in teams_by_dept.items():
            for dept_name, teams in teams_dict.items():
                for team_name, team in teams.items():
                    team_lead_key = f"{plant_name}-{dept_name}-{team_name}"
                    team_lead = team_leads.get(team_lead_key)
                    
                    if team_lead:
                        team_okr = self.create_objective(
                            title=f"{team_name} Performance & Execution",
                            owner_id=team_lead.id,
                            level="TEAM",
                            team_id=team.id,
                            cycle_id=random.choice(all_cycles).id
                        )
                        
                        self.create_key_result(team_okr.id, "Achieve all assigned targets", target_value=100.0, current_value=30.0)
                        self.create_key_result(team_okr.id, "Maintain team safety record", target_value=100.0, current_value=100.0)
        
        self.db.commit()

        # Individual Employee OKRs
        for plant_name, emp_dict in employees.items():
            for dept_name, emp_list in emp_dict.items():
                for emp in emp_list:
                    emp_okr = self.create_objective(
                        title=f"Individual Performance & Development",
                        owner_id=emp.id,
                        level="INDIVIDUAL",
                        cycle_id=random.choice(all_cycles).id
                    )
                    
                    self.create_key_result(emp_okr.id, "Complete assigned tasks on time", target_value=100.0, current_value=50.0)
                    self.create_key_result(emp_okr.id, "Attend all safety trainings", target_value=100.0, current_value=100.0)
        
        self.db.commit()

        # ===== CREATE PROGRESS UPDATES =====
        print("\n📊 Creating Progress Updates...")
        
        # Get some key results and update progress
        all_krs = self.db.query(KeyResult).limit(20).all()
        for kr in all_krs:
            # Create progress update
            submitter = self.db.query(User).filter(User.system_role == "MANAGER").first()
            if submitter:
                self.create_progress_update(
                    kr.id,
                    submitter.id,
                    kr.target_value * 0.6,
                    "Good progress this week"
                )
                
                # Update key result current value
                kr.current_value = kr.target_value * 0.6
        
        self.db.commit()

        print("\n" + "="*80)
        print("✅ SEEDING COMPLETED SUCCESSFULLY!")
        print("="*80)

        # Save credentials to file
        self.save_credentials()

    def save_credentials(self):
        """Save all credentials to a file"""
        output_file = "/root/ultratech_credentials.json"
        
        cred_list = []
        for email, cred in self.credentials.items():
            cred_list.append(cred)
        
        # Sort by role for easier reading
        role_order = ["SUPER_ADMIN", "CEO", "VP_OPERATIONS", "PLANT_HEAD", "DEPT_HEAD", 
                     "MANAGER", "TEAM_LEAD", "SUPERVISOR", "EMPLOYEE"]
        cred_list.sort(key=lambda x: (role_order.index(x['role']) if x['role'] in role_order else 999, x['email']))
        
        print("\n" + "="*80)
        print("📋 ULTRATECH CREDENTIALS")
        print("="*80)
        print(f"\n{len(cred_list)} users created.\n")
        print(f"{'Name':<40} | {'Email':<50} | {'Role':<20} | {'Password'}")
        print("-" * 130)
        
        for cred in cred_list:
            print(f"{cred['name']:<40} | {cred['email']:<50} | {cred['role']:<20} | {cred['password']}")
        
        print("\n" + "="*80)
        print(f"Saving credentials to: {output_file}")
        print("="*80 + "\n")
        
        try:
            with open(output_file, 'w') as f:
                json.dump(cred_list, f, indent=2)
            print(f"✓ Credentials saved to {output_file}")
        except Exception as e:
            print(f"⚠ Could not save to {output_file}: {e}")
            print("Displaying credentials in console only")


def main():
    """Main entry point"""
    print("\n🚀 Starting UltraTech Cement Manufacturing Seeder...\n")
    
    db = SessionLocal()
    try:
        seeder = UltraTechSeeder(db)
        seeder.seed()
    except Exception as e:
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
