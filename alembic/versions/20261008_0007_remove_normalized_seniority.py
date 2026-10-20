"""remove normalized seniority

Revision ID: 20261008_0007
Revises: 20261008_0006
"""
from alembic import op

revision = "20261008_0007"
down_revision = "20261008_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("phase1_normalized_data", "seniority")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("phase1_normalized_data", sa.Column("seniority", sa.String(), nullable=True))
