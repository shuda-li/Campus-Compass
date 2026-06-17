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

    num_match = re.search(r"(\d+)\s*(人|位|名)", text)
    if num_match:
        intent["participants"] = int(num_match.group(1))
    else:
        # 回退：尝试匹配纯数字（过滤日期/时间上下文）
        for m in re.finditer(r"(\d+)", text):
            num = int(m.group(1))
            if num > 10000:
                continue
            after = text[m.end():m.end() + 2]
            if after and after[0] in "年月日号点时秒分":
                continue
            if after and after[:2] in ["年", "月", "日"]:
                continue
            intent["participants"] = num
            break

    bld_match = re.search(r"([A-Za-z]+座)", text)
    if bld_match:
        intent["building"] = bld_match.group(1)

    equipment_keywords = [
        "投影", "音响", "灯光", "舞台", "麦克风", "空调", "白板", "黑板",
        "智慧屏", "录播设备", "同声传译", "LED屏", "提词器", "摄像机",
        "打印机", "幕布", "讲台", "桌椅",
    ]
    intent["equipment"] = [e for e in equipment_keywords if e in text]

    intent["theme"] = user_input.strip()
    return intent
