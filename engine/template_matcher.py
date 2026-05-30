import json
import os
from config import TEMPLATE_PATH


def match_template(intent: dict) -> dict:
    """根据活动类型匹配模板"""
    activity_type = intent.get("activity_type", "讲座")

    if not os.path.exists(TEMPLATE_PATH):
        return _default_template()

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        templates = json.load(f)

    template = templates.get(activity_type)
    if template is None:
        template = templates.get("讲座", _default_template())

    if int(intent.get("participants", 50)) > template.get("minimum_capacity", 50):
        template["suggested_capacity"] = int(intent.get("participants", 50)) + 10

    return template


def _default_template() -> dict:
    return {
        "activity_type": "讲座",
        "default_timeline": [
            {"time": "14:00-14:30", "content": "签到入场"},
            {"time": "14:30-16:00", "content": "活动主体"},
            {"time": "16:00-16:30", "content": "总结与结束"},
        ],
        "default_resources": ["投影仪", "音响"],
        "default_budget": {"场地布置": 200, "宣传物料": 100},
        "minimum_capacity": 50,
    }
