"""add phase one employee size ranges

Revision ID: 20261008_0003
Revises: 20261008_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0003"
down_revision = "20261008_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phase1_normalized_data", sa.Column("employee_count_min", sa.Integer(), nullable=True))
    op.add_column("phase1_normalized_data", sa.Column("employee_count_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("phase1_normalized_data", "employee_count_max")
    op.drop_column("phase1_normalized_data", "employee_count_min")
