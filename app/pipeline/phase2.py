from app.core.enums import StageName
from app.pipeline.synchronous import process_group


def process_phase2(prospect_id, session=None):
    return process_group(
        prospect_id, {StageName.PHASE2_COMPANY_ENRICHMENT, StageName.PHASE2_NORMALISATION}, session
    )
