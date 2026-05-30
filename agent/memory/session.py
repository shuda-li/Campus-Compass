import re
import json
import os
import sqlite3
from datetime import datetime


HISTORY_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "history.db")

# ============ L1: 内存短期记忆 ============
_recent: dict[str, dict] = {}


def remember(session_id: str, raw_input: str, intent: dict, plan: dict, budget: dict,
             rooms: list, navigation: str):
    """L1: 记住当前策划结果"""
    record = {
        "raw_input": raw_input,
        "intent": intent,
        "plan": plan,
        "budget": budget,
        "rooms": rooms[:3],
        "navigation": navigation,
    }
    _recent[session_id] = record

    try:
        _save_to_history(session_id, raw_input, plan)
    except Exception:
        pass


def recall(session_id: str) -> dict:
    """L1: 回忆最近一次策划结果"""
    return _recent.get(session_id, {})


def list_history(limit: int = 10) -> list:
    """L2: 查询历史策划列表"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        _ensure_history_table(cur)
        cur.execute(
            "SELECT id, session_id, raw_input, plan_title, created_at FROM history ORDER BY id DESC LIMIT ?",
            [limit],
        )
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_history_by_id(history_id: int) -> dict:
    """L2: 按 ID 获取历史策划完整内容"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        _ensure_history_table(cur)
        cur.execute("SELECT * FROM history WHERE id = ?", [history_id])
        row = cur.fetchone()
        conn.close()
        if row:
            return dict(row)
        return {}
    except Exception:
        return {}


# ============ 编辑意图识别 ============
EDIT_KEYWORDS = [
    "换成", "换到", "改成", "改为", "改到",
    "不要", "去掉", "删掉", "别要",
    "加上", "再加", "补充", "增加",
    "重新", "再来", "撤消",
]


def is_edit_request(text: str) -> bool:
    """判断用户是否想修改之前的方案"""
    return any(kw in text for kw in EDIT_KEYWORDS)


def merge_edit(session_id: str, edit_msg: str) -> str:
    """
    将编辑指令与上次策划的原始输入合并，生成新的完整输入。
    例：
      上次: "我想办一个50人的技术讲座"
      编辑: "换成D座，人数改成80"
      输出: "我想办一个80人的技术讲座，要求在D座"
    """
    prev = recall(session_id)
    if not prev:
        return edit_msg

    original = prev.get("raw_input", "")
    intent = prev.get("intent", {})
    new_text = edit_msg

    num_match = re.search(r"(\d+)\s*(人|位|名)", new_text)
    if num_match:
        new_count = num_match.group(1)
        original = re.sub(r"(\d+)\s*人", f"{new_count}人", original)

    keywords_map = {"E座": "E座"}
    for kw, bld in keywords_map.items():
        if kw in new_text:
            original = re.sub(r"在?\s*[A-Z]座", f"在{bld}", original)
            if "在" not in original:
                original = original.rstrip() + f" 在{bld}"

    equipment_keywords = ["投影", "音响", "灯光", "舞台", "麦克风", "空调", "白板", "黑板"]
    if any(k in new_text for k in ["不要", "去掉", "删掉"]):
        for eq in equipment_keywords:
            if eq in new_text:
                original = re.sub(rf"(、?{eq}\s*)", "", original)

    if any(k in new_text for k in ["加上", "再加", "补充", "增加"]):
        for eq in equipment_keywords:
            if eq in new_text and eq not in original:
                if "需要" in original:
                    original = original.rstrip() + f"、{eq}"
                else:
                    original = original.rstrip() + f" 需要{eq}"

    combined = original + "（补充要求：" + new_text + "）"
    return combined


def _save_to_history(session_id: str, raw_input: str, plan: dict):
    """L2: 持久化到 SQLite"""
    os.makedirs(os.path.dirname(HISTORY_DB), exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    cur = conn.cursor()
    _ensure_history_table(cur)
    cur.execute(
        "INSERT INTO history (session_id, raw_input, plan_title, plan_json, created_at) VALUES (?,?,?,?,?)",
        [session_id, raw_input, plan.get("activity_topic", plan.get("title", "")), json.dumps(plan, ensure_ascii=False),
         datetime.now().isoformat()],
    )
    conn.commit()
    conn.close()


def _ensure_history_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            raw_input TEXT,
            plan_title TEXT,
            plan_json TEXT,
            created_at TEXT
        )
    """)
