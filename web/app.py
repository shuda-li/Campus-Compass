import sys
import os
import re
import uuid
import json
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from agent.memory import remember, auto_remember, list_history, load_memory_block
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
from engine.topic_analyzer import analyze_topic, expand_topic_via_llm
from engine.plan_generator import generate_plan, parse_plan_response
from tools.db_service import query_rooms
from engine.room_scorer import rank_rooms
from tools.navigation import generate_navigation
from agent.formatter import build_html
from agent.llm import stream_generate_plan
from agent.skill_loader import load_all_skills

# 启动时初始化数据库（确保教室表存在）
from data.init_db import init_database
init_database()
print("[Web] 数据库已初始化")

app = Flask(__name__)

SESSION_FILE = Path(__file__).parent.parent / ".memory" / "web_sessions.json"
_lock = threading.Lock()


# ── 单主题检测（同一对话不得切换主题）──

def _detect_topic_switch(current_topic: str, new_input: str) -> bool:
    """
    检测用户输入是否疑似切换到新主题。

    策略：
    1. 纯数字/人数输入 → 不是主题切换
    2. 简短的确认/补充用语 → 不是主题切换
    3. 新输入中有「当前主题不存在」的技能专属关键词 → 疑似切换

    核心逻辑：不是看"新输入匹配了哪个技能"，而是看"新输入中出现了
    当前主题没有的异类关键词"。比如"篮球"对于"编程竞赛"就是异类关键词，
    说明用户想切换到运动类活动。
    """
    if not current_topic or not new_input:
        return False

    # 纯数字或人数输入 → 不是新主题
    if re.match(r'^\s*\d+\s*(人|位|名)?\s*$', new_input):
        return False

    # 简短的确认/补充用语 → 不是新主题
    short_lower = new_input.strip().lower()
    if short_lower in ['生成', '直接生成', '好了', '可以了', 'ok', '下一步', '跳过',
                       '是的', '对', '好', '行', '嗯', '没错', '需要', '补充',
                       '生成完整方案', '开始生成', 'go', 'yes', 'y']:
        return False
    if len(short_lower) <= 3:
        return False

    # ── 异类关键词检测 ──
    try:
        available = load_all_skills()

        # 找出当前主题命中了哪些技能（及命中关键词）
        current_skill_name = ""
        current_kw_hits = set()
        for name, skill in available.items():
            kw_list = skill.get("keywords", [])
            hits = {k for k in kw_list if k in current_topic}
            if hits:
                current_skill_name = name
                current_kw_hits = hits
                break  # 取第一个匹配的即可

        if not current_skill_name:
            # 当前主题无关键词命中 → 反向判断：新输入如果有活动关键词 → 可能是新主题
            for name, skill in available.items():
                kw_list = skill.get("keywords", [])
                for kw in kw_list:
                    if kw in new_input:
                        return True
            return False

        # 统计新输入在当前技能 vs 其他技能中的关键词命中
        current_skill_kw = available.get(current_skill_name, {}).get("keywords", [])
        current_hit_count = sum(1 for k in current_skill_kw if k in new_input)
        cross_alien_count = 0
        for name, skill in available.items():
            if name == current_skill_name:
                continue
            for kw in skill.get("keywords", []):
                if kw in new_input and kw not in current_kw_hits:
                    cross_alien_count += 1

        # 判定规则：
        # A) 跨技能异类词 ≥2 → 强烈信号（如 篮球+比赛 → 运动类）
        # B) 跨技能异类词 ≥1 且当前技能命中 = 0 且异类词长度≥3 → 主题无关
        #    （排除"分享""讨论"等短词误判；"摄影展"长度=3 可触发）
        # C) 同技能内新关键词 ≥1 → Python→Java 类切换
        if cross_alien_count >= 2:
            return True
        # 重新计算：只计长度≥3的异类词（避免"分享""讨论"等常见短词误判）
        long_alien_count = 0
        for name, skill in available.items():
            if name == current_skill_name:
                continue
            for kw in skill.get("keywords", []):
                if kw in new_input and kw not in current_kw_hits and len(kw) >= 3:
                    long_alien_count += 1
        if long_alien_count >= 1 and current_hit_count == 0:
            return True

        new_hits_in_same = [k for k in current_skill_kw if k in new_input]
        alien_in_same = [k for k in new_hits_in_same if k not in current_kw_hits]
        if len(alien_in_same) >= 1:
            return True

    except Exception:
        pass

    return False


def _topic_switch_warning() -> str:
    """新主题警告消息 HTML。"""
    return '''<div class="bg-amber-900/20 border border-amber-500/30 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-2">
        <span class="text-lg">⚠️</span>
        <span class="text-sm font-semibold text-amber-300">同一个对话多个主题可能会内容混淆！</span>
    </div>
    <p class="text-xs text-gray-400 leading-relaxed">
        请围绕当前主题继续完善方案。如需策划新主题，请点击侧边栏 <span class="text-pink font-semibold">"＋ 新对话"</span> 创建全新的对话。
    </p>
</div>'''


def _is_valid_topic(text: str) -> bool:
    """校验主题是否有效（非空、非占位符、非系统指令）。"""
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    # 系统占位符
    if t in ['_stream_done_', '_placeholder_', 'undefined', 'null', 'none']:
        return False
    # 过短（单字不成主题）
    if len(t) <= 1:
        return False
    return True


def _invalid_topic_html() -> str:
    """无效主题提示 HTML。"""
    return '''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📝</span>
        <span class="text-sm font-semibold text-gray-200">请提供您需要策划的活动主题</span>
    </div>
    <p class="text-sm text-gray-300 leading-relaxed mb-2">
        请输入有效的活动主题，我会帮您策划完整的活动方案。
    </p>
    <p class="text-xs text-gray-400">
        例如：<span class="text-pink">"50人的Python编程竞赛"</span>、<span class="text-pink">"AI技术讲座"</span>、<span class="text-pink">"校园篮球比赛"</span>
    </p>
</div>'''


def _review_hint_html(topic: str) -> str:
    """方案已生成后的改进引导 HTML。"""
    return f'''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-3 mt-3">
    <p class="text-xs text-gray-400">
        📋 当前主题：<span class="text-pink font-semibold">{topic}</span>
    </p>
    <p class="text-xs text-gray-500 mt-1">
        💡 你可以输入改进需求来调整方案（如"换大一点的教室"、"增加互动环节"等）
    </p>
</div>'''


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
        sessions[sid] = {
            "step": "ask_topic",
            "topic": "",
            "expanded_topic": "",
            "participants": 0,
            "proxy_enabled": False,
            "proxy_address": "",
        }
    return sessions[sid]


def _apply_proxy(state: dict):
    from agent.proxy import set_proxy, clear_proxy
    if state.get("proxy_enabled", False) and state.get("proxy_address"):
        set_proxy(state["proxy_address"])
    else:
        clear_proxy()


def _save_to_memory(sid: str, topic: str, plan: dict, intent: dict, participants: int):
    try:
        remember(sid, topic, intent, plan, {}, [], "")
    except Exception as e:
        print(f"[Memory] L1/L2 save failed: {e}")
    try:
        auto_remember(plan, intent, participants)
    except Exception as e:
        print(f"[Memory] L3 save failed: {e}")


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


@app.route("/api/proxy", methods=["GET", "POST"])
def proxy_config():
    if request.method == "GET":
        sid = request.args.get("session_id", "")
        if sid and sid in sessions:
            state = sessions[sid]
            return jsonify({
                "enabled": state.get("proxy_enabled", False),
                "address": state.get("proxy_address", ""),
            })
        return jsonify({
            "enabled": False,
            "address": "",
        })

    data = request.get_json() or {}
    sid = data.get("session_id", "")
    if sid and sid in sessions:
        state = sessions[sid]
        if "enabled" in data:
            state["proxy_enabled"] = bool(data["enabled"])
        if "address" in data:
            state["proxy_address"] = data["address"].strip()
        _save_sessions(sessions)
        return jsonify({
            "success": True,
            "enabled": state["proxy_enabled"],
            "address": state["proxy_address"],
        })
    return jsonify({"success": True, "message": "no session, saved locally"})


@app.route("/api/proxy/test", methods=["POST"])
def proxy_test():
    data = request.get_json() or {}
    address = data.get("address", "").strip()
    if not address:
        return jsonify({"success": False, "message": "代理地址不能为空"})

    from agent.proxy import validate
    ok, msg = validate(address)
    return jsonify({"success": ok, "message": msg})


@app.route("/api/history")
def api_history():
    limit = request.args.get("limit", 10, type=int)
    items = list_history(limit)
    return jsonify({"success": True, "items": items})


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
    _apply_proxy(state)

    if state["step"] == "ask_topic":
        # ── 主题有效性校验 ──
        if not _is_valid_topic(user_msg):
            return jsonify({
                "reply": _invalid_topic_html(),
                "success": True,
                "session_id": sid,
            })

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

    if state["step"] == "ask_participants":
        # ── 单主题检测：如果用户输入疑似新主题而非人数 → 警告 ──
        if _detect_topic_switch(state.get("expanded_topic") or state["topic"], user_msg):
            return jsonify({
                "reply": _topic_switch_warning() + _ask_participants_html(state["expanded_topic"] or state["topic"], False),
                "success": True,
                "session_id": sid,
            })

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
    <p class="text-xs text-gray-400 mb-0">
        如需补充活动时间、物资清单、人员分工等信息，请直接描述。<br>
        例如：<span class="text-pink">"5月10日下午，需要投影仪和音响"</span>
    </p>
    <p class="text-xs text-gray-400">
        如果不需要补充，请点击下方按钮：
    </p>
    <button onclick="generatePlanNow()"
                        class="mt-3 w-full py-2.5 bg-pink/15 border border-pink/30 text-pink text-sm font-medium rounded-xl hover:bg-pink/20 hover:border-pink/50 active:scale-[0.98] transition-all flex items-center justify-center gap-2">
                        <i class="fa fa-magic"></i>
                        生成完整方案
                    </button>
</div>'''
        return jsonify({"reply": reply, "success": True, "session_id": sid})

    if state["step"] == "ask_details":
        # ── 单主题检测：如果用户输入疑似新主题 → 警告 ──
        if _detect_topic_switch(state.get("expanded_topic") or state["topic"], user_msg):
            return jsonify({
                "reply": _topic_switch_warning(),
                "success": True,
                "session_id": sid,
            })

        if any(kw in user_msg for kw in ["生成", "直接生成", "好了", "可以了", "ok", "OK", "下一步", "跳过"]):
            pass
        else:
            from engine.completeness_checker import AssessmentState, evaluate_completeness, format_complete_html
            assessment = AssessmentState()
            assessment.feed(user_msg)
            result_check = evaluate_completeness(assessment)

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

        state["step"] = "streaming"
        _save_sessions(sessions)

        return jsonify({
            "success": True,
            "session_id": sid,
            "stream": True,
            "topic": state["expanded_topic"] or state["topic"],
            "participants": state["participants"],
        })

    if state["step"] == "streaming":
        state["step"] = "review"
        _save_sessions(sessions)
        return jsonify({"success": True, "session_id": sid, "stream_done": True})

    if state["step"] == "review":
        # _stream_done_ 是内部状态转换信号，直接忽略
        if user_msg == "_stream_done_":
            return jsonify({"success": True, "session_id": sid, "stream_done": True})

        # ── 单主题检测：方案已生成，禁止切换主题 ──
        if _detect_topic_switch(state.get("expanded_topic") or state["topic"], user_msg):
            return jsonify({
                "reply": _topic_switch_warning() + _review_hint_html(state["expanded_topic"] or state["topic"]),
                "success": True,
                "session_id": sid,
            })

        # 用户提供了改进反馈 → 回到 ask_details 状态，纳入补充信息
        state["details"] = state.get("details", "") + "\n[改进需求] " + user_msg
        state["step"] = "streaming"
        _save_sessions(sessions)

        return jsonify({
            "success": True,
            "session_id": sid,
            "stream": True,
            "topic": state["expanded_topic"] or state["topic"],
            "participants": state["participants"],
        })

    return jsonify({"reply": "请提供活动主题~", "success": False, "session_id": sid})


@app.route("/chat/stream")
def chat_stream():
    sid = request.args.get("session_id", "")
    if not sid or sid not in sessions:
        return Response("data: {\"error\": \"session not found\"}\n\n", mimetype="text/event-stream")

    state = sessions[sid]
    if state.get("step") != "streaming":
        return Response("data: {\"error\": \"not in streaming state\"}\n\n", mimetype="text/event-stream")

    _apply_proxy(state)

    topic = state.get("expanded_topic") or state.get("topic", "")
    participants = state.get("participants", 30)

    def generate():
        from agent.llm import stream_generate_plan
        from engine.plan_generator import _ultimate_fallback

        try:
            full_text = ""
            for event in stream_generate_plan(topic, participants):
                if event["type"] == "chunk":
                    full_text = event["full"]
                    yield f"data: {json.dumps({'type': 'chunk', 'text': event['text']})}\n\n"
                elif event["type"] == "done":
                    full_text = event["text"]
                    break

            try:
                plan = parse_plan_response(full_text)
            except Exception as parse_e:
                print(f"[ChatStream] 解析LLM响应失败，使用兜底方案: {parse_e}")
                plan = _ultimate_fallback(topic, participants)
        except Exception as stream_e:
            # LLM 流式调用失败（网络/API 错误）→ 降级为兜底方案
            print(f"[ChatStream] LLM流式调用失败，使用兜底方案: {stream_e}")
            full_text = ""
            plan = _ultimate_fallback(topic, participants)

        try:
            rooms = query_rooms(capacity_min=participants, building="E教学楼")
            intent = {"building": "E教学楼", "equipment": [], "participants": participants}
            sorted_rooms = rank_rooms(rooms, intent) if rooms else []
            nav = generate_navigation(sorted_rooms[0]) if sorted_rooms else []

            venue_html = _venue_recommend_html(sorted_rooms, participants)
            plan_html = build_html(plan, sorted_rooms, nav)

            state["step"] = "review"
            _save_sessions(sessions)

            _save_to_memory(sid, topic, plan, intent, participants)

            yield f"data: {json.dumps({'type': 'done', 'html': venue_html + plan_html, 'plan': plan})}\n\n"
        except Exception as e:
            print(f"[ChatStream] 后续处理错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': '方案生成后处理出错，请重试'})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    # Windows 终端默认 GBK 编码不支持 emoji，强制 UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 50)
    print("  🎓 Campus Compass 校园活动策划助手")
    print("  🧠 主题智能处理 + 结构化方案生成")
    print("  浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
