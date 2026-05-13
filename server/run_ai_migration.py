#!/usr/bin/env python3
"""
Database Migration Script - Add Quarter and AI Fields
Adds missing columns for AI OKR system and quarterly planning
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "manufacturing_os.db"

def run_migration():
    """Run database migration for quarter and AI fields"""
    
    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        return False
    
    print(f"📦 Database: {DB_PATH}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Check objectives table columns
        cursor.execute("PRAGMA table_info(objectives)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        print("🔍 Checking objectives table...")
        
        # Columns to add
        objectives_columns = [
            ("quarter", "VARCHAR(5)"),  # Q1, Q2, Q3, Q4
            ("year", "INTEGER"),
            ("ai_generated", "BOOLEAN DEFAULT FALSE"),
            ("ai_metadata", "TEXT"),
            ("okr_status", "VARCHAR(50) DEFAULT 'DRAFT'"),
        ]
        
        added_count = 0
        for col_name, col_type in objectives_columns:
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE objectives ADD COLUMN {col_name} {col_type}")
                    print(f"   ✅ Added column: {col_name}")
                    added_count += 1
                except sqlite3.OperationalError as e:
                    if "duplicate column" in str(e).lower():
                        print(f"   ⚠️  Column already exists: {col_name}")
                    else:
                        raise
            else:
                print(f"   ✓ Column exists: {col_name}")
        
        print(f"\n📊 Objectives table: {added_count} columns added")
        
        # Check progress_updates table
        try:
            cursor.execute("PRAGMA table_info(progress_updates)")
            progress_cols = {row[1] for row in cursor.fetchall()}
            
            print("\n🔍 Checking progress_updates table...")
            
            # Columns to add
            progress_columns = [
                ("auto_tracked", "BOOLEAN DEFAULT FALSE"),
                ("ai_coaching_notes", "TEXT"),
            ]
            
            progress_added = 0
            for col_name, col_type in progress_columns:
                if col_name not in progress_cols:
                    try:
                        cursor.execute(f"ALTER TABLE progress_updates ADD COLUMN {col_name} {col_type}")
                        print(f"   ✅ Added column: {col_name}")
                        progress_added += 1
                    except sqlite3.OperationalError as e:
                        if "duplicate column" in str(e).lower():
                            print(f"   ⚠️  Column already exists: {col_name}")
                        else:
                            raise
                else:
                    print(f"   ✓ Column exists: {col_name}")
            
            print(f"\n📊 ProgressUpdate table: {progress_added} columns added")
        
        except sqlite3.OperationalError as e:
            if "no such table" in str(e).lower():
                print("\n⚠️  progress_updates table doesn't exist yet (will be created by SQLAlchemy)")
            else:
                raise
        
        # Commit changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("\n📝 New Features Available:")
        print("   ✓ Quarterly OKR planning (Q1-Q4)")
        print("   ✓ Year selection (2024-2027)")
        print("   ✓ AI-assisted OKR creation")
        print("   ✓ Auto-progress tracking")
        print("   ✓ AI coaching suggestions")
        print("\n🚀 Next steps:")
        print("   1. Restart backend: python main.py")
        print("   2. Install new dependencies: pip install -r requirements.txt")
        print("   3. Test new AI endpoints at /api/okrs/ai/*")
        
        return True
        
    except sqlite3.OperationalError as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    import sys
    success = run_migration()
    sys.exit(0 if success else 1)
