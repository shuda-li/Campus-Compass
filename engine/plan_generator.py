import json
import re
from agent.skill_loader import match_skill, load_skill


def _search_topic_knowledge(topic: str) -> dict:
    try:
        from agent.mcp.tavily_search import search_web, is_available
        if not is_available():
            return {"available": False, "summary": "", "results": []}

        result = search_web(f"校园活动策划 {topic} 创意 案例 流程", max_results=3)
        data = json.loads(result)
        if not data.get("ok"):
            return {"available": False, "summary": "", "results": []}

        return {
            "available": True,
            "summary": data.get("answer", ""),
            "results": data.get("results", [])
        }
    except Exception as e:
        print(f"[PlanGen] MCP搜索失败: {e}")
        return {"available": False, "summary": "", "results": []}


SKILL_TO_CATEGORY = {
    "lecture_planning": "分享",
    "competition_planning": "竞赛",
    "performance_planning": "演出",
    "exhibition_planning": "展览",
    "practice_planning": "实践",
    "sports_planning": "运动",
}


def generate_plan(topic: str, participants: int, rooms: list, llm_call_fn=None, skill: dict = None) -> dict:
    if llm_call_fn:
        try:
            plan = llm_call_fn(topic, participants)
            if plan and plan.get("activity_content"):
                return plan
        except Exception as e:
            print(f"[PlanGen] LLM首次调用失败: {e}")

    return _reason_plan(topic, participants, rooms, skill)


def _reason_plan(topic: str, participants: int, rooms: list, skill: dict = None) -> dict:
    try:
        from config import LLM_API_KEY
        if LLM_API_KEY:
            from agent.llm import complete
            prompt = _build_simple_prompt(topic, participants, skill)
            content = complete(prompt, system="你是校园活动策划专家，只输出JSON。", temperature=0.8, max_tokens=2000, timeout=25)
            if content:
                plan = _parse_simple_response(content)
                if plan and plan.get("activity_content"):
                    print("[PlanGen] _reason_plan 中 LLM 生成成功")
                    return plan
    except Exception as e:
        print(f"[PlanGen] _reason_plan LLM 也失败: {e}")

    return _ultimate_fallback(topic, participants)


def _build_simple_prompt(topic: str, participants: int, skill: dict = None) -> str:
    # ── 技能指引部分（P0-1）──
    skill_part = ""
    if skill:
        title = skill.get("title", "")
        phases = skill.get("phases", [])
        host_guides = skill.get("host_guides", {})
        materials = skill.get("materials", [])
        constraints = skill.get("constraints", {})

        if any([phases, host_guides, materials, constraints]):
            skill_part = f"\n===== 活动策划技能模板：{title} =====\n"

            if phases:
                skill_part += "\n参考流程（请在此基础上根据主题创新调整）：\n"
                for p in phases:
                    skill_part += f"  - {p.get('phase','')}（{p.get('duration','')}）: {p.get('content','')} [{p.get('interaction','')}]\n"

            if host_guides:
                skill_part += "\n参考引导语（请根据主题改写，不要照抄）：\n"
                for key, val in host_guides.items():
                    skill_part += f"  - {key}: {val}\n"

            if materials:
                skill_part += "\n参考物资清单（请根据主题调整）：\n"
                for m in materials:
                    skill_part += f"  - {m.get('name','')} ×{m.get('qty','')}（{m.get('spec','')}）\n"

            if constraints:
                skill_part += "\n约束条件：\n"
                for key, val in constraints.items():
                    skill_part += f"  - {key}: {val}\n"

            skill_part += "===================================\n"

    return f'''为主题"{topic}"设计一个校园活动方案。

参与人数: {participants}人
{skill_part}
你必须深入理解"{topic}"的含义，基于理解来设计活动，不要套万能模板。
如果涉及专业知识（如MBTI/心理学/编程等），要体现该领域的特有概念。
如果提供了技能模板，请参考其流程结构，但根据具体主题进行创新调整。

输出JSON:
{{
    "activity_purpose": "活动目的（写清楚这个主题的独特价值，150-250字）",
    "activity_topic": "{topic}",
    "activity_time": "建议时间",
    "organizer": "主办单位建议",
    "host": "承办单位建议",
    "activity_content": [
        {{"phase": "环节名称", "duration": "时长", "content": "具体内容和执行方式", "host_guide": "主持人引导语", "interaction": "互动方式"}}
    ],
    "activity_materials": [
        {{"name": "物资名称", "spec": "规格", "qty": "数量"}}
    ]
}}'''


def _parse_simple_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.rstrip().endswith("```"):
            content = content[: content.rfind("```")]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


def _ultimate_fallback(topic: str, participants: int, skill: dict = None) -> dict:
    print("[PlanGen] 使用终极兜底模板")

    # ── 优先使用 Skill 模板（P0-1）──
    if skill and skill.get("phases"):
        phases = skill["phases"]
        host_guides = skill.get("host_guides", {})
        materials = skill.get("materials", [])
        activity_content = []
        for p in phases:
            phase_key = p.get("phase", "")
            # 尝试匹配引导语
            guide_key = None
            if "签到" in phase_key:
                guide_key = "签到"
            elif "开幕" in phase_key or "开场" in phase_key or "致辞" in phase_key:
                guide_key = "开幕" if "开幕" in host_guides else ("开场" if "开场" in host_guides else None)
            elif "互动" in phase_key or "讨论" in phase_key:
                guide_key = "互动环节" if "互动环节" in host_guides else None
            elif "颁奖" in phase_key or "点评" in phase_key:
                guide_key = "颁奖" if "颁奖" in host_guides else None
            elif "闭幕" in phase_key or "总结" in phase_key or "合影" in phase_key:
                guide_key = "闭幕" if "闭幕" in host_guides else ("结束" if "结束" in host_guides else None)
            host_guide = host_guides.get(guide_key, "") if guide_key else ""

            activity_content.append({
                "phase": p.get("phase", ""),
                "duration": p.get("duration", ""),
                "content": p.get("content", ""),
                "host_guide": host_guide,
                "interaction": p.get("interaction", ""),
            })

        activity_materials = []
        for m in materials:
            activity_materials.append({
                "name": m.get("name", ""),
                "spec": m.get("spec", ""),
                "qty": m.get("qty", ""),
            })
        if not activity_materials:
            activity_materials = [
                {"name": "签到表", "spec": "A4打印", "qty": "3张"},
                {"name": "饮用水", "spec": "瓶装550ml", "qty": f"{int(participants * 1.2)}瓶"},
            ]

        return {
            "activity_purpose": f'本次活动以"{topic}"为主题，旨在为同学们提供交流与学习的平台，通过精心设计的环节让参与者深入了解"{topic}"相关内容，激发兴趣、拓展视野。',
            "activity_time": "待定",
            "activity_topic": topic,
            "organizer": "待定",
            "host": "待定",
            "activity_content": activity_content,
            "activity_materials": activity_materials,
        }

    # ── 无 Skill 时的通用兜底 ──
    return {
        "activity_purpose": f'本次活动以"{topic}"为主题，旨在为同学们提供交流与学习的平台，通过精心设计的环节让参与者深入了解"{topic}"相关内容，激发兴趣、拓展视野。',
        "activity_time": "待定",
        "activity_topic": topic,
        "organizer": "待定",
        "host": "待定",
        "activity_content": [
            {"phase": "开场环节", "duration": "15分钟", "content": f'围绕"{topic}"进行介绍，让参与者了解活动背景和目标', "host_guide": f'欢迎大家来到今天的活动！今天我们将一起探索"{topic}"。', "interaction": "自由交流"},
            {"phase": "核心环节", "duration": "45分钟", "content": f'深入"{topic}"主题，通过多种形式展开活动主体内容', "host_guide": "接下来进入今天的核心环节，请大家积极参与！", "interaction": "全员参与"},
            {"phase": "互动环节", "duration": "20分钟", "content": f'围绕"{topic}"进行互动交流，加深理解和体验', "host_guide": "现在轮到大家了，有什么想法或问题都可以提出来！", "interaction": "问答+讨论"},
            {"phase": "总结收尾", "duration": "10分钟", "content": "回顾活动亮点，收集反馈，合影留念", "host_guide": "感谢大家的热情参与，期待下次再见！", "interaction": "合影留念"},
        ],
        "activity_materials": [
            {"name": "签到表", "spec": "A4打印", "qty": "3张"},
            {"name": "饮用水", "spec": "瓶装550ml", "qty": f"{int(participants * 1.2)}瓶"},
            {"name": "活动道具", "spec": "根据主题定制", "qty": "1套"},
        ],
    }


def build_plan_prompt(topic: str, participants: int, search_knowledge: dict = None, skill: dict = None) -> str:
    knowledge_part = ""
    if search_knowledge and search_knowledge.get("available"):
        summary = search_knowledge.get("summary", "")
        results = search_knowledge.get("results", [])
        knowledge_part = "\n===== 互联网搜索到的参考信息 =====\n"
        knowledge_part += f"{summary}\n"
        for i, r in enumerate(results[:3]):
            knowledge_part += f"\n参考案例{i+1}: {r.get('title', '')}\n{r.get('snippet', '')}\n"
        knowledge_part += "===================================\n"

    memory_part = ""
    try:
        from agent.memory import load_memory_block
        block = load_memory_block()
        if block:
            memory_part = f"\n===== 用户历史偏好 =====\n{block}\n===========================\n"
    except Exception:
        pass

    # ── 技能指引部分（P0-1）──
    skill_part = ""
    if skill:
        title = skill.get("title", "")
        phases = skill.get("phases", [])
        host_guides = skill.get("host_guides", {})
        materials = skill.get("materials", [])
        constraints = skill.get("constraints", {})

        if any([phases, host_guides, materials, constraints]):
            skill_part = f"\n===== 活动策划技能模板：{title} =====\n"
            if phases:
                skill_part += "\n参考流程（请在此基础上根据主题创新调整）：\n"
                for p in phases:
                    skill_part += f"  - {p.get('phase','')}（{p.get('duration','')}）: {p.get('content','')} [{p.get('interaction','')}]\n"
            if host_guides:
                skill_part += "\n参考引导语（请根据主题改写，不要照抄）：\n"
                for key, val in host_guides.items():
                    skill_part += f"  - {key}: {val}\n"
            if materials:
                skill_part += "\n参考物资清单（请根据主题调整）：\n"
                for m in materials:
                    skill_part += f"  - {m.get('name','')} ×{m.get('qty','')}（{m.get('spec','')}）\n"
            if constraints:
                skill_part += "\n约束条件：\n"
                for key, val in constraints.items():
                    skill_part += f"  - {key}: {val}\n"
            skill_part += "===================================\n"

    return f'''你是一个有创意的校园活动策划师。请为主题"{topic}"设计一个独特、有趣、可执行的活动方案。

参与人数: {participants}人
{knowledge_part}{memory_part}{skill_part}
核心原则:
1. 深入理解"{topic}"的真正含义——如果它涉及专业知识（如MBTI人格理论、编程技术、心理学等），你必须展现对该领域的理解
2. 活动目的要写出"{topic}"这个主题的独特价值，不要写"搭建平台""促进交流"这种万能套话
3. 活动环节根据主题特点灵活设计，每个环节的内容要具体实在，包含可操作细节
4. 物资清单要真实贴合这个主题的实际需求
5. 主持人引导语要自然口语化，贴合当前环节

输出JSON（只输出JSON，不要其他文字）:
{{
    "activity_purpose": "写清楚这个主题的独特价值（200-300字）",
    "activity_topic": "{topic}",
    "activity_time": "建议的活动时间",
    "organizer": "建议主办单位",
    "host": "建议承办单位",
    "activity_content": [
        {{"phase": "环节名称", "duration": "时长", "content": "具体内容和执行方式", "host_guide": "主持人引导语", "interaction": "互动方式"}}
    ],
    "activity_materials": [
        {{"name": "物资名称", "spec": "规格要求", "qty": "数量"}}
    ]
}}'''


def parse_plan_response(content: str) -> dict:
    content = content.strip()
    
    # 清理 Markdown 代码块标记
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.rstrip().endswith("```"):
            content = content[: content.rfind("```")]
    
    content = content.strip()
    
    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"[PlanGen] 直接解析失败: {e}")
    
    # 尝试找到 JSON 对象的开始和结束
    try:
        # 找到第一个 { 和最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = content[start:end+1]
            return json.loads(json_str)
    except Exception as e:
        print(f"[PlanGen] 提取JSON后解析也失败: {e}")
    
    # 如果都失败了，尝试使用 _ultimate_fallback
    raise ValueError("无法解析 LLM 返回的 JSON")


def call_llm_for_plan(topic: str, participants: int, api_key: str, api_url: str, model: str, search_knowledge: dict = None) -> dict:
    import requests
    from agent.proxy import get_proxy
    prompt = build_plan_prompt(topic, participants, search_knowledge)
    session = requests.Session()
    session.trust_env = False  # 绕过 Windows 系统代理
    kwargs = {"timeout": 25}
    proxy = get_proxy()
    if proxy:
        kwargs["proxies"] = proxy
    response = session.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "你是校园活动策划专家。你的回答必须只包含JSON，不要有其他文字。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.8,
            "max_tokens": 4000,
        },
        **kwargs,
    )
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return parse_plan_response(content)
