import sqlite3
import json
import os


def init_database(db_path: str = None):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "rooms.db")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            room_id   TEXT PRIMARY KEY,
            building  TEXT NOT NULL,
            floor     INTEGER NOT NULL,
            capacity  INTEGER NOT NULL,
            area      REAL,
            equipment TEXT,
            entrance_note TEXT,
            nav_landmarks  TEXT,
            coordinate_x   INTEGER,
            coordinate_y   INTEGER
        )
    """)

    # 21 间教室（全部 1F，坐标来自拓扑图 map.json，容量为实际数据）
    rooms = [
        # room_id, building, floor, capacity, area, equipment, entrance_note, nav_landmarks, coord_x, coord_y
        ("E101", "E教学楼", 1, 314, 250.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         306, 1034),
        ("E102", "E教学楼", 1, 163, 160.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         414, 940),
        ("E103", "E教学楼", 1, 243, 220.0,
         json.dumps(["投影仪", "音响", "空调", "白板", "模拟法庭"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         565, 941),
        ("E104", "E教学楼", 1, 230, 210.0,
         json.dumps(["投影仪", "音响", "空调", "录播设备", "阶梯录播教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         646, 855),
        ("E105", "E教学楼", 1, 304, 240.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         815, 865),
        ("E107", "E教学楼", 1, 42,  45.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         668, 14),
        ("E108", "E教学楼", 1, 80,  80.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         730, 137),
        ("E109", "E教学楼", 1, 141, 140.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         739, 198),
        ("E110", "E教学楼", 1, 141, 140.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         458, 111),
        ("E115", "E教学楼", 1, 60,  62.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         476, 279),
        ("E116", "E教学楼", 1, 60,  62.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         557, 383),
        ("E117", "E教学楼", 1, 60,  62.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         438, 444),
        ("E119", "E教学楼", 1, 42,  45.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         497, 611),
        ("E120", "E教学楼", 1, 160, 155.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         752, 631),
        ("E124", "E教学楼", 1, 54,  55.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         586, 702),
        ("E126", "E教学楼", 1, 60,  62.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         708, 1058),
        ("E127", "E教学楼", 1, 106, 108.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         482, 1150),
        ("E128", "E教学楼", 1, 105, 108.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         587, 1174),
        ("E129", "E教学楼", 1, 80,  80.0,
         json.dumps(["投影仪", "空调", "普通教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         649, 1315),
        ("E130", "E教学楼", 1, 167, 162.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         694, 1455),
        ("E133", "E教学楼", 1, 160, 155.0,
         json.dumps(["投影仪", "音响", "空调", "阶梯教室"], ensure_ascii=False),
         "", json.dumps(["正门"], ensure_ascii=False),
         99, 1010),

        # ── 体育场馆（不在 E 教学楼内，独立场地）──
        ("体育馆", "体育区", 0, 300, 600.0,
         json.dumps(["室内", "篮球场", "羽毛球", "舞台", "音响", "空调"], ensure_ascii=False),
         "", json.dumps([], ensure_ascii=False),
         900, 500),
        ("田径场", "体育区", 0, 500, 3000.0,
         json.dumps(["户外", "跑道", "草坪", "看台", "音响"], ensure_ascii=False),
         "", json.dumps([], ensure_ascii=False),
         950, 500),

        # ── 电竞机房 ──
        ("E506", "机房区", 5, 100, 120.0,
         json.dumps(["电脑", "投影仪", "空调", "电竞", "100机位"], ensure_ascii=False),
         "", json.dumps([], ensure_ascii=False),
         500, 900),
        ("E507", "机房区", 5, 100, 120.0,
         json.dumps(["电脑", "投影仪", "空调", "电竞", "100机位"], ensure_ascii=False),
         "", json.dumps([], ensure_ascii=False),
         520, 900),
    ]

    for room in rooms:
        cur.execute(
            "INSERT OR IGNORE INTO rooms VALUES (?,?,?,?,?,?,?,?,?,?)",
            room
        )

    conn.commit()
    conn.close()
    print("[OK] 数据库初始化完成（E座 21 间教室 + 2 个体育场馆 + 2 个电竞机房）")


if __name__ == "__main__":
    init_database()
