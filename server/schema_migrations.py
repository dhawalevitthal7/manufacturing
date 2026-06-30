"""Small SQLite schema migrations for local development.

SQLAlchemy's ``create_all`` creates missing tables, but it does not add columns
to existing tables. These idempotent migrations keep older local SQLite
databases compatible with the current models.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
import json


TABLE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "objectives": [
        ("creation_approval_status", "VARCHAR(50) DEFAULT 'PENDING'"),
        ("creation_approved_by_id", "VARCHAR(255)"),
        ("creation_approved_at", "TIMESTAMP"),
        ("creation_primary_approved_by_id", "VARCHAR(255)"),
        ("creation_primary_approved_at", "TIMESTAMP"),
        ("creation_functional_approved_by_id", "VARCHAR(255)"),
        ("creation_functional_approved_at", "TIMESTAMP"),
        ("creation_approval_notes", "TEXT"),
        ("visibility_scope", "VARCHAR(50) DEFAULT 'STANDARD'"),
        ("allows_cascade", "BOOLEAN DEFAULT TRUE"),
        ("quarter", "VARCHAR(5)"),
        ("year", "INTEGER"),
        ("ai_generated", "BOOLEAN DEFAULT FALSE"),
        ("ai_metadata", "TEXT"),
        ("okr_status", "VARCHAR(50) DEFAULT 'DRAFT'"),
        ("rejection_reason", "TEXT"),
        ("pending_approver_user_id", "VARCHAR(255)"),
        ("pending_approver_role", "VARCHAR(50)"),
        ("kr_baseline_locked", "BOOLEAN DEFAULT FALSE"),
        ("functional_parent_obj_id", "VARCHAR(255) REFERENCES objectives(id) ON DELETE SET NULL"),
        ("region_id", "VARCHAR(255) REFERENCES org_nodes(id)"),
        ("function_area", "VARCHAR(50)"),
        ("function_node_id", "VARCHAR(255) REFERENCES org_nodes(id) ON DELETE SET NULL"),
        ("cascade_generation_status", "VARCHAR(50)"),
        ("ai_generated_from_objective_id", "VARCHAR(255) REFERENCES objectives(id) ON DELETE SET NULL"),
        ("ai_generation_version", "INTEGER DEFAULT 1"),
        ("ai_confidence", "FLOAT"),
        ("ai_generation_reason", "TEXT"),
        ("review_status", "VARCHAR(50)"),
        ("reviewed_by_id", "VARCHAR(255) REFERENCES users(id)"),
        ("reviewed_at", "TIMESTAMP"),
        ("submitted_for_parent_approval_at", "TIMESTAMP"),
        ("approved_by_parent_id", "VARCHAR(255) REFERENCES users(id)"),
        ("approved_at", "TIMESTAMP"),
        ("ai_prompt_tokens", "INTEGER"),
        ("ai_completion_tokens", "INTEGER"),
        ("ai_total_tokens", "INTEGER"),
    ],
    "key_results": [
        ("kpi_behavior", "VARCHAR(50) DEFAULT 'HIGHER_IS_BETTER'"),
        ("target_min", "FLOAT"),
        ("target_max", "FLOAT"),
        ("tolerance", "FLOAT"),
        ("allow_overachievement", "BOOLEAN DEFAULT FALSE"),
        ("normalized_progress", "FLOAT DEFAULT 0.0"),
        ("last_actual_value", "FLOAT"),
        ("last_calculated_at", "TIMESTAMP"),
        ("milestone_total", "INTEGER"),
        ("milestone_completed", "INTEGER"),
    ],
    "progress_updates": [
        ("validation_level", "VARCHAR(50)"),
        ("validation_chain", "TEXT"),
        ("next_approver_role", "VARCHAR(50)"),
        ("approved_at", "TIMESTAMP"),
        ("auto_tracked", "BOOLEAN DEFAULT FALSE"),
        ("ai_coaching_notes", "TEXT"),
        ("progress_source", "VARCHAR(50) DEFAULT 'MANUAL'"),
        ("is_manual_override", "BOOLEAN DEFAULT FALSE"),
    ],
    "progress_submissions": [
        # Newer approval workflow expects submissions to optionally tie to a parent objective.
        # Older local DBs may miss this column, so add it as nullable for compatibility.
        ("objective_id", "VARCHAR(255) REFERENCES objectives(id) ON DELETE SET NULL"),
    ],
    "users": [
        ("org_node_id", "VARCHAR(255)"),
    ],
    "user_permission_profiles": [
        ("scoped_region_id", "VARCHAR(255)"),
    ],
    "org_nodes": [
        ("functional_parent_id", "VARCHAR(255) REFERENCES org_nodes(id) ON DELETE SET NULL"),
    ],
    "continuous_checkins": [
        ("workflow_status", "VARCHAR(50) DEFAULT 'DRAFT'"),
        ("acknowledged_at", "TIMESTAMP"),
        ("acknowledged_by_user_id", "VARCHAR(36)"),
        ("performance_concern_flag", "BOOLEAN DEFAULT FALSE"),
        ("concern_notes", "TEXT"),
        ("escalated_at", "TIMESTAMP"),
        ("escalated_by_user_id", "VARCHAR(36)"),
        ("escalation_target_user_id", "VARCHAR(36)"),
        ("escalation_reason", "VARCHAR(50)"),
        ("resolved_at", "TIMESTAMP"),
        ("closed_at", "TIMESTAMP"),
    ],
    "employee_performance_reviews": [
        ("dept_head_reviewer_id", "VARCHAR(36)"),
        ("requires_dept_moderation", "BOOLEAN DEFAULT FALSE"),
        ("ai_review_status", "VARCHAR(50) DEFAULT 'NONE'"),
        ("ai_review_payload", "TEXT"),
        ("ai_review_generated_at", "TIMESTAMP"),
        ("ai_review_context_snapshot", "TEXT"),
        ("employee_performance_narrative", "TEXT"),
        ("promotion_recommendation", "VARCHAR(50)"),
        ("promotion_rationale", "TEXT"),
        ("shared_with_employee_at", "TIMESTAMP"),
        ("submitted_to_dept_head_at", "TIMESTAMP"),
    ],
    "checkin_comments": [
        ("parent_comment_id", "VARCHAR(36)"),
        ("is_system_event", "BOOLEAN DEFAULT FALSE"),
    ],
}


def apply_sqlite_schema_migrations(engine: Engine) -> None:
    """Add columns required by newer models to existing SQLite tables."""

    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        for table_name, columns in TABLE_COLUMNS.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }

            for column_name, column_definition in columns:
                if column_name in existing_columns:
                    continue

                connection.execute(
                    text(
                        f"ALTER TABLE {table_name} "
                        f"ADD COLUMN {column_name} {column_definition}"
                    )
                )
    
    # After all column additions, backfill org_nodes hierarchy
    _backfill_org_nodes(engine)
    _ensure_approval_steps_table(engine)
    _backfill_key_results(engine)


def _backfill_key_results(engine: Engine) -> None:
    """Ensure existing KRs have a valid kpi_behavior."""
    if engine.dialect.name != "sqlite":
        return
    
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE key_results "
                "SET kpi_behavior = 'HIGHER_IS_BETTER' "
                "WHERE kpi_behavior IS NULL"
            )
        )


def _ensure_approval_steps_table(engine: Engine) -> None:
    """Create approval_steps table on older SQLite DBs (create_all skips existing DBs)."""
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    if "approval_steps" in inspector.get_table_names():
        return

    with engine.begin() as connection:
        connection.execute(
            text("""
                CREATE TABLE IF NOT EXISTS approval_steps (
                    id VARCHAR(255) PRIMARY KEY,
                    org_id VARCHAR(255) NOT NULL REFERENCES organizations(id),
                    subject_type VARCHAR(50) NOT NULL,
                    subject_id VARCHAR(255) NOT NULL,
                    sequence_order INTEGER NOT NULL DEFAULT 1,
                    approval_type VARCHAR(50) NOT NULL,
                    approver_id VARCHAR(255) REFERENCES users(id),
                    approver_role VARCHAR(50),
                    status VARCHAR(50) DEFAULT 'PENDING',
                    decided_at TIMESTAMP,
                    comment TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    CONSTRAINT uq_approval_step_seq UNIQUE (subject_type, subject_id, sequence_order)
                )
            """)
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_approval_steps_org ON approval_steps(org_id)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_approval_steps_subject "
                "ON approval_steps(subject_type, subject_id)"
            )
        )


def _backfill_org_nodes(engine: Engine) -> None:
    """
    Backfill org_nodes table with existing Plant/Department/Team hierarchy.
    
    Creates OrgNode entries for:
    1. Organization roots (depth=0)
    2. Plants (depth=1, under org root)
    3. Departments (depth=2, under plants)
    4. Teams (depth=3, under departments, with head_user_id from Team.lead_id)
    5. Populates User.org_node_id for all users
    
    Idempotent: safe to run multiple times. Uses INSERT OR IGNORE pattern.
    """
    if engine.dialect.name != "sqlite":
        return
    
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    
    # Only run if org_nodes table exists (created by Base.metadata.create_all)
    if "org_nodes" not in existing_tables:
        return
    
    with engine.begin() as connection:
        try:
            print("[Migration] org_nodes: removing orphan PLANT/DEPARTMENT/TEAM rows (id not in legacy tables)...")
            connection.execute(
                text("""
                    DELETE FROM org_nodes WHERE node_type = 'TEAM'
                      AND id NOT IN (SELECT id FROM teams)
                """)
            )
            connection.execute(
                text("""
                    DELETE FROM org_nodes WHERE node_type = 'DEPARTMENT'
                      AND id NOT IN (SELECT id FROM departments)
                """)
            )
            connection.execute(
                text("""
                    DELETE FROM org_nodes WHERE node_type = 'PLANT'
                      AND id NOT IN (SELECT id FROM plants)
                """)
            )

            # 1. Insert org root nodes (one per organization) — id = organizations.id
            print("[Migration] Creating organization root nodes...")
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO org_nodes 
                        (id, org_id, parent_id, node_type, name, path, depth, node_metadata, is_active, created_at, updated_at)
                    SELECT 
                        id,
                        id AS org_id,
                        NULL AS parent_id,
                        'ORGANIZATION' AS node_type,
                        name,
                        id AS path,
                        (LENGTH(id) - LENGTH(REPLACE(id, '.', ''))) AS depth,
                        '{}' AS node_metadata,
                        1 AS is_active,
                        datetime('now') AS created_at,
                        datetime('now') AS updated_at
                    FROM organizations
                """)
            )
            
            # 2. Insert plant nodes (under org roots)
            print("[Migration] Creating plant nodes...")
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO org_nodes 
                        (id, org_id, parent_id, node_type, name, code, path, depth, node_metadata, is_active, created_at, updated_at)
                    SELECT 
                        id,
                        org_id,
                        org_id AS parent_id,
                        'PLANT' AS node_type,
                        name,
                        code,
                        org_id || '.' || id AS path,
                        (LENGTH(org_id || '.' || id) - LENGTH(REPLACE(org_id || '.' || id, '.', ''))) AS depth,
                        '{}' AS node_metadata,
                        is_active,
                        created_at,
                        COALESCE(created_at, datetime('now')) AS updated_at
                    FROM plants
                """)
            )
            
            # 3. Insert department nodes (under plants)
            print("[Migration] Creating department nodes...")
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO org_nodes 
                        (id, org_id, parent_id, node_type, name, code, path, depth, node_metadata, is_active, created_at, updated_at)
                    SELECT 
                        d.id,
                        d.org_id,
                        d.plant_id AS parent_id,
                        'DEPARTMENT' AS node_type,
                        d.name,
                        NULL AS code,
                        d.org_id || '.' || d.plant_id || '.' || d.id AS path,
                        (LENGTH(d.org_id || '.' || d.plant_id || '.' || d.id) - LENGTH(REPLACE(d.org_id || '.' || d.plant_id || '.' || d.id, '.', ''))) AS depth,
                        json('{"dept_type":"' || COALESCE(d.dept_type, '') || '"}') AS node_metadata,
                        d.is_active,
                        d.created_at,
                        COALESCE(d.created_at, datetime('now')) AS updated_at
                    FROM departments d
                """)
            )
            
            # 4. Insert team nodes — path includes plant_id (join departments)
            print("[Migration] Creating team nodes...")
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO org_nodes 
                        (id, org_id, parent_id, node_type, name, head_user_id, path, depth, node_metadata, is_active, created_at, updated_at)
                    SELECT 
                        t.id,
                        t.org_id,
                        t.department_id AS parent_id,
                        'TEAM' AS node_type,
                        t.name,
                        t.lead_id AS head_user_id,
                        t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id AS path,
                        (LENGTH(t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id)
                         - LENGTH(REPLACE(t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id, '.', ''))) AS depth,
                        '{}' AS node_metadata,
                        t.is_active,
                        t.created_at,
                        COALESCE(t.created_at, datetime('now')) AS updated_at
                    FROM teams t
                    INNER JOIN departments d ON d.id = t.department_id
                """)
            )

            # Repair TEAM paths if rows pre-existed with old 3-segment paths (INSERT OR IGNORE)
            connection.execute(
                text("""
                    UPDATE org_nodes SET
                        path = (
                            SELECT t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id
                            FROM teams t
                            INNER JOIN departments d ON d.id = t.department_id
                            WHERE t.id = org_nodes.id
                        ),
                        depth = (
                            SELECT LENGTH(t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id)
                                 - LENGTH(REPLACE(t.org_id || '.' || d.plant_id || '.' || t.department_id || '.' || t.id, '.', ''))
                            FROM teams t
                            INNER JOIN departments d ON d.id = t.department_id
                            WHERE t.id = org_nodes.id
                        )
                    WHERE node_type = 'TEAM' AND id IN (SELECT id FROM teams)
                """)
            )

            # Align depth column with path for all org_nodes (idempotent repair)
            connection.execute(
                text("""
                    UPDATE org_nodes SET depth = LENGTH(path) - LENGTH(REPLACE(path, '.', ''))
                """)
            )
            
            # 5. Populate User.org_node_id (users assigned to deepest available node)
            print("[Migration] Assigning users to org nodes...")
            
            # First, assign team members to their team nodes
            connection.execute(
                text("""
                    UPDATE users
                    SET org_node_id = (
                        SELECT id FROM org_nodes 
                        WHERE org_nodes.id = users.team_id 
                            AND org_nodes.node_type = 'TEAM'
                        LIMIT 1
                    )
                    WHERE team_id IS NOT NULL AND org_node_id IS NULL
                """)
            )
            
            # Then, assign department members (without team) to their department nodes
            connection.execute(
                text("""
                    UPDATE users
                    SET org_node_id = (
                        SELECT id FROM org_nodes 
                        WHERE org_nodes.id = users.department_id 
                            AND org_nodes.node_type = 'DEPARTMENT'
                        LIMIT 1
                    )
                    WHERE department_id IS NOT NULL AND team_id IS NULL AND org_node_id IS NULL
                """)
            )
            
            # Then, assign plant members (without dept) to their plant nodes
            connection.execute(
                text("""
                    UPDATE users
                    SET org_node_id = (
                        SELECT id FROM org_nodes 
                        WHERE org_nodes.id = users.plant_id 
                            AND org_nodes.node_type = 'PLANT'
                        LIMIT 1
                    )
                    WHERE plant_id IS NOT NULL AND department_id IS NULL AND org_node_id IS NULL
                """)
            )
            
            # Finally, assign remaining users (org admins, etc.) to org root
            connection.execute(
                text("""
                    UPDATE users
                    SET org_node_id = (
                        SELECT id FROM org_nodes 
                        WHERE org_nodes.org_id = users.org_id 
                            AND org_nodes.node_type = 'ORGANIZATION'
                        LIMIT 1
                    )
                    WHERE plant_id IS NULL AND org_node_id IS NULL
                """)
            )
            
            print("[Migration] org_nodes backfill complete")
        
        except Exception as e:
            print(f"[Migration] org_nodes backfill error (non-critical): {e}")
            # Do not raise — this is a non-critical backfill that may fail on first run
            # before org_nodes table has foreign key relationships fully established
