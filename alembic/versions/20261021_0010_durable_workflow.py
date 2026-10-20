"""Durable stage ownership, contact attempts and receipts; reconcile legacy work.

Revision ID: 20261021_0010
Revises: 20261010_0009
"""

from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = "20261021_0010"
down_revision = "20261010_0009"
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        sa.Column(
            "due_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("publication_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("publication_error", sa.String()),
        sa.Column("owner", sa.String()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("execution_deadline", sa.DateTime(timezone=True)),
        sa.Column(
            "external_call_status", sa.String(), nullable=False, server_default="NOT_STARTED"
        ),
        sa.Column("failure_code", sa.String()),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "retry_requires_confirmation", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("automatic_retries", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checkpoint", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reservations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True)),
    ]
    for column in columns:
        op.add_column("stage_runs", column)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table in (
        "phase1_normalized_data",
        "phase2_normalized_data",
        "qualification_results",
        "priority_results",
    ):
        for index in inspector.get_indexes(table):
            if index["column_names"] == ["prospect_id"] and not index["unique"]:
                op.drop_index(index["name"], table_name=table)
    for constraint in inspector.get_unique_constraints("contact_enrichment_requests"):
        if constraint["column_names"] == ["prospect_id"]:
            op.drop_constraint(constraint["name"], "contact_enrichment_requests", type_="unique")
    op.drop_index(
        "ix_contact_enrichment_requests_callback_token_hash",
        table_name="contact_enrichment_requests",
    )
    op.add_column(
        "contact_enrichment_requests",
        sa.Column("stage_run_id", sa.Uuid(), sa.ForeignKey("stage_runs.id"), unique=True),
    )
    op.add_column("contact_enrichment_requests", sa.Column("deadline", sa.DateTime(timezone=True)))
    op.add_column("contact_enrichment_requests", sa.Column("outcome", sa.String()))
    op.create_table(
        "contact_callback_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "request_id",
            sa.Uuid(),
            sa.ForeignKey("contact_enrichment_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_request_id", sa.String()),
        sa.Column("payload_hash", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_error", sa.String()),
        sa.UniqueConstraint("request_id", "payload_hash"),
    )
    op.create_index(
        "ix_contact_callback_receipts_request_id", "contact_callback_receipts", ["request_id"]
    )
    op.create_table(
        "coordinator_heartbeat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Preserve historical null completion timestamps; close ambiguous active legacy rows.
    conn.execute(
        sa.text("""UPDATE stage_runs SET status='FAILED', failure_code='LEGACY_OUTCOME_UNKNOWN',
        retryable=true, retry_requires_confirmation=true, error_type='LegacyRecovery',
        error_message='Legacy in-flight work requires manual recovery; retrying may duplicate charges.'
        WHERE status IN ('QUEUED','PROCESSING')""")
    )
    conn.execute(
        sa.text("""UPDATE stage_runs SET retryable=true,
        retry_requires_confirmation=true, failure_code='LEGACY_OUTCOME_UNKNOWN'
        WHERE status='FAILED' AND failure_code IS NULL""")
    )
    # Backfill contact attempt relationships deterministically, preserving received data.
    contacts = (
        conn.execute(
            sa.text(
                "SELECT id, prospect_id, created_at, status FROM contact_enrichment_requests ORDER BY created_at,id"
            )
        )
        .mappings()
        .all()
    )
    for contact in contacts:
        stage_id = conn.execute(
            sa.text("""SELECT id FROM stage_runs WHERE prospect_id=:pid
            AND stage='PHASE2_CONTACT_ENRICHMENT' ORDER BY started_at DESC,id DESC LIMIT 1"""),
            {"pid": contact["prospect_id"]},
        ).scalar()
        if stage_id is None:
            stage_id = uuid4()
            conn.execute(
                sa.text("""INSERT INTO stage_runs(id,prospect_id,stage,status,attempt_number,started_at,provider,
                failure_code,retryable,retry_requires_confirmation) VALUES(:id,:pid,'PHASE2_CONTACT_ENRICHMENT',
                :status,1,:created,'signalhire',:code,true,true)"""),
                {
                    "id": stage_id,
                    "pid": contact["prospect_id"],
                    "created": contact["created_at"],
                    "status": "COMPLETED" if contact["status"] == "RECEIVED" else "FAILED",
                    "code": None if contact["status"] == "RECEIVED" else "LEGACY_OUTCOME_UNKNOWN",
                },
            )
        conn.execute(
            sa.text("UPDATE contact_enrichment_requests SET stage_run_id=:sid WHERE id=:id"),
            {"sid": stage_id, "id": contact["id"]},
        )
    # Only legacy work proven queued may be automatically scheduled.
    for p in (
        conn.execute(
            sa.text(
                "SELECT id,current_state FROM prospects WHERE current_state NOT IN ('COMPLETED','REJECTED','HUMAN_REVIEW','FAILED')"
            )
        )
        .mappings()
        .all()
    ):
        if p["current_state"] in {"CREATED", "PHASE1_QUEUED", "PHASE2_QUEUED"}:
            stage = (
                "PHASE2_COMPANY_ENRICHMENT"
                if p["current_state"] == "PHASE2_QUEUED"
                else "PHASE1_ENRICHMENT"
            )
            attempt = conn.execute(
                sa.text(
                    "SELECT coalesce(max(attempt_number),0)+1 FROM stage_runs WHERE prospect_id=:pid AND stage=:stage"
                ),
                {"pid": p["id"], "stage": stage},
            ).scalar()
            conn.execute(
                sa.text(
                    "INSERT INTO stage_runs(id,prospect_id,stage,status,attempt_number) VALUES(:id,:pid,:stage,'QUEUED',:attempt)"
                ),
                {"id": uuid4(), "pid": p["id"], "stage": stage, "attempt": attempt},
            )
        else:
            stages = {
                "PHASE1_PROCESSING": "PHASE1_ENRICHMENT",
                "PHASE1_NORMALISING": "PHASE1_NORMALISATION",
                "QUALIFYING": "QUALIFICATION",
                "PASSED": "PHASE2_COMPANY_ENRICHMENT",
                "PHASE2_PROCESSING": "PHASE2_COMPANY_ENRICHMENT",
                "PHASE2_NORMALISING": "PHASE2_NORMALISATION",
                "PRIORITISING": "PRIORITISATION",
                "CONTACT_ENRICHMENT_PENDING": "PHASE2_CONTACT_ENRICHMENT",
            }
            stage = stages[p["current_state"]]
            failed = conn.execute(
                sa.text(
                    "SELECT id FROM stage_runs WHERE prospect_id=:pid AND stage=:stage AND failure_code='LEGACY_OUTCOME_UNKNOWN' LIMIT 1"
                ),
                {"pid": p["id"], "stage": stage},
            ).scalar()
            if not failed:
                attempt = conn.execute(
                    sa.text(
                        "SELECT coalesce(max(attempt_number),0)+1 FROM stage_runs WHERE prospect_id=:pid AND stage=:stage"
                    ),
                    {"pid": p["id"], "stage": stage},
                ).scalar()
                conn.execute(
                    sa.text("""INSERT INTO stage_runs(id,prospect_id,stage,status,attempt_number,
                    failure_code,retryable,retry_requires_confirmation,error_type,error_message)
                    VALUES(:id,:pid,:stage,'FAILED',:attempt,'LEGACY_OUTCOME_UNKNOWN',true,true,'LegacyRecovery',
                    'Legacy in-flight work requires manual recovery; retrying may duplicate charges.')"""),
                    {"id": uuid4(), "pid": p["id"], "stage": stage, "attempt": attempt},
                )
            conn.execute(
                sa.text("UPDATE prospects SET current_state='FAILED' WHERE id=:id"), {"id": p["id"]}
            )
    op.create_index(
        "uq_stage_runs_active_prospect",
        "stage_runs",
        ["prospect_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED','PROCESSING')"),
    )
    conn.execute(
        sa.text("""UPDATE batches b SET status=CASE WHEN EXISTS(SELECT 1 FROM prospects p WHERE p.batch_id=b.id)
        AND NOT EXISTS(SELECT 1 FROM prospects p WHERE p.batch_id=b.id AND p.current_state NOT IN ('COMPLETED','REJECTED','FAILED'))
        THEN 'COMPLETED'::batch_status ELSE 'ACTIVE'::batch_status END""")
    )


def downgrade():
    raise RuntimeError(
        "Restore the verified pre-repair backup with the previous application image; contact attempt history cannot be flattened safely."
    )
