"""add review event audit trail

Revision ID: 20261008_0002
Revises: 20261008_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "20261008_0002"
down_revision = "20261008_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_review_events_prospect_id", "review_events", ["prospect_id"])


def downgrade() -> None:
    op.drop_table("review_events")
