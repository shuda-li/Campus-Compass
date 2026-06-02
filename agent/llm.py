import json
import requests
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL


def _get_proxies():
    from agent.proxy import get_proxy
    return get_proxy()


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
    response = requests.post(
        LLM_API_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
        proxies=_get_proxies()
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

    response = requests.post(
        LLM_API_URL,
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
        stream=True,
        proxies=_get_proxies()
    )

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
    for chunk in stream_complete(
        prompt,
        system="你是校园活动策划专家。你的回答必须只包含JSON，不要有其他文字。",
        temperature=0.8,
        max_tokens=4000,
        timeout=90
    ):
        full_text += chunk
        yield {"type": "chunk", "text": chunk, "full": full_text}

    yield {"type": "done", "text": full_text}


def is_available() -> bool:
    return bool(LLM_API_KEY)
