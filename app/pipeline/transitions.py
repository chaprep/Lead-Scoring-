from collections.abc import Iterable

from app.core.enums import ProspectState, StageName


class InvalidStateTransition(ValueError):
    """Raised when a prospect is asked to make an invalid workflow transition."""


ALLOWED_TRANSITIONS: dict[ProspectState, frozenset[ProspectState]] = {
    ProspectState.CREATED: frozenset({ProspectState.PHASE1_QUEUED}),
    ProspectState.PHASE1_QUEUED: frozenset({ProspectState.PHASE1_PROCESSING, ProspectState.FAILED}),
    ProspectState.PHASE1_PROCESSING: frozenset(
        {ProspectState.PHASE1_NORMALISING, ProspectState.FAILED}
    ),
    ProspectState.PHASE1_NORMALISING: frozenset({ProspectState.QUALIFYING, ProspectState.FAILED}),
    ProspectState.QUALIFYING: frozenset(
        {
            ProspectState.PASSED,
            ProspectState.HUMAN_REVIEW,
            ProspectState.REJECTED,
            ProspectState.FAILED,
        }
    ),
    ProspectState.PASSED: frozenset({ProspectState.PHASE2_QUEUED}),
    ProspectState.HUMAN_REVIEW: frozenset({ProspectState.PHASE2_QUEUED, ProspectState.REJECTED}),
    ProspectState.REJECTED: frozenset({ProspectState.PHASE2_QUEUED}),
    ProspectState.PHASE2_QUEUED: frozenset({ProspectState.PHASE2_PROCESSING, ProspectState.FAILED}),
    ProspectState.PHASE2_PROCESSING: frozenset(
        {ProspectState.PHASE2_NORMALISING, ProspectState.FAILED}
    ),
    ProspectState.PHASE2_NORMALISING: frozenset({ProspectState.PRIORITISING, ProspectState.FAILED}),
    ProspectState.PRIORITISING: frozenset(
        {ProspectState.CONTACT_ENRICHMENT_PENDING, ProspectState.COMPLETED, ProspectState.FAILED}
    ),
    ProspectState.CONTACT_ENRICHMENT_PENDING: frozenset(
        {ProspectState.COMPLETED, ProspectState.FAILED}
    ),
    ProspectState.COMPLETED: frozenset(),
    ProspectState.FAILED: frozenset(
        {
            ProspectState.PHASE1_QUEUED,
            ProspectState.PHASE2_QUEUED,
            ProspectState.PHASE1_NORMALISING,
            ProspectState.QUALIFYING,
            ProspectState.PHASE2_NORMALISING,
            ProspectState.PRIORITISING,
            ProspectState.CONTACT_ENRICHMENT_PENDING,
        }
    ),
}

RETRY_STATE_BY_STAGE: dict[StageName, ProspectState] = {
    StageName.PHASE1_ENRICHMENT: ProspectState.PHASE1_QUEUED,
    StageName.PHASE1_NORMALISATION: ProspectState.PHASE1_NORMALISING,
    StageName.QUALIFICATION: ProspectState.QUALIFYING,
    StageName.PHASE2_COMPANY_ENRICHMENT: ProspectState.PHASE2_QUEUED,
    StageName.PHASE2_CONTACT_ENRICHMENT: ProspectState.CONTACT_ENRICHMENT_PENDING,
    StageName.PHASE2_NORMALISATION: ProspectState.PHASE2_NORMALISING,
    StageName.PRIORITISATION: ProspectState.PRIORITISING,
}


def allowed_targets(state: ProspectState) -> Iterable[ProspectState]:
    return ALLOWED_TRANSITIONS[state]


def transition(prospect: object, target: ProspectState) -> None:
    current = getattr(prospect, "current_state")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidStateTransition(f"Cannot transition prospect from {current} to {target}.")
    setattr(prospect, "current_state", target)


def retry_target(stage: StageName) -> ProspectState:
    return RETRY_STATE_BY_STAGE[stage]
