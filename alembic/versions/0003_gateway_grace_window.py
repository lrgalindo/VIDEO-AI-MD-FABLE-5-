"""Add prev-hash grace window columns to edge_gateways (§8.7.0 lost-response mitigation).

Two columns store the previous refresh_token_hash after rotation and a short expiry
that limits the grace window to REFRESH_GRACE_SECONDS seconds. This lets a gateway
retry with its old token after a lost HTTP response without requiring manual reactivation.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-20
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE edge_gateways
          ADD COLUMN refresh_token_prev_hash        TEXT,
          ADD COLUMN refresh_token_prev_expires_at  TIMESTAMPTZ
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE edge_gateways
          DROP COLUMN IF EXISTS refresh_token_prev_hash,
          DROP COLUMN IF EXISTS refresh_token_prev_expires_at
    """)
