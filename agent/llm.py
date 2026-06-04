import json
import requests
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL

# ═══════════════════════════════════════════════════════════════
# 共享 Session（连接复用 + 显式绕过系统代理）
# ═══════════════════════════════════════════════════════════════

def _build_session() -> requests.Session:
    """创建绕过系统代理的 Session，代理由 Campus Compass 内部管理。"""
    s = requests.Session()
    s.trust_env = False  # ← 关键：忽略 Windows 系统代理
    return s


def _get_request_kwargs(timeout: int = 45) -> dict:
    """构建 requests 调用的公共参数（代理 + 超时）。"""
    from agent.proxy import get_proxy
    proxy = get_proxy()
    kwargs = {"timeout": timeout}
    if proxy:
        kwargs["proxies"] = proxy
    return kwargs


def chat(messages: list, tools: list = None, temperature: float = 0.7, max_tokens: int = 1024, timeout: int = 45) -> dict:
    if not LLM_API_KEY:
        return None
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    session = _build_session()
    response = session.post(
        LLM_API_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        **_get_request_kwargs(timeout),
    )
    return response.json()


def complete(prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2000, timeout: int = 30) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = chat(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    if resp is None:
        return ""

    message = resp["choices"][0]["message"]
    content = message.get("content", "")
    reasoning = message.get("reasoning_content", "")

    return content or reasoning


def stream_complete(prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2000, timeout: int = 60):
    if not LLM_API_KEY:
        yield ""
        return

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True
    }

    session = _build_session()
    response = session.post(
        LLM_API_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        stream=True,
        **_get_request_kwargs(timeout),
    )

    # 检查 HTTP 状态码（非 200 直接报错，不解析 SSE）
    if response.status_code != 200:
        error_msg = f"LLM API returned {response.status_code}: {response.text[:300]}"
        print(f"[LLM] {error_msg}")
        yield f"[Error: {error_msg}]"
        return

    for line in response.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]
        if data_str == "[DONE]":
            break
        try:
            chunk = json.loads(data_str)
            choices = chunk.get("choices", [])
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content", "")
            if content:
                yield content
        except json.JSONDecodeError:
            continue


def expand_topic(topic: str) -> str:
    from engine.topic_analyzer import build_expansion_prompt, parse_expansion_response
    prompt = build_expansion_prompt(topic)
    content = complete(prompt, system="你是活动策划标题专家。", temperature=0.9, max_tokens=80, timeout=15)
    if content:
        return parse_expansion_response(content)
    return ""


def generate_plan(topic: str, participants: int, skill: dict = None) -> dict:
    from engine.plan_generator import build_plan_prompt, parse_plan_response, _search_topic_knowledge

    search_knowledge = _search_topic_knowledge(topic)
    if search_knowledge.get("available"):
        print(f"[LLM] 已获取主题相关搜索知识")

    prompt = build_plan_prompt(topic, participants, search_knowledge, skill)
    content = complete(
        prompt,
        system="你是校园活动策划专家。你的回答必须只包含JSON，不要有其他文字。",
        temperature=0.8,
        max_tokens=4000,
        timeout=25,
    )
    if content:
        return parse_plan_response(content)
    return {}


def stream_generate_plan(topic: str, participants: int, skill: dict = None):
    from engine.plan_generator import build_plan_prompt, _search_topic_knowledge

    search_knowledge = _search_topic_knowledge(topic)
    if search_knowledge.get("available"):
        print(f"[LLM] 已获取主题相关搜索知识")

    prompt = build_plan_prompt(topic, participants, search_knowledge, skill)
    full_text = ""
    try:
        for chunk in stream_complete(
            prompt,
            system="你是校园活动策划专家。你的回答必须只包含JSON，不要有其他文字。",
            temperature=0.8,
            max_tokens=4000,
            timeout=90
        ):
            full_text += chunk
            yield {"type": "chunk", "text": chunk, "full": full_text}
    except Exception as e:
        print(f"[LLM] 流式调用失败: {e}")

    yield {"type": "done", "text": full_text}


def is_available() -> bool:
    return bool(LLM_API_KEY)
