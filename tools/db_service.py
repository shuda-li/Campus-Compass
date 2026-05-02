import sqlite3
import json
from config import DB_PATH


def query_rooms(capacity_min: int = 30, building: str = None) -> list:
    """查询符合条件的教室，返回字典列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        query = "SELECT * FROM rooms WHERE capacity >= ?"
        params = [capacity_min]

        if building:
            query += " AND building LIKE ?"
            params.append(f"%{building}%")

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        rooms = []
        for row in rows:
            room = dict(row)
            try:
                room["equipment"] = json.loads(room.get("equipment", "[]"))
            except (json.JSONDecodeError, TypeError):
                room["equipment"] = []
            try:
                room["nav_landmarks"] = json.loads(room.get("nav_landmarks", "[]"))
            except (json.JSONDecodeError, TypeError):
                room["nav_landmarks"] = []
            rooms.append(room)

        return rooms
    except Exception as e:
        print(f"[DB] 查询失败: {e}")
        return []


def get_room_by_id(room_id: str) -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM rooms WHERE room_id = ?", [room_id])
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return {}
    except Exception as e:
        print(f"[DB] 查询失败: {e}")
        return {}
