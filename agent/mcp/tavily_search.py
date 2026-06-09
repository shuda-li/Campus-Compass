"""
知识搜索 — Tavily 实时搜索 + DeepSeek 知识兜底

策略：先调用 Tavily Search API 获取实时联网结果；
若网络不通/超时/Key无效/返回异常，则降级到 DeepSeek LLM 知识兜底。
返回格式统一，附加 source 字段标明数据来源。
"""
import json
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

# ── Tavily API 配置 ──
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT = 8  # 秒，超时立刻降级


def _search_via_tavily(query: str, max_results: int = 3, search_depth: str = "basic") -> dict:
    """调用 Tavily Search API 执行真实联网搜索。成功返回 dict，失败抛异常。"""
    import requests

    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
    }

    resp = requests.post(TAVILY_URL, json=payload, headers=headers, timeout=TAVILY_TIMEOUT)

    if resp.status_code == 401 or resp.status_code == 403:
        raise RuntimeError(f"Tavily auth failed: HTTP {resp.status_code} (key invalid or expired)")
    if resp.status_code == 429:
        raise RuntimeError(f"Tavily rate limited: HTTP 429 (quota exhausted)")
    if not resp.ok:
        raise RuntimeError(f"Tavily HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    results = data.get("results", [])
    answer = data.get("answer", "")

    return {
        "answer": answer or "",
        "results": [
            {"title": r.get("title", ""), "snippet": r.get("content", "")[:300]}
            for r in results[:max_results]
        ],
    }


def _search_via_deepseek(query: str, max_results: int = 3) -> dict:
    """用 DeepSeek LLM 知识兜底，返回与 Tavily 一致的结构。"""
    from config import LLM_API_KEY
    if not LLM_API_KEY:
        return {"answer": "", "results": [], "error": "LLM not configured"}

    from agent.llm import chat

    prompt = f"""请针对以下查询提供结构化的知识回答：

查询：{query}

请输出 JSON（只输出 JSON，不要其他文字）：
{{
    "answer": "针对查询的简要总结（100-200字）",
    "results": [
        {{"title": "知识点1", "snippet": "具体内容..."}},
        {{"title": "知识点2", "snippet": "具体内容..."}}
    ]
}}

最多提供 {max_results} 条结果。"""

    resp = chat(
        [{"role": "system", "content": "你是活动策划知识助手。请用简洁的中文回答，只输出JSON。"},
         {"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=800,
        timeout=20
    )

    if resp is None:
        return {"answer": "", "results": [], "error": "LLM unavailable"}

    content = resp["choices"][0]["message"].get("content", "")
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.rstrip().endswith("```"):
            content = content[:content.rfind("```")]

    data = json.loads(content)
    return {
        "answer": data.get("answer", ""),
        "results": data.get("results", []),
    }


def search_web(query, max_results=3, search_depth="basic"):
    """
    搜索知识：Tavily 实时搜索 → 失败则 DeepSeek LLM 兜底。

    返回 JSON 字符串：
    {
        "ok": true/false,
        "source": "tavily" | "deepseek" | "none",
        "answer": "...",
        "results": [{"title": "...", "snippet": "..."}],
        "error": "..."  // 仅失败时
    }
    """
    # ── 第一优先级：Tavily 实时搜索 ──
    try:
        data = _search_via_tavily(query, max_results=max_results, search_depth=search_depth)
        return json.dumps({
            "ok": True,
            "source": "tavily",
            "answer": data.get("answer", ""),
            "results": data.get("results", []),
        }, ensure_ascii=False)

    except Exception as e:
        error_msg = str(e)[:200]
        # 区分错误类型决定日志级别
        if "timeout" in error_msg.lower() or "connect" in error_msg.lower():
            print(f"[search] Tavily 连接超时/不通，降级到 DeepSeek: {error_msg}")
        elif "auth" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            print(f"[search] Tavily Key 无效，降级到 DeepSeek: {error_msg}")
        elif "429" in error_msg:
            print(f"[search] Tavily 额度耗尽，降级到 DeepSeek: {error_msg}")
        else:
            print(f"[search] Tavily 失败，降级到 DeepSeek: {error_msg}")

    # ── 第二优先级：DeepSeek LLM 知识兜底 ──
    try:
        data = _search_via_deepseek(query, max_results=max_results)
        if data.get("error"):
            return json.dumps({
                "ok": False,
                "source": "none",
                "answer": "",
                "results": [],
                "error": data["error"],
            }, ensure_ascii=False)

        return json.dumps({
            "ok": True,
            "source": "deepseek",
            "answer": data.get("answer", ""),
            "results": data.get("results", []),
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({
            "ok": False,
            "source": "none",
            "answer": "",
            "results": [],
            "error": str(e)[:200],
        }, ensure_ascii=False)


def is_available():
    """Tavily 或 LLM 任一可用即返回 True。"""
    from config import LLM_API_KEY
    return bool(TAVILY_API_KEY) or bool(LLM_API_KEY)


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    print("=" * 50)
    print("Testing search with graceful degradation...")
    print(f"Tavily key configured: {bool(TAVILY_API_KEY)}")
    print("=" * 50)

    result = search_web("校园科技节活动策划案例", max_results=2)
    data = json.loads(result)
    print(f"ok: {data.get('ok')}")
    print(f"source: {data.get('source')}")
    print(f"answer: {data.get('answer', '')[:200]}")
    for r in data.get('results', []):
        print(f"  - {r['title']}: {r['snippet'][:100]}")
