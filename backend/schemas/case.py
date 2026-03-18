from pydantic import BaseModel, Field
from datetime import datetime
from backend.models.case import CaseStatus

class CaseCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)

class CaseResponse(BaseModel):
    case_id: str
    client_name: str
    created_by: str
    created_at: datetime
    last_updated: datetime
    status: CaseStatus
    compact_summary: str | None = None

    model_config = {"from_attributes": True}
