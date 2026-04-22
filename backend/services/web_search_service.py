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
        self._available = True

    async def _get_client(self):
        from tavily import TavilyClient
        from backend.services.settings_service import get_setting
        api_key = await get_setting("tavily_api_key")
        if not api_key or api_key == "placeholder":
            return None
        return TavilyClient(api_key=api_key)

    async def search(self, query: str, max_results: int = 3) -> list[WebResult]:
        try:
            client = await self._get_client()
            if not client:
                return []
            response = client.search(
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
