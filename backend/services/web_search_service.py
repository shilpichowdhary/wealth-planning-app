from dataclasses import dataclass
from datetime import datetime

@dataclass
class WebResult:
    text: str
    url: str
    title: str
    retrieved_at: str

class WebSearchService:
    def __init__(self):
        try:
            from tavily import TavilyClient
            from backend.config import settings
            self.client = TavilyClient(api_key=settings.tavily_api_key)
            self._available = True
        except Exception:
            self._available = False

    async def search(self, query: str, max_results: int = 3) -> list[WebResult]:
        if not self._available:
            return []
        try:
            response = self.client.search(
                query=f"wealth planning tax law {query}",
                search_depth="advanced",
                max_results=max_results,
            )
            return [
                WebResult(
                    text=r.get("content", ""),
                    url=r.get("url", ""),
                    title=r.get("title", ""),
                    retrieved_at=datetime.utcnow().strftime("%d %b %Y"),
                )
                for r in response.get("results", [])
            ]
        except Exception:
            return []
