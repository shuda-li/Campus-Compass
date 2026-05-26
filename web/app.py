import sys
import os
import re
import uuid
import json
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
from engine.topic_analyzer import analyze_topic, expand_topic_via_llm
from engine.plan_generator import generate_plan, call_llm_for_plan
from tools.db_service import query_rooms
from engine.room_scorer import rank_rooms
from tools.navigation import generate_navigation
from agent.formatter import build_html

app = Flask(__name__)

SESSION_FILE = Path(__file__).parent.parent / ".memory" / "web_sessions.json"
_lock = threading.Lock()


def _load_sessions() -> dict:
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_sessions(ss: dict):
    try:
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            SESSION_FILE.write_text(json.dumps(ss, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


sessions: dict[str, dict] = _load_sessions()


def _get_session(sid: str) -> dict:
    if sid not in sessions:
        sessions[sid] = {"step": "ask_topic", "topic": "", "expanded_topic": "", "participants": 0}
    return sessions[sid]


def _ask_topic_html() -> str:
    return '''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📝</span>
        <span class="text-sm font-semibold text-gray-200">请提供您需要策划的活动主题</span>
    </div>
    <p class="text-sm text-gray-300 leading-relaxed mb-3">
        请描述您想举办的活动，可以是简要关键词或详细描述。<br>
        例如：<span class="text-pink">"科技创新活动"</span>、<span class="text-pink">"电脑硬件知识分享会"</span>
    </p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">💡 输入活动主题后按 Enter 发送</span>
    </div>
</div>'''


def _ask_participants_html(topic: str, was_expanded: bool) -> str:
    hint = ""
    if was_expanded:
        hint = f'<p class="text-xs text-pink mb-2">✨ 您的主题已扩展为：<strong>{topic}</strong></p>'
    return f'''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">👥</span>
        <span class="text-sm font-semibold text-gray-200">请问该活动预计参与人数大约是多少？</span>
    </div>
    {hint}
    <p class="text-sm text-gray-300 leading-relaxed mb-3">
        请告诉我预计参与人数，我会据此推荐合适的教室规格。<br>
        输入数字即可（如 <span class="text-pink font-semibold">50</span> 或 <span class="text-pink font-semibold">80人</span>）
    </p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">💡 输入人数后按 Enter</span>
    </div>
</div>'''


def _topic_expand_notice(original: str, expanded: str) -> str:
    return f'''<div class="bg-pinkMuted border border-pink/20 rounded-2xl px-5 py-3 mb-3">
    <p class="text-xs text-pink font-semibold mb-1">🔍 检测到主题较简略，已自动扩展</p>
    <p class="text-xs text-gray-400">"{original}" → <span class="text-pink">"{expanded}"</span></p>
</div>'''


def _venue_recommend_html(rooms: list, participants: int) -> str:
    if not rooms:
        return ""
    top = rooms[0]
    return f'''<div class="bg-darkCard border border-green-500/10 rounded-2xl px-5 py-3 mb-3">
    <div class="flex items-center gap-2 mb-2">
        <span class="text-lg">🏫</span>
        <span class="text-sm font-semibold text-gray-200">场地推荐</span>
    </div>
    <p class="text-xs text-gray-400">
        根据 {participants} 人规模，推荐 <span class="text-pink font-semibold">{top.get("room_id","")}</span>（{top.get("building","")} {top.get("floor","")}F，容纳 {top.get("capacity","")} 人）
    </p>
</div>'''


def _extract_participants(text: str) -> int:
    m = re.search(r"(\d+)\s*(人|位|名)?", text)
    if m:
        return int(m.group(1))
    return 0


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "请提供活动主题~", "success": False})

    sid = data.get("session_id", "")
    if not sid:
        sid = str(uuid.uuid4())[:8]
    state = _get_session(sid)

    # ===== Step 1: 询问主题 → 用户输入主题 =====
    if state["step"] == "ask_topic":
        state["topic"] = user_msg
        state["step"] = "ask_participants"
        _save_sessions(sessions)

        has_llm = bool(LLM_API_KEY)
        expand_fn = (lambda t: expand_topic_via_llm(t, LLM_API_KEY, LLM_API_URL, LLM_MODEL)) if has_llm else None
        result = analyze_topic(user_msg, expand_fn)

        if result["is_simple"] and result["expanded"]:
            state["expanded_topic"] = result["expanded"]
            _save_sessions(sessions)
            notice = _topic_expand_notice(result["original"], result["expanded"])
            question = _ask_participants_html(result["expanded"], True)
            return jsonify({"reply": notice + question, "success": True, "session_id": sid})
        else:
            state["expanded_topic"] = user_msg
            _save_sessions(sessions)
            return jsonify({
                "reply": _ask_participants_html(user_msg, False),
                "success": True,
                "session_id": sid,
            })

    # ===== Step 2: 询问人数 → 用户输入人数 =====
    if state["step"] == "ask_participants":
        participants = _extract_participants(user_msg)
        if participants == 0:
            participants = 30
        state["participants"] = participants
        state["step"] = "ask_details"
        _save_sessions(sessions)

        reply = f'''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📋</span>
        <span class="text-sm font-semibold text-gray-200">确认活动信息</span>
    </div>
    <p class="text-sm text-gray-300 leading-relaxed mb-2">
        主题：<span class="text-pink font-semibold">{state["expanded_topic"] or state["topic"]}</span><br>
        人数：<span class="text-pink font-semibold">{participants}人</span>
    </p>
    <p class="text-xs text-gray-400 mb-3">
        如需补充活动时间、物资清单、人员分工等信息，请直接描述。<br>
        例如：<span class="text-pink">"5月10日下午，需要投影仪和音响"</span><br>
        如果不需要补充，直接回复 <span class="text-pink font-semibold">"生成方案"</span>
    </p>
</div>'''
        return jsonify({"reply": reply, "success": True, "session_id": sid})

    # ===== Step 3: 补充细节（可选）=====
    if state["step"] == "ask_details":
        if any(kw in user_msg for kw in ["生成", "直接生成", "好了", "可以了", "ok", "OK", "下一步", "跳过"]):
            # 用户跳过，直接生成
            pass
        else:
            # 用户提供了细节，用 completeness_checker 评估
            from engine.completeness_checker import AssessmentState, evaluate_completeness, format_complete_html
            assessment = AssessmentState()
            assessment.feed(user_msg)
            result_check = evaluate_completeness(assessment)

            # 保存细节
            state["details"] = state.get("details", "") + "\n" + user_msg
            _save_sessions(sessions)

            if result_check["complete"]:
                return jsonify({
                    "reply": format_complete_html(result_check["collected_summary"]),
                    "success": True,
                    "session_id": sid,
                })
            elif result_check["next_question"]:
                from engine.completeness_checker import format_question_html
                return jsonify({
                    "reply": format_question_html(result_check["next_question"], result_check["collected_summary"]),
                    "success": True,
                    "session_id": sid,
                })

        # 生成方案
        state["step"] = "done"
        _save_sessions(sessions)

        participants = state["participants"]
        topic = state["expanded_topic"] or state["topic"]

        try:
            rooms = query_rooms(capacity_min=participants, building="E教学楼")
            intent = {"building": "E教学楼", "equipment": [], "participants": participants}
            sorted_rooms = rank_rooms(rooms, intent) if rooms else []
            nav = generate_navigation(sorted_rooms[0]) if sorted_rooms else ""

            has_llm = bool(LLM_API_KEY)
            llm_fn = (lambda t, p: call_llm_for_plan(t, p, LLM_API_KEY, LLM_API_URL, LLM_MODEL)) if has_llm else None
            plan = generate_plan(topic, participants, sorted_rooms, llm_fn)

            venue_html = _venue_recommend_html(sorted_rooms, participants)
            plan_html = build_html(plan, sorted_rooms, nav)

            return jsonify({
                "reply": venue_html + plan_html,
                "success": True,
                "session_id": sid,
            })
        except Exception as e:
            return jsonify({
                "reply": f"<div class='bg-red-900/20 border border-red-500/20 text-red-300 px-5 py-3 rounded-2xl text-sm'>生成方案时出错: {str(e)}</div>",
                "success": False,
                "session_id": sid,
            })

   # ===== 已完成：重新开始 =====
    if state["step"] == "done":
        sessions.pop(sid, None)
        _save_sessions(sessions)
        new_state = _get_session(sid)
        new_state["topic"] = user_msg
        has_llm = bool(LLM_API_KEY)
        expand_fn = (lambda t: expand_topic_via_llm(t, LLM_API_KEY, LLM_API_URL, LLM_MODEL)) if has_llm else None
        result = analyze_topic(user_msg, expand_fn)
        if result["is_simple"] and result["expanded"]:
            new_state["expanded_topic"] = result["expanded"]
            new_state["step"] = "ask_participants"
            return jsonify({
                "reply": _topic_expand_notice(result["original"], result["expanded"]) + _ask_participants_html(result["expanded"], True),
                "success": True,
                "session_id": sid,
            })
        else:
            new_state["expanded_topic"] = user_msg
            new_state["step"] = "ask_participants"
            return jsonify({
                "reply": _ask_participants_html(user_msg, False),
                "success": True,
                "session_id": sid,
            })

    return jsonify({"reply": "请提供活动主题~", "success": False, "session_id": sid})


if __name__ == "__main__":
    print("=" * 50)
    print("  🎓 Campus Compass 校园活动策划助手")
    print("  🧠 主题智能处理 + 结构化方案生成")
    print("  浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
