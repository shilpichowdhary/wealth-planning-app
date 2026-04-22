from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    """Used for typed history responses. Reserved for GET /chat/history endpoint."""
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    case_id: str
    message: str = Field(min_length=1, max_length=2000)
    session_tavily_count: int = 0
    # KB-first permission gate:
    # - If KB has sufficient coverage, respond from KB (always).
    # - If KB is thin and allow_web is False and force_answer is False,
    #   the backend emits a `kb_insufficient` SSE event and short-circuits
    #   the stream — the client decides whether to resend with web allowed
    #   or to answer from whatever KB matched (+ general knowledge).
    allow_web: bool = False
    force_answer: bool = False
