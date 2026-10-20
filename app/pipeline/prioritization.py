from app.core.enums import StageName
from app.pipeline.synchronous import process_group


def process_prioritization(prospect_id, session=None):
    return process_group(prospect_id, {StageName.PRIORITISATION}, session)
