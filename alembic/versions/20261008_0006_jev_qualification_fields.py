"""add Jev qualification evidence fields

Revision ID: 20261008_0006
Revises: 20261008_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0006"
down_revision = "20261008_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column in (
        ("assessments", sa.JSON()), ("overall_fit_band", sa.String()), ("confidence_band", sa.String()),
        ("model_identifier", sa.String()), ("provider_identifier", sa.String()), ("usage_metadata", sa.JSON()),
    ):
        op.add_column("qualification_results", sa.Column(name, column, nullable=True))


def downgrade() -> None:
    for name in ("usage_metadata", "provider_identifier", "model_identifier", "confidence_band", "overall_fit_band", "assessments"):
        op.drop_column("qualification_results", name)
