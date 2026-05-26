import json


def rank_rooms(rooms: list, intent: dict, plan: dict = None) -> list:
    """
    对教室列表多维加权打分排序:

    评分维度（总分上限 ~50 分）:
    1. 容量适配度  (0~20分)  —— 核心：连续函数，15%余量最优
    2. 楼层便利性  (0~5分)   —— 低楼层优先
    3. 设备匹配度  (0~15分)  —— 每匹配一项 +3
    4. 建筑偏好    (0~10分)  —— 用户指定建筑时加分

    容量适配度（连续分段线性，消除硬跳变）:
      - 0~5%:    线性 6 → 10 分
      - 5%~15%:  线性 10 → 15 分（最优区间）
      - 15%~35%: 线性 15 → 10 分
      - 35%~80%: 线性 10 → 4 分
      - >80%:    线性 4 → 1 分"""
    preferred_building = intent.get("building", "")
    needed_equipment = set(intent.get("equipment", []))
    participants = max(1, int(intent.get("participants", 50)))

    def _capacity_score(ratio: float) -> float:
        if ratio <= 0.05:
            return 6.0 + (ratio / 0.05) * 4.0
        elif ratio <= 0.15:
            return 10.0 + ((ratio - 0.05) / 0.10) * 5.0
        elif ratio <= 0.35:
            return 15.0 - ((ratio - 0.15) / 0.20) * 5.0
        elif ratio <= 0.80:
            return 10.0 - ((ratio - 0.35) / 0.45) * 6.0
        else:
            return max(1.0, 4.0 - ((ratio - 0.80) / 0.20) * 3.0)

    def score(room):
        s = 0
        capacity = room.get("capacity", 0)

        if capacity >= participants:
            ratio = (capacity - participants) / participants
            s += _capacity_score(ratio)

        # ===== 2. 楼层便利性 =====
        floor = room.get("floor", 1)
        if floor <= 2:
            s += 5
        elif floor <= 4:
            s += 2

        # ===== 3. 设备匹配度 =====
        equip_raw = room.get("equipment", "[]")
        if isinstance(equip_raw, str):
            try:
                equip_list = json.loads(equip_raw)
            except (json.JSONDecodeError, TypeError):
                equip_list = []
        else:
            equip_list = equip_raw if isinstance(equip_raw, list) else []

        equip_text = " ".join(equip_list).lower()
        match_count = 0
        for need in needed_equipment:
            if need.lower() in equip_text:
                match_count += 1
        s += match_count * 3

        # ===== 4. 建筑偏好 =====
        if preferred_building:
            building_name = room.get("building", "")
            if preferred_building in building_name:
                s += 10

        return s

    scored = [(score(r), r) for r in rooms]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]
