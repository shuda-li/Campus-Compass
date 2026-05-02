import re

ACTIVITY_KEYWORDS = {
    "讲座": ["讲座", "演讲", "分享", "学术", "报告", "seminar", "交流会", "研讨会"],
    "晚会": ["晚会", "演出", "文艺", "才艺", "迎新", "毕业", "联欢", "庆典", "party"],
    "竞赛": ["竞赛", "比赛", "大赛", "挑战赛", "编程", "辩论", "答辩", "contest"],
    "社团活动": ["社团", "团建", "聚会", "沙龙", "工作坊", "workshop", "见面会"],
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

    equipment_keywords = ["投影", "音响", "灯光", "舞台", "麦克风", "空调", "白板", "黑板"]
    intent["equipment"] = [e for e in equipment_keywords if e in text]

    intent["theme"] = user_input.strip()
    return intent
