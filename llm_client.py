import json
import requests
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL


def call_llm_for_ideation(intent: dict) -> dict:
    """根据解析出的意图，调用LLM生成活动创意"""
    prompt = _build_ideation_prompt(intent)

    if not LLM_API_KEY:
        return _fallback_ideation(intent)

    try:
        response = requests.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是校园活动策划专家，请用JSON格式输出创意方案。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.8,
            },
            timeout=30,
        )
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_llm_response(content)
    except Exception as e:
        print(f"[LLM] 调用失败: {e}")
        return _fallback_ideation(intent)


def _build_ideation_prompt(intent: dict) -> str:
    activity_type = intent.get("activity_type", "讲座")
    participants = intent.get("participants", 50)
    theme = intent.get("theme", intent.get("raw_input", ""))

    return f'''请根据以下信息生成校园活动方案:

活动类型: {activity_type}
预计人数: {participants}人
用户想法: {theme}

请用JSON格式输出（只输出JSON，不要其他文字）:
{{
    "recommended_title": "推荐活动标题",
    "activity_timeline": [
        {{"time": "14:00-14:30", "content": "签到入场"}},
        {{"time": "14:30-15:30", "content": "主题分享"}},
        {{"time": "15:30-16:00", "content": "问答互动"}}
    ],
    "resource_list": ["设备1", "设备2"],
    "promotion_suggestion": "宣传建议文字"
}}'''


def _parse_llm_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
    return json.loads(content)


def _fallback_ideation(intent: dict) -> dict:
    return {
        "recommended_title": f"{intent.get('activity_type', '校园活动')}策划方案",
        "activity_timeline": [
            {"time": "14:00-14:30", "content": "签到入场"},
            {"time": "14:30-16:00", "content": "活动主体"},
            {"time": "16:00-16:30", "content": "互动与总结"},
        ],
        "resource_list": ["投影仪", "音响", "签到表"],
        "promotion_suggestion": "通过校园公众号和海报进行宣传",
    }
