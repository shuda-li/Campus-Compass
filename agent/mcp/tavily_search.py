import json
from config import TAVILY_API_KEY


def search_web(query: str, max_results: int = 3, include_answer: bool = True) -> str:
    if not TAVILY_API_KEY:
        return json.dumps({"ok": False, "error": "TAVILY_API_KEY 未配置"}, ensure_ascii=False)

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        result = client.search(query, max_results=max_results, include_answer=include_answer)

        answer = result.get("answer", "")
        results = result.get("results", [])

        output = {"ok": True, "answer": answer, "results": []}
        for r in results:
            output["results"].append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("content", "") or "")[:300],
            })

        return json.dumps(output, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)


def search_activity_trends(topic: str) -> str:
    query = f"校园活动策划 {topic} 创意 流程"
    return search_web(query, max_results=3, include_answer=True)


def is_available() -> bool:
    return bool(TAVILY_API_KEY)
