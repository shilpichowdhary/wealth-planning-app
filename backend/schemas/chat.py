from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    case_id: str
    message: str = Field(min_length=1, max_length=2000)
    session_tavily_count: int = 0
