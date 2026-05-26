import math


def generate_navigation(room: dict) -> str:
    if not room:
        return "暂无可用教室"

    building = room.get("building", "未知建筑")
    floor = room.get("floor", 1)
    room_id = room.get("room_id", "?")
    entrance_note = room.get("entrance_note", "")
    landmarks = room.get("nav_landmarks", [])
    coordinate_x = room.get("coordinate_x", 0)
    coordinate_y = room.get("coordinate_y", 0)

    # 默认大厅坐标
    start_x, start_y = 200, 50

    # 距离计算
    dx = coordinate_x - start_x
    dy = coordinate_y - start_y
    distance = math.sqrt(dx ** 2 + dy ** 2)

    # 步行时间
    walk_minutes = max(1, int(distance / 80))

    # 区域判断
    if coordinate_x < 205:
        area = "西侧区域"
    elif coordinate_x < 215:
        area = "中部区域"
    else:
        area = "东侧区域"

    # 楼层导航方式
    if floor <= 2:
        route_method = "步行楼梯"
    else:
        route_method = "乘坐电梯"

    lines = []

    lines.append(f"📍目标教室：{room_id}（{building}）")
    lines.append("")

    lines.append("🚶建议路线：")
    lines.append(f"进入 {building} 大厅后，建议{route_method}前往 {floor} 楼。")

    if entrance_note:
        lines.append(entrance_note)

    lines.append("")
    lines.append(f"⏱ 预计步行时间：{walk_minutes} 分钟")

    if landmarks:
        lines.append("")
        lines.append("🧭 沿途参照物：")

        for landmark in landmarks:
            lines.append(f"- {landmark}")

    lines.append("")
    lines.append(f"📌 教室位置：{building}{floor}楼{area}")

    return "\n".join(lines)