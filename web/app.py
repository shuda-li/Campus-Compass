import sys
import os
import re
import uuid
import json
import threading
from pathlib import Path

# ── Windows 终端 UTF-8 乱码修复 ──
# 强制 stdout/stderr 使用 UTF-8，避免中文输出在 GBK 终端下显示为乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from agent.memory import remember, auto_remember, list_history, load_memory_block
from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
from engine.topic_analyzer import analyze_topic, expand_topic_via_llm
from engine.plan_generator import generate_plan, parse_plan_response
from tools.db_service import query_rooms
from engine.room_selector import select_best_rooms
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
                       '生成完整方案', '开始生成', 'go', 'yes', 'y','生成方案','走','继续']:
        return False

    # 明确换题意向短语 → 直接判定为换题
    if any(phrase in short_lower for phrase in [
        '换个主题', '换个话题', '换一个主题', '换一个话题',
        '重新开始', '新主题', '新话题', '新的活动',
        '新建对话', '新对话', '换个活动',
        '不聊这个', '换一个', '重来',
    ]):
        return True

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
    return '''<div class="bg-amberMuted border border-amberWarn/30 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-2">
        <span class="text-lg">⚠️</span>
        <span class="text-sm font-semibold text-amber">同一个对话多个主题可能会内容混淆！</span>
    </div>
    <p class="text-xs text-stardust leading-relaxed">
        请围绕当前主题继续完善方案。如需策划新主题，请点击侧边栏 <span class="text-nebula font-semibold">"＋ 新对话"</span> 创建全新的对话。
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
    return '''<div class="glass-panel rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📝</span>
        <span class="text-sm font-semibold text-starlight">请提供您需要策划的活动主题</span>
    </div>
    <p class="text-sm text-starlight leading-relaxed mb-2">
        请输入有效的活动主题，我会帮您策划完整的活动方案。
    </p>
    <p class="text-xs text-stardust">
        例如：<span class="text-nebula">"50人的Python编程竞赛"</span>、<span class="text-nebula">"AI技术讲座"</span>、<span class="text-nebula">"校园篮球比赛"</span>
    </p>
</div>'''


def _review_hint_html(topic: str) -> str:
    """方案已生成后的改进引导 HTML。"""
    return f'''<div class="glass-panel rounded-2xl px-5 py-3 mt-3">
    <p class="text-xs text-stardust">
        📋 当前主题：<span class="text-nebula font-semibold">{topic}</span>
    </p>
    <p class="text-xs text-stardust mt-1">
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
            "temperature": 0.8,
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
        remember(sid, topic, intent, plan, {}, [])
    except Exception as e:
        print(f"[Memory] L1/L2 save failed: {e}")
    try:
        auto_remember(plan, intent, participants)
    except Exception as e:
        print(f"[Memory] L3 save failed: {e}")


def _ask_topic_html() -> str:
    return '''<div class="glass-panel rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📝</span>
        <span class="text-sm font-semibold text-starlight">请提供您需要策划的活动主题</span>
    </div>
    <p class="text-sm text-starlight leading-relaxed mb-3">
        请描述您想举办的活动，可以是简要关键词或详细描述。<br>
        例如：<span class="text-nebula">"科技创新活动"</span>、<span class="text-nebula">"电脑硬件知识分享会"</span>
    </p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-stardust">💡 输入活动主题后按 Enter 发送</span>
    </div>
</div>'''


def _ask_participants_html(topic: str, was_expanded: bool) -> str:
    hint = ""
    if was_expanded:
        hint = f'<p class="text-xs text-nebula mb-2">✨ 您的主题已扩展为：<strong>{topic}</strong></p>'
    return f'''<div class="glass-panel rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">👥</span>
        <span class="text-sm font-semibold text-starlight">请问该活动预计参与人数大约是多少？</span>
    </div>
    {hint}
    <p class="text-sm text-starlight leading-relaxed mb-3">
        请告诉我预计参与人数，我会据此推荐合适的教室规格。<br>
        输入数字即可（如 <span class="text-nebula font-semibold">50</span> 或 <span class="text-nebula font-semibold">80人</span>）
    </p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-stardust">💡 输入人数后按 Enter</span>
    </div>
</div>'''


def _topic_expand_notice(original: str, expanded: str) -> str:
    return f'''<div class="bg-nebulaMuted border border-nebula/25 rounded-2xl px-5 py-3 mb-3">
    <p class="text-xs text-nebula font-semibold mb-1">🔍 检测到主题较简略，已自动扩展</p>
    <p class="text-xs text-stardust">"{original}" → <span class="text-nebula">"{expanded}"</span></p>
</div>'''


def _venue_recommend_html(rooms: list, participants: int) -> str:
    if not rooms:
        return '<div class="glass-panel border border-amberWarn/10 rounded-2xl px-5 py-3 mb-3"><p class=\"text-xs text-amberWarn\">⚠️ 暂无可匹配教室</p></div>'

    def _room_type(r: dict) -> str:
        """从 equipment 数组中提取教室类型。"""
        equip = r.get("equipment", "[]")
        if isinstance(equip, str):
            try:
                equip = json.loads(equip)
            except Exception:
                equip = []
        for e in equip:
            if "教室" in e or "法庭" in e:
                return e
        return ""

    top = rooms[0]
    top_type = _room_type(top)
    fill_pct = f"{participants / top['capacity'] * 100:.0f}%"
    score = top.get("_score", 0)
    fill_s = top.get("_fill_score", 0)
    dist_s = top.get("_distance_score", 0)
    wdist = top.get("_weighted_dist", "?")

    # 备选（第2、3名）
    alts = ""
    for i, r in enumerate(rooms[1:4]):
        if i >= 2:
            break
        alt_fill = f"{participants / r['capacity'] * 100:.0f}%"
        alt_score = r.get("_score", 0)
        alt_type = _room_type(r)
        alt_type_str = f" · {alt_type}" if alt_type else ""
        alts += '<span class="text-xs text-stardust">'
        alts += f' · {r["room_id"]}（{r["capacity"]}人, {alt_fill}{alt_type_str}, {alt_score:.0f}分）'
        alts += '</span>'

    type_badge = f'<span class="text-xs bg-nebula/10 text-nebula px-2 py-0.5 rounded-full ml-2">{top_type}</span>' if top_type else ''

    return f'''<div class="glass-panel border border-greenOk/10 rounded-2xl px-5 py-3 mb-3">
    <div class="flex items-center gap-2 mb-2">
        <span class="text-lg">🏫</span>
        <span class="text-sm font-semibold text-starlight">场地推荐</span>
        <span class="text-xs text-stardust ml-auto">填充率 50% + 距离 50%</span>
    </div>
    <p class="text-xs text-stardust">
        推荐 <span class="text-nebula font-semibold">{top.get("room_id","")}</span>{type_badge}（{top.get("capacity","")}人，填充{fill_pct}，总分{score:.0f}）
    </p>
    <p class="text-xs text-stardust mt-1">
        填充分 {fill_s:.0f}/50 · 距离分 {dist_s:.0f}/50{alts}
    </p>
</div>'''


def _extract_participants(text: str) -> int:
    """
    从用户输入中提取参与人数。

    规则（按优先级）：
    1. 数字 + 人/位/名 → 明确人数，如 "30人"、"50位"
    2. 单独数字且后面不跟日期单位 → 可能是人数，如 "30"、"50"
    3. 数字 + 年/月/日/号/点/时/分 → 日期/时间，忽略，如 "27年"、"5月"、"1号"
    """
    # 规则1：明确带人数单位
    m = re.search(r"(\d+)\s*(人|位|名)", text)
    if m:
        return int(m.group(1))

    # 规则2+3：提取所有数字及其上下文，过滤日期
    for m in re.finditer(r"(\d+)", text):
        num = int(m.group(1))
        if num > 500:  # 不可能的活动人数
            continue
        # 检查数字后紧跟的字符
        after = text[m.end():m.end() + 2]
        if after and after[0] in "年月日号点时秒分":
            continue  # 日期/时间，跳过
        if after and after[:2] in ["年", "月", "日"]:
            continue
        return num

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
    temperature = float(data.get("temperature", 0.8))
    if not user_msg:
        return jsonify({"reply": "请提供活动主题~", "success": False})

    sid = data.get("session_id", "")
    if not sid:
        sid = str(uuid.uuid4())[:8]
    state = _get_session(sid)
    if temperature:
        state["temperature"] = temperature
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

        reply = f'''<div class="glass-panel rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📋</span>
        <span class="text-sm font-semibold text-starlight">确认活动信息</span>
    </div>
    <p class="text-sm text-starlight leading-relaxed mb-2">
        主题：<span class="text-nebula font-semibold">{state["expanded_topic"] or state["topic"]}</span><br>
        人数：<span class="text-nebula font-semibold">{participants}人</span>
    </p>
    <p class="text-xs text-stardust mb-0">
        如需补充活动时间、物资清单、人员分工等信息，请直接描述。<br>
        例如：<span class="text-nebula">"5月10日下午，需要投影仪和音响"</span>
    </p>
    <p class="text-xs text-stardust">
        如果不需要补充，请点击下方按钮：
    </p>
    <button onclick="generatePlanNow()"
                        class="mt-3 w-full py-2.5 bg-nebulaMuted border border-nebula/30 text-nebula text-sm font-medium rounded-xl hover:bg-nebula/15 hover:border-nebula/40 hover:shadow-[0_0_12px_rgba(139,92,246,0.2)] active:scale-[0.98] transition-all flex items-center justify-center gap-2">
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

        # ── Phase 1: 关键词锚定（Plan-Aware）──
        from engine.plan_anchor import anchor_feedback, derive_intent_from_anchors
        last_plan = state.get("last_plan")
        anchors = anchor_feedback(last_plan, user_msg) if last_plan else []
        if anchors:
            anchor_labels = [f"{a['keyword']}→{a['section']}[{a.get('index','')}].{a.get('field','')}" for a in anchors[:5]]
            print(f"[Web] 关键词锚定: {', '.join(anchor_labels)}")
            state["anchors"] = anchors
            anchor_intents = derive_intent_from_anchors(anchors)
        else:
            anchor_intents = []
            state["anchors"] = None

        # ── Phase 2: 通用修改意图检测（时间/场地/人数/预算）──
        from engine.intent_detector import detect_intent
        general_intents = detect_intent(user_msg)

        # 合并 intent：锚定优先，通用检测补充
        merged_intents = anchor_intents.copy()
        seen_types = {i["type"] for i in merged_intents}
        for gi in general_intents:
            if gi["type"] not in seen_types:
                merged_intents.append(gi)
                seen_types.add(gi["type"])

        if merged_intents:
            state["active_intents"] = merged_intents
            labels = [f"{i['type']}={i['value']}" for i in merged_intents]
            print(f"[Web] 合并修改意图: {', '.join(labels)}")
        else:
            state["active_intents"] = None

        # ── 单主题检测：锚定和意图都失败时才触发 ──
        # 有锚定 → 确认是改进反馈；有意图 → 可能是改进
        # 两者都没有 → 疑似换题，警告
        if not anchors and not merged_intents:
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
    temperature = state.get("temperature", 0.8)
    active_intents = state.get("active_intents")  # 用户修改意图列表
    anchors = state.get("anchors")                 # 关键词锚定结果
    last_plan = state.get("last_plan")             # 上次生成的 plan

    def generate():
        from agent.llm import stream_generate_plan
        from engine.plan_generator import _ultimate_fallback

        try:
            full_text = ""
            for event in stream_generate_plan(topic, participants, temp=temperature,
                                               active_intents=active_intents,
                                               anchors=anchors, last_plan=last_plan):
                if event["type"] == "chunk":
                    full_text = event["full"]
                    yield f"data: {json.dumps({'type': 'chunk', 'text': event['text']})}\n\n"
                elif event["type"] == "done":
                    full_text = event["text"]
                    break

            try:
                plan = parse_plan_response(full_text)
                print(f"[ChatStream] Plan 解析成功, phases={len(plan.get('activity_content',[]))}, "
                      f"materials={len(plan.get('activity_materials',[]))}, "
                      f"purpose_len={len(plan.get('activity_purpose',''))}")
            except Exception as parse_e:
                # 打印 full_text 的头尾各 200 字符，方便排查 LLM 输出了什么
                head = full_text[:200] if full_text else "(empty)"
                tail = full_text[-200:] if full_text and len(full_text) > 200 else ""
                print(f"[ChatStream] 解析LLM响应失败: {parse_e}")
                print(f"[ChatStream] full_text 头: {head}")
                if tail:
                    print(f"[ChatStream] full_text 尾: {tail}")
                plan = _ultimate_fallback(topic, participants)
                print(f"[ChatStream] 使用兜底方案, phases={len(plan.get('activity_content',[]))}")
        except Exception as stream_e:
            # LLM 流式调用失败（网络/API 错误）→ 降级为兜底方案
            print(f"[ChatStream] LLM流式调用失败，使用兜底方案: {stream_e}")
            full_text = ""
            plan = _ultimate_fallback(topic, participants)

        try:
            # 场地路由：电竞→机房区，体育→体育区，其他→E教学楼
            try:
                from agent.skill_loader import match_skill
                skill_name, _ = match_skill(topic)
                if skill_name == "sports_planning":
                    topic_lower = topic.lower()
                    if any(kw in topic_lower for kw in [
                        "电竞", "电子竞技", "电竞赛", "游戏赛", "游戏竞技", "游戏竞赛",
                        "网游", "端游", "手游", "主机游戏", "电竞联赛", "电竞挑战", "电竞杯",
                        "lol", "英雄联盟", "dota", "csgo", "cs2", "王者荣耀", "吃鸡",
                        "绝地求生", "pubg", "守望先锋", "overwatch", "炉石传说", "星际争霸",
                        "魔兽争霸", "valorant", "瓦罗兰特", "apex", "永劫无间", "原神",
                        "崩坏", "星穹铁道", "第五人格", "和平精英", "穿越火线", "cf",
                        "使命召唤", "cod", "街霸", "拳皇", "铁拳", "fifa", "实况",
                        "nba2k", "游戏王", "宝可梦", "马里奥", "模拟器",
                    ]):
                        venue_building = "机房区"
                    else:
                        venue_building = "体育区"
                else:
                    venue_building = "E教学楼"
            except Exception:
                venue_building = "E教学楼"

            rooms = query_rooms(capacity_min=1, building=venue_building)
            sorted_rooms = select_best_rooms(rooms, participants) if rooms else []
            intent = {"building": venue_building, "participants": participants}

            venue_html = _venue_recommend_html(sorted_rooms, participants)
            plan_html = build_html(plan, sorted_rooms)

            # ── 保存 plan 供后续关键词锚定 ──
            state["last_plan"] = plan
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


@app.route("/export/word")
def export_word():
    """导出活动方案为 Word 文档 (.docx)"""
    sid = request.args.get("session_id", "")
    if not sid or sid not in sessions:
        return jsonify({"error": "会话未找到"}), 404

    state = sessions[sid]
    plan = state.get("last_plan")
    if not plan:
        return jsonify({"error": "尚未生成方案"}), 400

    # 自动安装缺失的 python-docx
    try:
        from agent.word_export import export_plan_to_docx
    except ImportError:
        import subprocess as _sp
        print("[Export] python-docx 未安装，正在自动安装...")
        _sp.check_call([sys.executable, "-m", "pip", "install", "-q", "python-docx"])
        from agent.word_export import export_plan_to_docx

    try:
        topic = plan.get("activity_topic", "活动方案")
        # 文件名：去掉不安全字符
        safe_topic = "".join(c for c in topic if c.isalnum() or c in (' ', '_', '-', '、'))
        if not safe_topic.strip():
            safe_topic = "活动方案"
        filename = f"CampusCompass_{safe_topic[:20]}.docx"

        filepath = export_plan_to_docx(plan)
        from flask import send_file
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        print(f"[Export] Word 导出失败: {e}")
        return jsonify({"error": f"导出失败: {str(e)}"}), 500


if __name__ == "__main__":
    # Windows 终端默认 GBK 编码不支持 emoji，强制 UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 50)
    print("  🎓 Campus Compass 校园活动策划助手")
    print("  🧠 主题智能处理 + 结构化方案生成")
    print("  浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
