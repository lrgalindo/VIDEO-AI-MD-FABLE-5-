"""Add password_hash column to platform_admins (SuperAdmin login endpoint).

SDD §3.1 decision 11b — POST /v1/superadmin/login requires credentials
stored in the DB.  Uses bcrypt (cost factor 12).

Revision ID: 0010
Revises: 0009
"""

revision = "0010"
down_revision = "0009"

_SQL_UP = """
ALTER TABLE platform_admins ADD COLUMN password_hash TEXT NOT NULL DEFAULT '';
-- Remove the synthetic default immediately so new rows must supply a hash.
ALTER TABLE platform_admins ALTER COLUMN password_hash DROP DEFAULT;
"""

_SQL_DOWN = """
ALTER TABLE platform_admins DROP COLUMN IF EXISTS password_hash;
"""


def upgrade(conn):
    with conn.cursor() as cur:
        cur.execute(_SQL_UP)
    conn.commit()


def downgrade(conn):
    with conn.cursor() as cur:
        cur.execute(_SQL_DOWN)
    conn.commit()
