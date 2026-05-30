import re

ACTIVITY_KEYWORDS = {
    "讲座": [
        "讲座", "演讲", "分享", "学术", "报告", "seminar", "交流会", "研讨会",
        "论坛", "峰会", "宣讲会", "培训", "公开课", "大师课", "经验分享",
        "科普", "座谈", "茶话会",
    ],
    "晚会": [
        "晚会", "演出", "文艺", "才艺", "迎新", "毕业", "联欢", "庆典", "party",
        "嘉年华", "音乐节", "才艺展", "年度盛典", "文艺汇演", "歌手大赛",
        "音乐会", "舞会", "文化节", "艺术节", "合唱",
    ],
    "竞赛": [
        "竞赛", "比赛", "大赛", "挑战赛", "编程", "辩论", "答辩", "contest",
        "路演", "创业赛", "创新赛", "演讲比赛", "知识竞赛", "黑客松",
        "马拉松", "hackathon", "擂台赛", "选拔赛", "初赛", "决赛",
    ],
    "社团活动": [
        "社团", "团建", "聚会", "沙龙", "工作坊", "workshop", "见面会",
        "团日活动", "志愿活动", "素拓", "联谊", "招新", "换届",
        "动员大会", "总结大会", "义卖", "支教", "社会实践",
    ],
}


def parse_intent(user_input: str) -> dict:
    """
    从用户自然语言中提取：
    - activity_type: 讲座/晚会/竞赛/社团活动
    - participants: 预计人数
    - building: 偏好的教学楼
    - equipment: 需要的设备
    - theme: 活动主题关键词
    """
    intent = {
        "raw_input": user_input,
        "activity_type": "讲座",
        "participants": 50,
        "building": "E座",
        "equipment": [],
        "theme": "",
    }

    text = user_input

    for atype, keywords in ACTIVITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                intent["activity_type"] = atype
                break

    num_match = re.search(r"(\d+)\s*人", text)
    if num_match:
        intent["participants"] = int(num_match.group(1))

    bld_match = re.search(r"([A-Za-z]+座)", text)
    if bld_match:
        intent["building"] = bld_match.group(1)

    equipment_keywords = [
        "投影", "音响", "灯光", "舞台", "麦克风", "空调", "白板", "黑板",
        "智慧屏", "录播设备", "同声传译", "LED屏", "提词器", "摄像机",
        "打印机", "幕布", "讲台", "桌椅",
    ]
    intent["equipment"] = [e for e in equipment_keywords if e in text]

    intent["theme"] = _extract_theme(user_input)
    return intent


def _extract_theme(text: str) -> str:
    text = text.strip()

    action_words = "办|组织|策划|搞|安排|弄"
    quantifiers = "一个?|场|次|个"
    prefixes = "再|还|另外|我想|帮我|请|要|需要"
    adverbs = "再|还|又|来|去"

    compound_prefixes = [
        "再来|再来一|再来个",
        "还想要|想要|我要|请帮我|请|另外|还|又想",
        "还想再|还想|还再",
        "我还想再|我还想|我还想再|我还想|我还要|我还要再|我想要|我想要再",
    ]

    patterns_to_remove = [
        (rf"^({compound_prefixes[3]})\s*", 0),
        (rf"^({compound_prefixes[2]})\s*", 0),
        (rf"^({compound_prefixes[0]})\s*", 0),
        (rf"^({compound_prefixes[1]})\s*", 0),
        (rf"^({adverbs})\s*({action_words})\s*({quantifiers})?\s*", 0),
        (rf"^({prefixes})\s*({action_words})\s*({quantifiers})?\s*", 0),
        (rf"^({action_words})\s*({quantifiers})?\s*", 0),
        (rf"^({adverbs})\s*({quantifiers})\s*", 0),
        (rf"^({prefixes})\s*({quantifiers})?\s*", 0),
        (rf"^(还想|想要|我要)\s*", 0),
        (rf"^(一场|一个个?|一次)\s*", 0),
        (rf"^({quantifiers})\s*", 0),
        (rf"\s*({quantifiers})$", 0),
        (rf"^(的|在|于)\s*", 0),
    ]
    for pattern, _ in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()

    activity_suffixes = [
        r"\s*(活动|讲座|晚会|竞赛|比赛|会议|聚会|分享会|培训|演出)\s*$",
    ]
    for suffix_pattern in activity_suffixes:
        text = re.sub(suffix_pattern, "", text, flags=re.IGNORECASE)

    text = text.strip()

    if not text or len(text) < 2:
        return text

    return text
