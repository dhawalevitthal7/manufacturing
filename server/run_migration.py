#!/usr/bin/env python3
"""
Database Migration Script
Adds missing columns for OKR Hierarchy Workflow to existing database
Run this ONCE to update your database schema
"""

import sqlite3
import sys
from pathlib import Path

# Determine database path
DB_PATH = Path(__file__).parent.parent / "manufacturing_os.db"

def run_migration():
    """Run database migration to add new columns"""
    
    if not DB_PATH.exists():
        print(f"❌ ERROR: Database not found at {DB_PATH}")
        print("Please ensure your database file exists before running migration")
        return False
    
    print(f"📦 Database: {DB_PATH}")
    print("=" * 60)
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Get existing columns for objectives table
        cursor.execute("PRAGMA table_info(objectives)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        print("🔍 Checking objectives table...")
        
        # Columns to add to objectives table
        objectives_columns = [
            ("creation_approval_status", "VARCHAR(50) DEFAULT 'PENDING'"),
            ("creation_approved_by_id", "VARCHAR(255)"),
            ("creation_approved_at", "TIMESTAMP"),
            ("creation_approval_notes", "TEXT"),
            ("visibility_scope", "VARCHAR(50) DEFAULT 'STANDARD'"),
            ("allows_cascade", "BOOLEAN DEFAULT TRUE"),
        ]
        
        # Add missing columns to objectives
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
        
        # Get existing columns for progress_updates table
        try:
            cursor.execute("PRAGMA table_info(progress_updates)")
            progress_cols = {row[1] for row in cursor.fetchall()}
            
            print("\n🔍 Checking progress_updates table...")
            
            # Columns to add to progress_updates table
            progress_columns = [
                ("validation_level", "VARCHAR(50)"),
                ("validation_chain", "TEXT"),
                ("next_approver_role", "VARCHAR(50)"),
                ("approved_at", "TIMESTAMP"),
            ]
            
            # Add missing columns to progress_updates
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
            # progress_updates table might not exist yet, which is OK
            if "no such table" in str(e).lower():
                print("\n⚠️  progress_updates table doesn't exist yet (will be created by SQLAlchemy)")
            else:
                raise
        
        # Commit changes
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Restart your backend server")
        print("   2. Test the API endpoints")
        print("\n💡 TIP: If you get errors, try deleting the .db file and letting")
        print("   SQLAlchemy recreate it from scratch with all tables.")
        
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
    success = run_migration()
    sys.exit(0 if success else 1)
