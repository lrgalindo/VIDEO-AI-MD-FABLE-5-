"""Edge Gateway auth columns (§8.7.0): refresh token, activation code, status expansion.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-20
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE edge_gateways
          ADD COLUMN activation_code_hash       TEXT,
          ADD COLUMN activation_code_expires_at TIMESTAMPTZ,
          ADD COLUMN refresh_token_hash         TEXT,
          ADD COLUMN refresh_token_expires_at   TIMESTAMPTZ,
          ADD COLUMN last_token_refresh_at      TIMESTAMPTZ,
          ADD COLUMN replaced_edge_gateway_id   TEXT REFERENCES edge_gateways(id)
    """)

    op.execute("""
        ALTER TABLE edge_gateways
          DROP CONSTRAINT IF EXISTS edge_gateways_status_check
    """)
    op.execute("""
        ALTER TABLE edge_gateways
          ADD CONSTRAINT edge_gateways_status_check
          CHECK (status IN ('online','offline','degraded','revoked','decommissioned'))
    """)

    op.execute("""
        CREATE UNIQUE INDEX idx_edge_gateways_refresh_hash
          ON edge_gateways(refresh_token_hash)
          WHERE refresh_token_hash IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_edge_gateways_refresh_hash")

    op.execute("""
        ALTER TABLE edge_gateways
          DROP CONSTRAINT IF EXISTS edge_gateways_status_check
    """)
    op.execute("""
        ALTER TABLE edge_gateways
          ADD CONSTRAINT edge_gateways_status_check
          CHECK (status IN ('online','offline','degraded'))
    """)

    op.execute("""
        ALTER TABLE edge_gateways
          DROP COLUMN IF EXISTS activation_code_hash,
          DROP COLUMN IF EXISTS activation_code_expires_at,
          DROP COLUMN IF EXISTS refresh_token_hash,
          DROP COLUMN IF EXISTS refresh_token_expires_at,
          DROP COLUMN IF EXISTS last_token_refresh_at,
          DROP COLUMN IF EXISTS replaced_edge_gateway_id
    """)
