import json
import time
import os
from datetime import datetime

TRACE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".traces")


class Trace:
    def __init__(self, session_id: str = ""):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = time.time()
        self.events = []

    def event(self, event_type: str, detail: dict = None):
        entry = {
            "ts": time.time() - self.start_time,
            "type": event_type,
            "detail": detail or {},
        }
        self.events.append(entry)

    def llm_call(self, tokens_in: int, tokens_out: int, tool_calls: int = 0):
        self.event("llm_call", {"tokens_in": tokens_in, "tokens_out": tokens_out, "tool_calls": tool_calls})

    def tool_exec(self, name: str, ok: bool, duration_ms: float = 0):
        self.event("tool_exec", {"name": name, "ok": ok, "duration_ms": round(duration_ms)})

    def nag(self, reason: str):
        self.event("nag", {"reason": reason})

    def dump(self):
        os.makedirs(TRACE_DIR, exist_ok=True)
        filepath = os.path.join(TRACE_DIR, f"{self.session_id}.json")
        report = {
            "session_id": self.session_id,
            "started_at": datetime.now().isoformat(),
            "duration_s": round(time.time() - self.start_time, 1),
            "total_events": len(self.events),
            "events": self.events,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def report(self) -> str:
        llm_calls = sum(1 for e in self.events if e["type"] == "llm_call")
        tool_calls = sum(1 for e in self.events if e["type"] == "tool_exec")
        nags = sum(1 for e in self.events if e["type"] == "nag")
        errors = sum(1 for e in self.events if e["type"] == "error")
        duration = round(time.time() - self.start_time, 1)
        return f"时长:{duration}s LLM调用:{llm_calls} 工具:{tool_calls} 提醒:{nags} 错误:{errors}"
