def generate_navigation(room: dict) -> str:
    """
    根据教室信息生成步行导航指引文本
    格式：建筑 → 楼层 → 具体位置 → 沿途参照物
    """
    if not room:
        return "暂无可用教室"

    building = room.get("building", "未知建筑")
    floor = room.get("floor", 1)
    room_id = room.get("room_id", "?")
    entrance_note = room.get("entrance_note", "")
    landmarks = room.get("nav_landmarks", [])
    coordinate_x = room.get("coordinate_x", 0)
    coordinate_y = room.get("coordinate_y", 0)

    lines = []
    lines.append(f"📍 目标教室: **{room_id}**（{building}）")
    lines.append("")

    lines.append(f"🚶 导航路线:")
    if entrance_note:
        lines.append(f"   {entrance_note}")

    if landmarks:
        lines.append(f"   沿途参照物: {' → '.join(landmarks)} → {room_id}")

    lines.append(f"   教室坐标: ({coordinate_x}, {coordinate_y})")
    return "\n".join(lines)
