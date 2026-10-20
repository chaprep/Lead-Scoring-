from pydantic import BaseModel


class BulkReviewResponse(BaseModel):
    updated_count: int
