"""store normalized SignalHire contact details

Revision ID: 20261010_0009
Revises: 20261009_0008
"""

from alembic import op
import sqlalchemy as sa


revision = "20261010_0009"
down_revision = "20261009_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contact_enrichment_requests",
        sa.Column("normalized_contact_data", sa.JSON(), nullable=True),
    )
    connection = op.get_bind()
    requests = sa.table(
        "contact_enrichment_requests",
        sa.column("id", sa.Uuid()),
        sa.column("raw_callback_payload", sa.JSON()),
        sa.column("normalized_contact_data", sa.JSON()),
    )
    rows = connection.execute(
        sa.select(requests.c.id, requests.c.raw_callback_payload).where(
            requests.c.raw_callback_payload.is_not(None)
        )
    )
    for request_id, payload in rows:
        normalized = _normalize_callback(payload)
        if normalized is not None:
            connection.execute(
                requests.update()
                .where(requests.c.id == request_id)
                .values(normalized_contact_data=normalized)
            )


def downgrade() -> None:
    op.drop_column("contact_enrichment_requests", "normalized_contact_data")


def _objects(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _normalize_callback(payload):
    if not isinstance(payload, dict):
        return None
    for result in _objects(payload.get("items")):
        candidate = result.get("candidate")
        if result.get("status") == "success" and isinstance(candidate, dict):
            current_experience = next(
                (item for item in _objects(candidate.get("experience")) if item.get("current") is True),
                None,
            )
            return {
                "provider_uid": candidate.get("uid"),
                "full_name": candidate.get("fullName"),
                "headline": candidate.get("headLine"),
                "summary": candidate.get("summary"),
                "experience_years": candidate.get("experienceYears"),
                "locations": _objects(candidate.get("locations")),
                "current_experience": current_experience,
                "contacts": _objects(candidate.get("contacts")),
                "social_profiles": _objects(candidate.get("social")),
                "addresses": _objects(candidate.get("addresses")),
                "names": _objects(candidate.get("names")),
            }
    return None
