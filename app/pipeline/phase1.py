from app.core.enums import StageName
from app.pipeline.synchronous import process_group


def process_phase1(prospect_id, session=None):
    return process_group(
        prospect_id,
        {StageName.PHASE1_ENRICHMENT, StageName.PHASE1_NORMALISATION, StageName.QUALIFICATION},
        session,
    )
