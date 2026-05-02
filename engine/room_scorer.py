def rank_rooms(rooms: list, intent: dict, plan: dict = None) -> list:
    """
    对教室列表打分排序，考虑：
    - 容量匹配度
    - 楼层（低楼层优先）
    - 设备匹配
    - 建筑偏好
    """
    preferred_building = intent.get("building", "")
    needed_equipment = set(intent.get("equipment", []))
    participants = int(intent.get("participants", 50))

    def score(room):
        s = 0
        capacity = room.get("capacity", 0)

        if capacity >= participants:
            s += 10
        if capacity >= participants + 10:
            s += 5

        floor = room.get("floor", 1)
        if floor <= 2:
            s += 5
        elif floor <= 4:
            s += 2

        try:
            equipment = __import__("json").loads(room.get("equipment", "[]"))
        except Exception:
            equipment = []
        match_count = sum(1 for e in needed_equipment if e in str(equipment))
        s += match_count * 3

        if preferred_building and preferred_building in room.get("building", ""):
            s += 8

        return s

    scored = [(score(r), r) for r in rooms]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]
