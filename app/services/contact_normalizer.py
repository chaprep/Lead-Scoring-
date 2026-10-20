"""Normalize the contact-bearing portion of SignalHire callbacks for internal use."""

from typing import Any


def _objects(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def normalize_signalhire_callback(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return all contact methods and related contact channels from one successful result.

    Raw provider payload remains attached to the enrichment request for audit/debugging.
    This representation is deliberately limited to profile and contact material needed
    by an authorized internal user.
    """
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
