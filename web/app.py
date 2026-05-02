import sys
import os
import re
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from engine.workflow import run_workflow

app = Flask(__name__)

_pending: dict[str, str] = {}


def _has_participant_count(text: str) -> bool:
    return bool(re.search(r"(\d+)\s*(人|位|名)", text))


def _is_skip_reply(text: str) -> bool:
    return text.strip().lower() in ("跳过", "skip", "不用", "算了", "不填")


def _question_html() -> str:
    return '''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">👥</span>
        <span class="text-sm font-semibold text-gray-200">预计多少人参加？</span>
    </div>
    <p class="text-sm text-gray-300 leading-relaxed mb-3">
        请告诉我预计的参与人数，我会据此推荐合适的教室和预算。<br>
        输入数字即可（如 "50" 或 "50人"），也可以直接说 <span class="text-pink font-semibold">跳过</span>。
    </p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">💡 输入人数 或 回复"跳过"</span>
    </div>
</div>'''


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "请输入您的活动想法~", "success": False})

    sid = data.get("session_id", "")
    if not sid:
        sid = str(uuid.uuid4())[:8]

    # 场景1：用户直接说了包含人数的完整句子 → 直接生成
    if not _is_skip_reply(user_msg) and _has_participant_count(user_msg):
        try:
            result = run_workflow(user_msg)
            return jsonify({"reply": result, "success": True, "session_id": sid})
        except Exception as e:
            return jsonify({
                "reply": f"<div class='bg-red-900/20 border border-red-500/20 text-red-300 px-5 py-3 rounded-2xl text-sm'>出错了: {str(e)}</div>",
                "success": False,
                "session_id": sid,
            })

    # 场景2：用户回复了人数或跳过 → 拼接原始消息再生成
    if sid in _pending:
        original = _pending.pop(sid)
        if _is_skip_reply(user_msg):
            combined = original
        else:
            combined = original + " " + user_msg
        try:
            result = run_workflow(combined)
            return jsonify({"reply": result, "success": True, "session_id": sid})
        except Exception as e:
            return jsonify({
                "reply": f"<div class='bg-red-900/20 border border-red-500/20 text-red-300 px-5 py-3 rounded-2xl text-sm'>出错了: {str(e)}</div>",
                "success": False,
                "session_id": sid,
            })

    # 场景3：用户没提供人数 → 询问一次
    _pending[sid] = user_msg
    return jsonify({
        "reply": _question_html(),
        "success": True,
        "session_id": sid,
    })


if __name__ == "__main__":
    print("=" * 50)
    print("  🎓 Campus Compass 校园活动策划助手")
    print("  浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
