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

    sample_data = [
        ("D101", "思源书院D座", 1, 80, 100.0,
         json.dumps(["投影仪", "音响", "空调"], ensure_ascii=False),
         "从D座正门进入直行，一楼大厅右侧第一个门",
         json.dumps(["大厅右侧", "灭火器旁"], ensure_ascii=False),
         100, 50),
        ("D206", "思源书院D座", 2, 60, 75.0,
         json.dumps(["投影仪", "黑板"], ensure_ascii=False),
         "上楼后左转，走廊东侧第二个门",
         json.dumps(["二楼楼梯口左转", "东侧饮水机"], ensure_ascii=False),
         50, 150),
        ("D307", "思源书院D座", 3, 40, 50.0,
         json.dumps(["白板", "空调"], ensure_ascii=False),
         "上三楼后右转，走廊尽头",
         json.dumps(["三楼右转", "走廊尽头"], ensure_ascii=False),
         30, 200),
        ("E301", "知行书院E座", 3, 120, 150.0,
         json.dumps(["投影仪", "音响", "舞台", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到3楼，出电梯后右手边第一个门",
         json.dumps(["三楼电梯口右手边", "大型阶梯教室"], ensure_ascii=False),
         200, 100),
        ("E102", "知行书院E座", 1, 50, 65.0,
         json.dumps(["投影仪", "音响"], ensure_ascii=False),
         "从E座正门进入，左转直行",
         json.dumps(["一楼左转", "自动售货机旁"], ensure_ascii=False),
         220, 80),
        ("F201", "致远楼F座", 2, 90, 110.0,
         json.dumps(["投影仪", "音响", "空调", "视频会议"], ensure_ascii=False),
         "从F座侧门进入，上二楼后直走",
         json.dumps(["F座侧门进", "二楼电梯厅旁"], ensure_ascii=False),
         150, 180),
        ("F403", "致远楼F座", 4, 200, 300.0,
         json.dumps(["投影仪", "音响", "舞台", "灯光", "空调"], ensure_ascii=False),
         "从F座正门乘电梯到4楼，出电梯直行",
         json.dumps(["F座正门", "四楼报告厅"], ensure_ascii=False),
         160, 50),
    ]

    for room in sample_data:
        try:
            cur.execute(
                "INSERT INTO rooms VALUES (?,?,?,?,?,?,?,?,?,?)",
                room
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print("✓ 数据库初始化完成")


if __name__ == "__main__":
    init_database()
