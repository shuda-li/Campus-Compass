def estimate_budget(
    template: dict,
    participants: int,
    activity_type: str = "讲座",
    room_equipment: list = None
) -> dict:

    base = template.get("default_budget", {
        "场地布置": 200,
        "宣传物料": 150,
        "其他": 100,
    })

    # 人数倍率
    multiplier = 1.0

    if participants > 100:
        multiplier = 1.5
    elif participants > 50:
        multiplier = 1.2

    # 活动类型倍率
    activity_multiplier = {
        "讲座": 1.0,
        "社团活动": 0.9,
        "竞赛": 1.3,
        "晚会": 1.6,
    }

    multiplier *= activity_multiplier.get(activity_type, 1.0)

    budget = {}

    for key, value in base.items():
        budget[key] = round(value * multiplier)

    # 设备费用
    equipment_prices = {
        "投影仪": 50,
        "音响": 80,
        "灯光": 200,
        "舞台": 300,
        "视频会议": 150,
        "空调": 30,
    }

    equipment_cost = 0

    if room_equipment:
        for eq in room_equipment:
            equipment_cost += equipment_prices.get(eq, 0)

    budget["设备费用"] = equipment_cost

    total = sum(budget.values())

    budget["合计"] = total

    # 预算等级
    if total < 500:
        level = "经济型活动"
    elif total < 1000:
        level = "标准型活动"
    else:
        level = "大型活动"

    budget["预算等级"] = level

    budget["预算说明"] = "预算会根据人数规模、活动类型和设备需求动态调整"

    return budget