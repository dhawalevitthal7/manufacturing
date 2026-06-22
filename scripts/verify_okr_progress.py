"""
Verify OKR Progress Updates - Show Current State
=================================================
"""

import sys
sys.path.insert(0, '/c/Users/dhawa/Desktop/manufacturing')

from server.database import SessionLocal
from server.models import Objective, KeyResult, Organization
from server.okr_cascade_service import calculate_objective_progress


def verify_updates():
    """Verify and display updated progress."""
    db = SessionLocal()
    
    try:
        # Find organization
        org = db.query(Organization).filter(
            Organization.name.ilike("%UltraTech%")
        ).first()
        
        if not org:
            print("Organization not found")
            return
        
        org_id = org.id
        levels = ["ORGANIZATION", "PLANT", "DEPARTMENT", "TEAM", "INDIVIDUAL"]
        
        print("\n" + "="*80)
        print(f"OKR PROGRESS VERIFICATION - {org.name}")
        print("="*80)
        
        grand_totals = {
            "total_okrs": 0,
            "on_track": 0,
            "at_risk": 0,
            "off_track": 0,
            "completed": 0,
        }
        
        for level in levels:
            print(f"\n{'-'*80}")
            print(f"{level} LEVEL OKRs")
            print(f"{'-'*80}")
            
            objs = db.query(Objective).filter(
                Objective.org_id == org_id,
                Objective.level == level
            ).all()
            
            print(f"Total: {len(objs)}\n")
            
            level_totals = {
                "on_track": 0,
                "at_risk": 0,
                "off_track": 0,
                "completed": 0,
            }
            
            for obj in sorted(objs, key=lambda x: x.progress or 0, reverse=True):
                # Get KRs for this OKR
                krs = db.query(KeyResult).filter(
                    KeyResult.objective_id == obj.id
                ).all()
                
                progress = obj.progress or 0.0
                
                # Categorize
                if progress >= 90:
                    status = "COMPLETED"
                    level_totals["completed"] += 1
                    grand_totals["completed"] += 1
                elif progress >= 70:
                    status = "ON_TRACK"
                    level_totals["on_track"] += 1
                    grand_totals["on_track"] += 1
                elif progress >= 40:
                    status = "AT_RISK"
                    level_totals["at_risk"] += 1
                    grand_totals["at_risk"] += 1
                else:
                    status = "OFF_TRACK"
                    level_totals["off_track"] += 1
                    grand_totals["off_track"] += 1
                
                grand_totals["total_okrs"] += 1
                
                kr_summary = f"{len(krs)} KRs"
                if krs:
                    kr_progress_vals = [kr.current_value for kr in krs]
                    kr_avg = sum(kr_progress_vals) / len(kr_progress_vals) if kr_progress_vals else 0
                    kr_summary += f" (avg: {kr_avg:.1f})"
                
                print(f"  [{status:12}] {progress:6.1f}% | {obj.title[:55]:55} | {kr_summary}")
            
            print(f"\n  Summary: ON_TRACK={level_totals['on_track']} | AT_RISK={level_totals['at_risk']} | OFF_TRACK={level_totals['off_track']} | COMPLETED={level_totals['completed']}")
        
        # Grand summary
        print(f"\n{'='*80}")
        print("GRAND SUMMARY")
        print(f"{'='*80}")
        print(f"Total OKRs Updated: {grand_totals['total_okrs']}")
        print(f"  On Track:  {grand_totals['on_track']:3} ({grand_totals['on_track']*100/max(1,grand_totals['total_okrs']):5.1f}%)")
        print(f"  At Risk:   {grand_totals['at_risk']:3} ({grand_totals['at_risk']*100/max(1,grand_totals['total_okrs']):5.1f}%)")
        print(f"  Off Track: {grand_totals['off_track']:3} ({grand_totals['off_track']*100/max(1,grand_totals['total_okrs']):5.1f}%)")
        print(f"  Completed: {grand_totals['completed']:3} ({grand_totals['completed']*100/max(1,grand_totals['total_okrs']):5.1f}%)")
        
        avg_progress = sum([o.progress or 0 for o in db.query(Objective).filter(Objective.org_id == org_id).all()]) / max(1, grand_totals['total_okrs'])
        print(f"\nAverage Progress: {avg_progress:.1f}%")
        print("="*80 + "\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    verify_updates()
