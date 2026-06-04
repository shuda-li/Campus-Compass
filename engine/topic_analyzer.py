import json


def analyze_topic(topic: str, llm_call_fn=None) -> dict:
    """
    分析主题复杂度，判断是否需要扩展。
    返回:
    {
        "is_simple": True/False,
        "original": "原主题",
        "expanded": "扩展后主题" 或 None,
        "confidence": 0.0~1.0,
        "reason": "判断依据",
    }
    """
    score = _complexity_score(topic)

    if score >= 0.6:
        return {
            "is_simple": False,
            "original": topic,
            "expanded": None,
            "confidence": score,
            "reason": f"主题包含具体关键词，清晰度评分 {score:.0%}",
        }

    if llm_call_fn:
        try:
            expanded = llm_call_fn(topic)
            return {
                "is_simple": True,
                "original": topic,
                "expanded": expanded,
                "confidence": score,
                "reason": f"主题过于简略（评分 {score:.0%}），已自动扩展",
            }
        except Exception:
            pass

    suggestion = _rule_expand(topic)
    return {
        "is_simple": True,
        "original": topic,
        "expanded": suggestion,
        "confidence": score,
        "reason": f"主题过于简略（评分 {score:.0%}），已用规则扩展",
    }


def _complexity_score(topic: str) -> float:
    chars = len(topic)

    specific_nouns = [
        "电脑", "硬件", "软件", "编程", "算法", "数据", "网络", "安全",
        "AI", "人工智能", "机器学习", "深度学习", "区块链", "物联网",
        "机器人", "无人机", "芯片", "电路", "通信", "云计算", "大数据",
        "知识", "分享", "演讲", "论坛", "峰会", "路演", "展览", "展销",
        "招聘", "就业", "创业", "创新", "设计", "摄影", "音乐", "舞蹈",
        "书法", "绘画", "手工", "烘焙", "花艺", "茶艺", "咖啡", "美食",
        "体育", "篮球", "足球", "排球", "乒乓球", "羽毛球", "跑步", "健身",
        "瑜伽", "太极", "武术", "跆拳道", "拳击", "游泳", "登山", "骑行",
        "辩论", "演讲", "朗诵", "写作", "阅读", "英语", "日语", "法语",
        "志愿者", "公益", "环保", "献血", "支教", "募捐", "义卖",
        "科技", "技术", "技能", "知识", "经验", "心得", "干货", "实战",
        "分享会", "培训", "沙龙", "工作坊", "workshop",
        "大赛", "竞赛", "挑战赛",
    ]
    match_count = 0
    for noun in specific_nouns:
        if noun in topic:
            match_count += 1

    noun_score = min(match_count * 0.35, 0.7)

    if chars >= 10:
        length_score = 0.3
    elif chars >= 6:
        length_score = 0.2
    elif chars >= 4:
        length_score = 0.1
    else:
        length_score = 0.05

    has_action = any(k in topic for k in ["办", "搞", "组织", "策划", "举办", "安排", "布置"])
    action_score = 0.15 if has_action else 0

    return noun_score + length_score + action_score


def _rule_expand(topic: str) -> str:
    if "科技" in topic and "创新" in topic:
        return "AI 时代下的校园科技创新实践分享会"
    if "科技" in topic:
        return "前沿科技趋势与技术实践分享活动"
    if "创业" in topic:
        return "大学生创新创业经验交流与项目路演"
    if "音乐" in topic:
        return "校园音乐之夜——青春旋律演奏会暨交流活动"
    if "体育" in topic:
        return "阳光体育——校园趣味运动会暨团队挑战赛"
    if "摄影" in topic:
        return "光影校园——摄影技巧分享会暨作品展览"
    if "编程" in topic:
        return "编程马拉松——校园代码挑战赛暨技术交流工作坊"
    if "设计" in topic:
        return "创意设计——校园视觉设计作品展暨经验分享沙龙"
    if "读书" in topic or "阅读" in topic:
        return "书香校园——读书分享会暨经典阅读交流活动"
    if "志愿" in topic or "公益" in topic:
        return "青春志愿行——校园公益服务实践分享活动"
    return f"{topic}——校园专题活动策划方案"


def build_expansion_prompt(topic: str) -> str:
    return f'''请将以下简略的活动主题扩展成更具吸引力和明确性的完整标题。

原始主题: {topic}

要求:
1. 保持原主题的核心意思，但让它更具体、更吸引人
2. 增加活动形式暗示（如"分享会""工作坊""竞赛""展览""演出"等）
3. 控制在 15-30 个字
4. 适合校园活动场景
5. 只返回扩展后的标题文本，不要任何解释'''


def parse_expansion_response(content: str) -> str:
    content = content.strip().strip('"').strip("'")
    if len(content) > 60:
        content = content[:60]
    return content


def expand_topic_via_llm(topic: str, api_key: str, api_url: str, model: str) -> str:
    import requests
    prompt = build_expansion_prompt(topic)
    session = requests.Session()
    session.trust_env = False  # 绕过 Windows 系统代理
    response = session.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "你是活动策划标题专家。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 80,
        },
        timeout=15,
    )
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    return parse_expansion_response(content)
