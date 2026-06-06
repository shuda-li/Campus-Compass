"""
知识搜索（基于 LLM 而非外部 API）

原实现调用 Tavily Search API，因国内网络限制改为直接使用 DeepSeek。
LLM 的知识面足以覆盖活动策划案例、背景知识和创意灵感。
"""
import json
from dotenv import load_dotenv

load_dotenv()


def search_web(query, max_results=3, search_depth="basic"):
    """
    用 LLM 搜索知识（替代 Tavily API）。

    返回格式保持不变：{"ok": True/False, "answer": "...", "results": [...]}
    """
    try:
        from config import LLM_API_KEY
        if not LLM_API_KEY:
            return json.dumps({"ok": False, "answer": "", "results": [],
                               "error": "LLM not configured"}, ensure_ascii=False)

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
            return json.dumps({"ok": False, "answer": "", "results": [],
                               "error": "LLM unavailable"}, ensure_ascii=False)

        content = resp["choices"][0]["message"].get("content", "")
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.rstrip().endswith("```"):
                content = content[:content.rfind("```")]

        data = json.loads(content)
        return json.dumps({
            "ok": True,
            "answer": data.get("answer", ""),
            "results": data.get("results", [])
        }, ensure_ascii=False)

    except Exception as e:
        print(f"[LLM Search] {e}")
        return json.dumps({"ok": False, "answer": "", "results": [],
                           "error": str(e)[:100]}, ensure_ascii=False)


def is_available():
    """只要 LLM 可用，搜索就可用。"""
    from config import LLM_API_KEY
    return bool(LLM_API_KEY)


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    print("Testing LLM-based search...")
    result = search_web("校园科技节活动策划案例", max_results=2)
    data = json.loads(result)
    print(f"ok: {data.get('ok')}")
    print(f"answer: {data.get('answer', '')[:200]}")
    for r in data.get('results', []):
        print(f"  - {r['title']}: {r['snippet'][:100]}")
