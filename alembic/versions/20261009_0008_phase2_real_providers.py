"""add real Phase Two provider persistence

Revision ID: 20261009_0008
Revises: 20261008_0007
Create Date: 2026-10-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20261009_0008"
down_revision = "20261008_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires a committed transaction before a new enum value can
    # be used by application transactions, hence Alembic's autocommit block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE prospect_state ADD VALUE IF NOT EXISTS 'CONTACT_ENRICHMENT_PENDING'")

    op.add_column("priority_results", sa.Column("criteria_assessments", sa.JSON(), nullable=True))
    op.add_column("priority_results", sa.Column("model_identifier", sa.String(), nullable=True))
    op.add_column("priority_results", sa.Column("provider_identifier", sa.String(), nullable=True))
    op.add_column("priority_results", sa.Column("usage_metadata", sa.JSON(), nullable=True))
    op.execute("UPDATE priority_results SET criteria_assessments = '{}'::json WHERE criteria_assessments IS NULL")
    op.alter_column("priority_results", "criteria_assessments", nullable=False)

    op.create_table(
        "contact_enrichment_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("callback_token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("provider_request_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw_callback_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contact_enrichment_requests_prospect_id", "contact_enrichment_requests", ["prospect_id"])
    op.create_index("ix_contact_enrichment_requests_callback_token_hash", "contact_enrichment_requests", ["callback_token_hash"])


def downgrade() -> None:
    op.drop_index("ix_contact_enrichment_requests_callback_token_hash", table_name="contact_enrichment_requests")
    op.drop_index("ix_contact_enrichment_requests_prospect_id", table_name="contact_enrichment_requests")
    op.drop_table("contact_enrichment_requests")
    op.drop_column("priority_results", "usage_metadata")
    op.drop_column("priority_results", "provider_identifier")
    op.drop_column("priority_results", "model_identifier")
    op.drop_column("priority_results", "criteria_assessments")
    # PostgreSQL does not support removing enum values. The extra state remains
    # harmless after a downgrade.
