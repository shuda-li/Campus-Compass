import os
import requests
import json


def _get_proxies():
    from agent.proxy import get_proxy
    return get_proxy()


def search_web(query, max_results=3, search_depth="basic"):
    try:
        api_key = os.environ.get('TAVILY_API_KEY')
        if not api_key:
            return json.dumps({"ok": False, "answer": "", "results": []})

        response = requests.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            json={
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth
            },
            proxies=_get_proxies(),
            timeout=30
        )

        data = response.json()

        results = []
        for r in data.get('results', []):
            results.append({
                "title": r.get('title', ''),
                "url": r.get('url', ''),
                "snippet": r.get('content', '')
            })

        return json.dumps({
            "ok": True,
            "answer": data.get('answer', ''),
            "results": results
        })
    except Exception as e:
        print(f"[Tavily Error] {e}")
        return json.dumps({"ok": False, "answer": "", "results": []})


def is_available():
    return os.environ.get('TAVILY_API_KEY') is not None


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing Tavily...")
    result = search_web("校园活动策划", max_results=2)
    print(result)
