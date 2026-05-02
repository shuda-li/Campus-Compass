import json


def rank_rooms(rooms: list, intent: dict, plan: dict = None) -> list:
    """
    对教室列表多维加权打分排序:

    评分维度（总分上限 ~50 分）:
    1. 容量适配度  (0~20分)  —— 核心：教室不能太小，也不能浪费太大
    2. 楼层便利性  (0~5分)   —— 低楼层优先
    3. 设备匹配度  (0~15分)  —— 每匹配一项 +3
    4. 建筑偏好    (0~10分)  —— 用户指定建筑时加分

    容量适配度细分:
      - 容量不足        →  0 分（已被 SQL 过滤，不应出现）
      - 容量刚好 (0~5%) → +8 分（偏紧，但能用）
      - 最佳区间 (5%~30%) → +15 分（留有适当余量）
      - 偏大 (30%~80%)  → +12 分（空间浪费，扣分）
      - 过大 (>80%)     → +5 分（严重浪费，大幅扣分）
    """
    preferred_building = intent.get("building", "")
    needed_equipment = set(intent.get("equipment", []))
    participants = max(1, int(intent.get("participants", 50)))

    def score(room):
        s = 0
        capacity = room.get("capacity", 0)

        # ===== 1. 容量适配度 =====
        if capacity >= participants:
            ratio = (capacity - participants) / participants
            if ratio <= 0.05:
                s += 8     # 刚好够用
            elif ratio <= 0.30:
                s += 15    # 最佳区间：有 5%~30% 余量
            elif ratio <= 0.80:
                s += 12    # 偏大：空间利用率不高
            else:
                s += 5     # 过大：严重浪费空间
        # 容量不足的情况已被 SQL 过滤，不会到这里

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
