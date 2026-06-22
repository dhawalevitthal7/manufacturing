"""
Update OKR Progress for All OKRs in Ultratech Cement Company
==============================================================

This script intelligently updates progress for all OKRs with realistic values:
- On-track: 70-90%
- At-risk: 40-70%
- Off-track: 0-40%
- Completed: 90-100%
"""

import sys
import random
from datetime import datetime
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, '/c/Users/dhawa/Desktop/manufacturing')

from server.database import SessionLocal
from server.models import Objective, KeyResult
from server.okr_cascade_service import OKRCascadeService


def get_realistic_progress() -> float:
    """
    Generate realistic progress distribution:
    - 30% on-track (70-90%)
    - 35% at-risk (40-70%)
    - 20% off-track (0-40%)
    - 15% completed (90-100%)
    """
    rand = random.random()
    
    if rand < 0.15:  # 15% completed
        return round(random.uniform(90, 100), 1)
    elif rand < 0.35:  # 20% off-track
        return round(random.uniform(0, 40), 1)
    elif rand < 0.70:  # 35% at-risk
        return round(random.uniform(40, 70), 1)
    else:  # 30% on-track
        return round(random.uniform(70, 90), 1)


def update_key_result_progress(kr: KeyResult, target_progress: float) -> None:
    """
    Update Key Result's current_value based on target progress percentage.
    
    Formula: current_value = (target_progress / 100) * target_value
    """
    new_value = (target_progress / 100) * kr.target_value
    kr.current_value = round(new_value, 2)
    print(f"  KR: '{kr.title}' → {kr.current_value}/{kr.target_value} ({target_progress}%)")


def update_okr_progress(db: Session, okr_id: str, cascade_service: OKRCascadeService) -> None:
    """
    Update progress for a single OKR by updating its Key Results.
    """
    obj = db.query(Objective).filter(Objective.id == okr_id).first()
    if not obj:
        return
    
    krs = db.query(KeyResult).filter(KeyResult.objective_id == okr_id).all()
    
    if not krs:
        print(f"  ⚠️  No Key Results found for '{obj.title}'")
        return
    
    # Generate target progress
    target_progress = get_realistic_progress()
    
    # Update each KR with the same progress percentage
    for kr in krs:
        update_key_result_progress(kr, target_progress)
    
    # Refresh objective progress (recalculate from KRs)
    cascade_service.refresh_objective_progress_for_session(okr_id)


def update_okrs_by_level(
    db: Session,
    cascade_service: OKRCascadeService,
    org_id: str,
    levels: list,
) -> dict:
    """
    Update OKRs by hierarchy level.
    """
    stats = {
        "total_updated": 0,
        "by_level": {},
        "errors": [],
    }
    
    for level in levels:
        print(f"\n{'='*70}")
        print(f"UPDATING {level} LEVEL OKRs")
        print(f"{'='*70}")
        
        try:
            objs = db.query(Objective).filter(
                Objective.org_id == org_id,
                Objective.level == level
            ).all()
            
            print(f"Found {len(objs)} OKRs at {level} level")
            
            level_count = 0
            for obj in objs:
                print(f"\n✓ {obj.title}")
                update_okr_progress(db, obj.id, cascade_service)
                level_count += 1
            
            stats["by_level"][level] = level_count
            stats["total_updated"] += level_count
            
            print(f"\n→ Updated {level_count} {level} OKRs")
            
        except Exception as e:
            error_msg = f"Error updating {level} OKRs: {str(e)}"
            print(f"❌ {error_msg}")
            stats["errors"].append(error_msg)
    
    return stats


def propagate_all_progress(
    db: Session,
    cascade_service: OKRCascadeService,
    org_id: str,
) -> None:
    """
    Propagate progress upward through hierarchy after all updates.
    """
    print(f"\n{'='*70}")
    print("PROPAGATING PROGRESS UPWARD")
    print(f"{'='*70}\n")
    
    # Get all individual-level OKRs as starting points
    individual_okrs = db.query(Objective).filter(
        Objective.org_id == org_id,
        Objective.level == "INDIVIDUAL"
    ).all()
    
    propagated = set()
    
    for okr in individual_okrs:
        if okr.id not in propagated:
            result = cascade_service.propagate_progress_upward(okr.id)
            if result["success"]:
                print(f"✓ Propagated from '{okr.title}'")
                propagated.update([p["id"] for p in result.get("propagated", [])])


def main():
    """Main execution function."""
    db = SessionLocal()
    cascade_service = OKRCascadeService(db)
    
    try:
        # Find Ultratech Cement Company Organization
        from server.models import Organization
        org = db.query(Organization).filter(
            Organization.name.ilike("%UltraTech%")
        ).first()
        
        if not org:
            print("❌ ERROR: UltraTech Cement organization not found in database")
            print("Available organizations:")
            orgs = db.query(Organization).all()
            for o in orgs:
                print(f"  - {o.name} ({o.id})")
            return
        
        org_id = org.id
        
        # Levels to update (all of them)
        levels = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]
        
        print("\n" + "="*70)
        print("OKR PROGRESS UPDATE - ULTRATECH CEMENT COMPANY")
        print("="*70)
        print(f"Organization ID: {org_id}")
        print(f"Levels: {', '.join(levels)}")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        
        # Update OKRs by level
        stats = update_okrs_by_level(db, cascade_service, org_id, levels)
        
        # Propagate progress upward
        propagate_all_progress(db, cascade_service, org_id)
        
        # Commit all changes
        db.commit()
        print(f"\n✓ All changes committed to database")
        
        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Total OKRs Updated: {stats['total_updated']}")
        for level, count in stats['by_level'].items():
            print(f"  {level}: {count}")
        
        if stats['errors']:
            print(f"\nErrors encountered:")
            for error in stats['errors']:
                print(f"  - {error}")
        else:
            print("\n✓ No errors - all updates completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
