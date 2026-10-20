"""create initial lead scoring schema

Revision ID: 20261008_0001
Revises:
Create Date: 2026-10-08 11:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    batch_status = sa.Enum("ACTIVE", "COMPLETED", name="batch_status")
    prospect_state = sa.Enum(
        "CREATED", "PHASE1_QUEUED", "PHASE1_PROCESSING", "PHASE1_NORMALISING", "QUALIFYING",
        "PASSED", "HUMAN_REVIEW", "REJECTED", "PHASE2_QUEUED", "PHASE2_PROCESSING",
        "PHASE2_NORMALISING", "PRIORITISING", "COMPLETED", "FAILED", name="prospect_state"
    )
    stage_name = sa.Enum(
        "PHASE1_ENRICHMENT", "PHASE1_NORMALISATION", "QUALIFICATION", "PHASE2_COMPANY_ENRICHMENT",
        "PHASE2_CONTACT_ENRICHMENT", "PHASE2_NORMALISATION", "PRIORITISATION", name="stage_name"
    )
    stage_status = sa.Enum("QUEUED", "PROCESSING", "COMPLETED", "FAILED", name="stage_status")
    qualification_decision = sa.Enum("PASS", "HUMAN_REVIEW", "REJECTED", name="qualification_decision")
    priority_level = sa.Enum("P1", "P2", "P3", name="priority_level")

    op.create_table("batches", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("status", batch_status, nullable=False), sa.Column("total_prospects", sa.Integer(), nullable=False), sa.Column("created_by_optional", sa.String(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_table("icp_snapshots", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("company_size_min", sa.Integer(), nullable=True), sa.Column("company_size_max", sa.Integer(), nullable=True), sa.Column("industries", sa.JSON(), nullable=False), sa.Column("company_types", sa.JSON(), nullable=False), sa.Column("departments", sa.JSON(), nullable=False), sa.Column("seniorities", sa.JSON(), nullable=False), sa.Column("geographies", sa.JSON(), nullable=False), sa.Column("exclusions", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_table("prospects", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("batches.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("linkedin_url", sa.String(), nullable=False), sa.Column("current_state", prospect_state, nullable=False), sa.Column("final_priority", priority_level, nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_prospects_batch_id", "prospects", ["batch_id"])
    op.create_index("ix_prospects_current_state", "prospects", ["current_state"])
    op.create_index("ix_prospects_final_priority", "prospects", ["final_priority"])
    op.create_table("stage_runs", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False), sa.Column("stage", stage_name, nullable=False), sa.Column("status", stage_status, nullable=False), sa.Column("provider", sa.String(), nullable=True), sa.Column("attempt_number", sa.Integer(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True), sa.Column("error_type", sa.String(), nullable=True), sa.Column("error_message", sa.String(), nullable=True))
    op.create_index("ix_stage_runs_prospect_id", "stage_runs", ["prospect_id"])
    op.create_table("raw_provider_responses", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False), sa.Column("phase", sa.String(16), nullable=False), sa.Column("provider", sa.String(), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_raw_provider_responses_prospect_id", "raw_provider_responses", ["prospect_id"])
    op.create_table("phase1_normalized_data", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("name", sa.String(), nullable=True), sa.Column("linkedin_url", sa.String(), nullable=True), sa.Column("job_title", sa.String(), nullable=True), sa.Column("department", sa.String(), nullable=True), sa.Column("seniority", sa.String(), nullable=True), sa.Column("location", sa.String(), nullable=True), sa.Column("current_company", sa.String(), nullable=True), sa.Column("company_name", sa.String(), nullable=True), sa.Column("company_domain", sa.String(), nullable=True), sa.Column("industry", sa.String(), nullable=True), sa.Column("company_type", sa.String(), nullable=True), sa.Column("employee_count", sa.Integer(), nullable=True), sa.Column("hq_location", sa.String(), nullable=True), sa.Column("company_description", sa.String(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_phase1_normalized_data_prospect_id", "phase1_normalized_data", ["prospect_id"])
    op.create_table("qualification_results", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("decision", qualification_decision, nullable=False), sa.Column("person_fit", sa.String(), nullable=True), sa.Column("company_fit", sa.String(), nullable=True), sa.Column("exclusion_flags", sa.JSON(), nullable=False), sa.Column("reason", sa.String(), nullable=False), sa.Column("confidence", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_qualification_results_prospect_id", "qualification_results", ["prospect_id"])
    op.create_table("phase2_normalized_data", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("signals", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_phase2_normalized_data_prospect_id", "phase2_normalized_data", ["prospect_id"])
    op.create_table("priority_results", sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("prospect_id", sa.Uuid(), sa.ForeignKey("prospects.id", ondelete="CASCADE"), nullable=False, unique=True), sa.Column("priority", priority_level, nullable=False), sa.Column("confidence", sa.String(), nullable=False), sa.Column("positive_signals", sa.JSON(), nullable=False), sa.Column("negative_or_weak_signals", sa.JSON(), nullable=False), sa.Column("reason", sa.String(), nullable=False), sa.Column("summary", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.create_index("ix_priority_results_prospect_id", "priority_results", ["prospect_id"])


def downgrade() -> None:
    for table in ("priority_results", "phase2_normalized_data", "qualification_results", "phase1_normalized_data", "raw_provider_responses", "stage_runs", "prospects", "icp_snapshots", "batches"):
        op.drop_table(table)
    for enum_name in ("priority_level", "qualification_decision", "stage_status", "stage_name", "prospect_state", "batch_status"):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
