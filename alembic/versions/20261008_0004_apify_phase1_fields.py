"""add normalized Apify phase one fields

Revision ID: 20261008_0004
Revises: 20261008_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0004"
down_revision = "20261008_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column in (
        ("skills", sa.JSON()), ("professional_summary", sa.String()), ("education", sa.JSON()),
        ("open_to_work", sa.Boolean()), ("person_follower_count", sa.Integer()),
        ("company_tagline", sa.String()), ("company_specialities", sa.JSON()),
        ("company_founded_year", sa.Integer()), ("company_follower_count", sa.Integer()),
    ):
        op.add_column("phase1_normalized_data", sa.Column(name, column, nullable=True))


def downgrade() -> None:
    for name in ("company_follower_count", "company_founded_year", "company_specialities", "company_tagline", "person_follower_count", "open_to_work", "education", "professional_summary", "skills"):
        op.drop_column("phase1_normalized_data", name)
