import sqlite3
import json
from config import DB_PATH


def query_rooms(
    capacity_min: int = 30,
    building: str = None,
    required_equipment: list = None,
    max_floor: int = None
) -> list:

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        building = building or "E教学楼"

        query = """
            SELECT * FROM rooms
            WHERE capacity >= ?
            AND building LIKE ?
        """

        params = [capacity_min, f"%{building}%"]

        # 设备筛选
        if required_equipment:
            for eq in required_equipment:
                query += " AND equipment LIKE ?"
                params.append(f"%{eq}%")

        # 楼层筛选
        if max_floor:
            query += " AND floor <= ?"
            params.append(max_floor)

        # 排序：优先容量接近
        query += " ORDER BY capacity ASC"

        # 调试日志
        print(f"[DB] SQL: {query}")
        print(f"[DB] 参数: {params}")

        cur.execute(query, params)

        rows = cur.fetchall()

        conn.close()

        print(f"[DB] 查询到 {len(rows)} 间教室")

        if not rows:
            print("[DB] 未找到符合条件的教室")

        rooms = []

        for row in rows:
            room = dict(row)

            try:
                room["equipment"] = json.loads(
                    room.get("equipment", "[]")
                )
            except:
                room["equipment"] = []

            try:
                room["nav_landmarks"] = json.loads(
                    room.get("nav_landmarks", "[]")
                )
            except:
                room["nav_landmarks"] = []

            rooms.append(room)

        return rooms

    except Exception as e:
        print(f"[DB] 查询失败: {e}")
        return []