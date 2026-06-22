import sqlite3
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Determine database path
DB_PATH = Path(__file__).parent.parent.parent / "manufacturing_os.db"

def gen_uuid():
    return str(uuid.uuid4())

def run_migration():
    """Migrate quarter/year fields to the new Cycle table."""
    if not DB_PATH.exists():
        print(msg.encode("ascii", "ignore").decode("ascii"))
        return False
    
    print(f"📦 Database: {DB_PATH}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # 1. Ensure `cycles` table exists
        cursor.execute("PRAGMA table_info(cycles)")
        if not cursor.fetchall():
            print("⚠️ 'cycles' table does not exist. Please run FastAPI to trigger create_all() first.")
            return False

        # 2. Add `cycle_id` column to `objectives` if not present
        cursor.execute("PRAGMA table_info(objectives)")
        obj_cols = {row[1] for row in cursor.fetchall()}
        if "cycle_id" not in obj_cols:
            cursor.execute("ALTER TABLE objectives ADD COLUMN cycle_id VARCHAR(255)")
            print("   ✅ Added cycle_id column to objectives")
            
        # 3. Find unique (org_id, quarter, year) combinations
        print("🔍 Scanning objectives for quarter/year to migrate...")
        cursor.execute("SELECT DISTINCT org_id, quarter, year FROM objectives WHERE quarter IS NOT NULL AND year IS NOT NULL")
        rows = cursor.fetchall()
        
        migrated_count = 0
        for org_id, quarter, year in rows:
            # Check if this cycle already exists
            cycle_name = f"{quarter}-{year}"
            cursor.execute("SELECT id FROM cycles WHERE org_id = ? AND name = ?", (org_id, cycle_name))
            cycle = cursor.fetchone()
            
            if not cycle:
                # Create a new cycle
                cycle_id = gen_uuid()
                now = datetime.utcnow().isoformat()
                
                # Determine dates based on quarter
                start_month = {"Q1": "01-01", "Q2": "04-01", "Q3": "07-01", "Q4": "10-01"}.get(quarter, "01-01")
                end_month = {"Q1": "03-31", "Q2": "06-30", "Q3": "09-30", "Q4": "12-31"}.get(quarter, "12-31")
                
                start_date = f"{year}-{start_month}"
                end_date = f"{year}-{end_month}"
                freeze_date = end_date # For simplicity
                
                cursor.execute("""
                    INSERT INTO cycles (id, org_id, name, cycle_type, start_date, end_date, freeze_date, status, applies_to_levels, created_at)
                    VALUES (?, ?, ?, 'QUARTERLY', ?, ?, ?, 'ACTIVE', '[]', ?)
                """, (cycle_id, org_id, cycle_name, start_date, end_date, freeze_date, now))
                print(f"   ✅ Created cycle: {cycle_name} for org {org_id}")
            else:
                cycle_id = cycle[0]
                
            # Update objectives
            cursor.execute("""
                UPDATE objectives 
                SET cycle_id = ? 
                WHERE org_id = ? AND quarter = ? AND year = ? AND cycle_id IS NULL
            """, (cycle_id, org_id, quarter, year))
            
            migrated_count += cursor.rowcount
            
        conn.commit()
        print(f"\n📊 Migrated {migrated_count} objectives to cycles.")
        
        # 4. Check if review_cycles exists and handle data transfer if needed (Phase 5 renames this logically)
        # Actually, Phase 5 just states to migrate quarter/year. We will leave ReviewCycle alone.
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
