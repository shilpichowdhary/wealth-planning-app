from pydantic import BaseModel
from datetime import datetime
from backend.models.case import CaseStatus

class CaseCreate(BaseModel):
    client_name: str

class CaseResponse(BaseModel):
    case_id: str
    client_name: str
    created_by: str
    created_at: datetime
    last_updated: datetime
    status: CaseStatus
    compact_summary: str | None = None

    model_config = {"from_attributes": True}
