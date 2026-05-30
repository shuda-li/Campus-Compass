import os
import json
import hashlib
from datetime import datetime

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "index.json")


def _ensure_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _load_index() -> dict:
    _ensure_dir()
    if not os.path.exists(MEMORY_INDEX):
        return {"memories": {}, "preferences": {}}
    with open(MEMORY_INDEX, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(idx: dict):
    _ensure_dir()
    with open(MEMORY_INDEX, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def save_memory(session_id: str, key: str, value, source: str = "") -> str:
    """保存一条长期记忆，写 .memory/[hash].json"""
    idx = _load_index()

    memory_id = hashlib.md5(f"{session_id}:{key}".encode()).hexdigest()[:12]

    entry = {
        "session_id": session_id,
        "key": key,
        "value": value,
        "source": source,
        "updated_at": datetime.now().isoformat(),
    }

    file_path = os.path.join(MEMORY_DIR, f"{memory_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

    idx["memories"][memory_id] = {
        "key": key,
        "file": f"{memory_id}.json",
        "updated_at": entry["updated_at"],
    }
    _save_index(idx)
    return memory_id


def save_preference(session_id: str, key: str, value) -> str:
    """保存用户偏好（常用建筑、惯用人数等）"""
    idx = _load_index()
    idx["preferences"][key] = {
        "value": value,
        "session_id": session_id,
        "updated_at": datetime.now().isoformat(),
    }
    _save_index(idx)
    return key


def get_preference(key: str, default=None):
    """读取用户偏好"""
    idx = _load_index()
    entry = idx["preferences"].get(key)
    if entry:
        return entry["value"]
    return default


def load_memory_block() -> str:
    """将所有长期记忆打包为一段可注入 system prompt 的文本"""
    idx = _load_index()
    memories = idx.get("memories", {})
    prefs = idx.get("preferences", {})

    if not memories and not prefs:
        return ""

    lines = ["[Long-term Memories]"]

    if prefs:
        lines.append("用户偏好：")
        for key, entry in prefs.items():
            lines.append(f"  - {key}: {entry['value']}")

    if memories:
        lines.append("历史记录摘要：")
        for mid, meta in list(memories.items())[-5:]:
            file_path = os.path.join(MEMORY_DIR, meta["file"])
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                lines.append(f"  - {entry['key']}: {str(entry['value'])[:200]}")

    return "\n".join(lines)


def auto_remember(plan: dict, intent: dict, participants: int):
    """自动从活动方案中提取值得记住的信息"""
    if not intent:
        return

    building = intent.get("building", "E座")
    activity_type = intent.get("activity_type", "讲座")

    save_preference("_auto", "last_building", building)
    save_preference("_auto", "last_participants", participants)
    save_preference("_auto", "last_activity_type", activity_type)
