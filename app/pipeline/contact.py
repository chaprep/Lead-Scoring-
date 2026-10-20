from app.core.enums import StageName
from app.pipeline.synchronous import process_group


def process_contact_enrichment(prospect_id, callback_token=None, session=None):
    return process_group(prospect_id, {StageName.PHASE2_CONTACT_ENRICHMENT}, session)
