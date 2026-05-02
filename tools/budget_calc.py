def estimate_budget(template: dict, participants: int) -> dict:
    """
    根据模板和人数估算预算
    人数越多，某些费用按比例增加
    """
    base = template.get("default_budget", {
        "场地布置": 200,
        "宣传物料": 150,
        "其他": 100,
    })

    multiplier = 1.0
    if participants > 100:
        multiplier = 1.5
    elif participants > 50:
        multiplier = 1.2

    budget = {}
    for key, value in base.items():
        budget[key] = round(value * multiplier)

    budget["合计"] = sum(budget.values())
    return budget
