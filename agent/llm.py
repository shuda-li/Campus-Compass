import json
import requests
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL


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
    return resp["choices"][0]["message"].get("content", "")


def expand_topic(topic: str) -> str:
    from engine.topic_analyzer import build_expansion_prompt, parse_expansion_response
    prompt = build_expansion_prompt(topic)
    content = complete(prompt, system="你是活动策划标题专家。", temperature=0.9, max_tokens=80, timeout=15)
    if content:
        return parse_expansion_response(content)
    return ""


def generate_plan(topic: str, participants: int) -> dict:
    from engine.plan_generator import build_plan_prompt, parse_plan_response, _search_topic_knowledge
    
    # 先通过MCP搜索获取主题相关知识
    search_knowledge = _search_topic_knowledge(topic)
    if search_knowledge.get("available"):
        print(f"[LLM] 已获取主题相关搜索知识")
    
    prompt = build_plan_prompt(topic, participants, search_knowledge)
    content = complete(
        prompt,
        system="你是校园活动策划专家。你的回答必须只包含JSON，不要有其他文字。",
        temperature=0.8,
        max_tokens=2000,
        timeout=25,
    )
    if content:
        return parse_plan_response(content)
    return {}


def is_available() -> bool:
    return bool(LLM_API_KEY)
