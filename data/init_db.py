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

    rooms = [
        ("E101", "E教学楼", 1, 40, 55.0,
         json.dumps(["投影仪", "黑板", "空调"], ensure_ascii=False),
         "从E座正门进入，左转直行，走廊第一间",
         json.dumps(["E座正门", "一楼左转"], ensure_ascii=False),
         200, 60),
        ("E102", "E教学楼", 1, 60, 75.0,
         json.dumps(["投影仪", "音响", "空调"], ensure_ascii=False),
         "从E座正门进入，左转直行，走廊第二间",
         json.dumps(["E座正门", "一楼左转", "自动售货机旁"], ensure_ascii=False),
         205, 60),
        ("E103", "E教学楼", 1, 80, 100.0,
         json.dumps(["投影仪", "音响", "空调", "白板"], ensure_ascii=False),
         "从E座正门进入，直行至大厅，右侧第一个门",
         json.dumps(["E座正门", "一楼大厅"], ensure_ascii=False),
         210, 55),
        ("E201", "E教学楼", 2, 50, 65.0,
         json.dumps(["投影仪", "黑板"], ensure_ascii=False),
         "从E座大厅上楼，二楼左转第一间",
         json.dumps(["E座大厅", "二楼左转"], ensure_ascii=False),
         200, 100),
        ("E202", "E教学楼", 2, 70, 90.0,
         json.dumps(["投影仪", "音响", "白板", "空调"], ensure_ascii=False),
         "从E座大厅上楼，二楼直行，右侧第二间",
         json.dumps(["E座大厅", "二楼直行"], ensure_ascii=False),
         205, 100),
        ("E203", "E教学楼", 2, 100, 130.0,
         json.dumps(["投影仪", "音响", "空调", "视频会议"], ensure_ascii=False),
         "从E座大厅上楼，二楼右转，走廊尽头",
         json.dumps(["E座大厅", "二楼右转", "饮水机旁"], ensure_ascii=False),
         215, 100),
        ("E301", "E教学楼", 3, 80, 100.0,
         json.dumps(["投影仪", "音响", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到3楼，出电梯后右手边第一间",
         json.dumps(["E座大厅电梯", "三楼电梯口"], ensure_ascii=False),
         200, 150),
        ("E302", "E教学楼", 3, 120, 160.0,
         json.dumps(["投影仪", "音响", "舞台", "灯光", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到3楼，出电梯后直行左转",
         json.dumps(["E座大厅电梯", "三楼直行左转", "大型阶梯教室"], ensure_ascii=False),
         210, 150),
        ("E303", "E教学楼", 3, 50, 60.0,
         json.dumps(["投影仪", "白板", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到3楼，出电梯后右转走廊第三间",
         json.dumps(["E座大厅电梯", "三楼右转"], ensure_ascii=False),
         215, 155),
        ("E304", "E教学楼", 3, 45, 55.0,
         json.dumps(["白板", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到3楼，出电梯后左转走廊尽头",
         json.dumps(["E座大厅电梯", "三楼左转", "走廊尽头"], ensure_ascii=False),
         220, 145),
        ("E401", "E教学楼", 4, 150, 200.0,
         json.dumps(["投影仪", "音响", "舞台", "灯光", "空调", "视频会议"], ensure_ascii=False),
         "从E座大厅乘电梯到4楼，出电梯直行",
         json.dumps(["E座大厅电梯", "四楼报告厅"], ensure_ascii=False),
         205, 200),
        ("E402", "E教学楼", 4, 60, 80.0,
         json.dumps(["投影仪", "音响", "空调"], ensure_ascii=False),
         "从E座大厅乘电梯到4楼，出电梯后右转",
         json.dumps(["E座大厅电梯", "四楼右转"], ensure_ascii=False),
         215, 200),
    ]

    for room in rooms:
        try:
            cur.execute(
                "INSERT INTO rooms VALUES (?,?,?,?,?,?,?,?,?,?)",
                room
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print("✓ 数据库初始化完成（E座 12 间教室）")


if __name__ == "__main__":
    init_database()
