"""store provider current role without seniority inference

Revision ID: 20261008_0005
Revises: 20261008_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0005"
down_revision = "20261008_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phase1_normalized_data", sa.Column("current_role", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("phase1_normalized_data", "current_role")
