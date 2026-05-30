import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LLM_API_KEY
from agent.state import AgentState
from agent.tools.registry import TOOL_DEFINITIONS, dispatch_tool
from agent.memory.trim import estimate_tokens, trim_to_budget, build_summary, DEFAULT_TOKEN_BUDGET
from agent.memory.persistence import load_memory_block
from agent.harness.observ import Trace


MAX_TURNS = 15
TODO_NAG_THRESHOLD = 3


SYSTEM_PROMPT = """你是 Campus Compass 校园活动策划 Agent。你通过调用工具来完成活动策划任务。

## 任务规划规则

重要：对于任何复杂任务，你必须先调用 todowrite 列出计划步骤，再逐个执行：
- 收到任务 → 先调 todowrite 列出所有步骤 (pending)
- 开始某步 → 把该步翻成 in_progress
- 完成某步 → 翻成 completed
- 同一时间只有一个 in_progress
- 所有步骤 completed 后才能调 finalize

## 核心工具流程

1. parse_user_input — 解析用户意图
2. analyze_and_expand_topic — 分析/扩展主题
3. generate_activity_plan — 生成方案
4. find_classrooms — 查询教室（空则扩大范围）
5. score_classrooms — 评分排序（如有教室）
6. get_navigation — 获取导航
7. calculate_budget — 计算预算
8. finalize — 生成最终HTML

## 行为规则

- 不要猜测结果，调用工具获取真实数据
- 工具返回空或出错时，不要卡住，继续下一步
- 工具调用之间的文字输出简短即可
- 用户有长期记忆时，参考记忆中的偏好
- 如果用户在活动中表现出偏好（常用建筑、惯用人数），调用 save_user_preference 保存
- 对于不熟悉的活动主题，可以使用 search_web 搜索背景知识和案例来丰富方案内容"""


def _build_system_prompt() -> str:
    memory_block = load_memory_block()
    if memory_block:
        return SYSTEM_PROMPT + "\n\n## 用户长期记忆\n" + memory_block
    return SYSTEM_PROMPT


def _render_todo_section(todos: list) -> str:
    if not todos:
        return ""
    lines = ["\n[Current Todo List]"]
    for t in todos:
        status = t.get("status", "pending")
        mark = "☑" if status == "completed" else ("▶" if status == "in_progress" else "☐")
        lines.append(f"  {mark} {t['content']}")
    return "\n".join(lines)


def _call_llm(messages: list, tools: list = None):
    from agent.llm import chat
    return chat(messages, tools)


def run_agent(user_input: str, session_id: str = None) -> str:
    state = AgentState()
    trace = Trace(session_id or "")
    t0 = time.time()

    system_content = _build_system_prompt()
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input},
    ]

    if LLM_API_KEY:
        for turn in range(MAX_TURNS):
            state.round_count = turn + 1
            state.rounds_since_todo += 1
            print(f"[Agent] Turn {turn + 1}/{MAX_TURNS}  tokens≈{estimate_tokens(messages)}")

            # ===== Nag: TodoWrite 提醒 =====
            if state.rounds_since_todo >= TODO_NAG_THRESHOLD and state.todos:
                pending = [t for t in state.todos if t["status"] != "completed"]
                if pending:
                    nag = f"[Reminder] 你有 {len(pending)} 个未完成的待办项，请更新 todowrite 后继续。\n" + _render_todo_section(state.todos)
                    messages.append({"role": "user", "content": nag})
                    trace.nag(f"{len(pending)} pending todos")
                    state.rounds_since_todo = 0

            # ===== Token 预算裁剪 =====
            messages = trim_to_budget(messages)

            try:
                resp = _call_llm(messages, TOOL_DEFINITIONS)
            except Exception as e:
                print(f"[Agent] LLM 调用失败: {e}")
                trace.event("error", {"msg": str(e)})
                break

            if resp is None:
                break

            choice = resp["choices"][0]
            msg = choice["message"]
            usage = resp.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            state.total_tokens_in += tokens_in
            state.total_tokens_out += tokens_out

            tool_calls = msg.get("tool_calls", [])
            trace.llm_call(tokens_in, tokens_out, len(tool_calls))

            if msg.get("content"):
                print(f"[Agent] [talk] {msg['content'][:120]}")

            if not tool_calls:
                pending = [t for t in state.todos if t["status"] != "completed"] if state.todos else None
                if pending:
                    nag = (
                        "[System] 你必须调用工具来执行步骤，而不是描述你要做什么。"
                        "当前待办：" + _render_todo_section(state.todos) +
                        "\n请调用对应的工具函数（如 parse_user_input），不要只说'正在调用'。"
                    )
                    messages.append({"role": "user", "content": nag})
                    state.rounds_since_todo = 0
                    print("[Agent] [WARN] LLM 描述而非调工具，已推回并要求调工具")
                    continue
                print("[Agent] [OK] 无工具调用，Agent 认为任务完成")
                break

            messages.append(msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}
                print(f"[Agent] [tool] {func_name}({json.dumps(func_args, ensure_ascii=False)[:100]})")

                t_tool0 = time.time()
                result = dispatch_tool(func_name, func_args, state)
                t_tool1 = time.time()
                trace.tool_exec(func_name, json.loads(result).get("ok", False), (t_tool1 - t_tool0) * 1000)

                result_preview = result[:200] if len(result) > 200 else result
                print(f"[Agent] [result] {result_preview}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

                if func_name == "finalize":
                    print("[Agent] [OK] Agent 调用 finalize，任务完成")
                    trace.dump()
                    print(f"[Trace] {trace.report()}")
                    if state.html_output:
                        return state.html_output
                    break

        # LLM 循环结束但未 finalize
        if state.plan and not state.html_output:
            print("[Agent] [WARN] 未调用 finalize，用已有数据生成")
            from agent.formatter import build_html
            from agent.memory.persistence import auto_remember
            state.html_output = build_html(state.plan, state.sorted_rooms, state.navigation, state.budget)
            if state.intent:
                auto_remember(state.plan, state.intent, state.participants)

        trace.dump()
        print(f"[Trace] {trace.report()}")
        if state.html_output:
            return state.html_output

    print("[Agent] [Fallback] 降级为确定性流水线模式")
    return _run_fallback_pipeline(user_input, state, session_id, trace)


def _run_fallback_pipeline(user_input: str, state: AgentState, session_id: str, trace: Trace) -> str:
    from engine.intent_parser import parse_intent
    from engine.topic_analyzer import analyze_topic
    from engine.plan_generator import generate_plan
    from engine.room_scorer import rank_rooms
    from tools.db_service import query_rooms
    from tools.navigation import generate_navigation
    from tools.budget_calc import estimate_budget
    from agent.formatter import build_html
    from agent.memory.persistence import auto_remember

    print("[Fallback] Step 1: 意图解析")
    state.intent = parse_intent(user_input)
    state.participants = state.intent.get("participants", 50)

    print("[Fallback] Step 2: 主题分析")
    topic_result = analyze_topic(user_input)
    state.expanded_topic = topic_result.get("expanded") or user_input

    print("[Fallback] Step 3: 生成活动方案")
    state.plan = generate_plan(state.expanded_topic, state.participants, [])

    print("[Fallback] Step 4: 查询教室")
    state.rooms = query_rooms(capacity_min=state.participants, building=state.intent.get("building"))

    if state.rooms:
        print("[Fallback] Step 5: 教室排序")
        state.sorted_rooms = rank_rooms(state.rooms, state.intent)
        print("[Fallback] Step 6: 导航生成")
        top = state.sorted_rooms[0] if state.sorted_rooms else {}
        state.navigation = generate_navigation(top if top else {})

    print("[Fallback] Step 7: 预算计算")
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        template = templates.get(state.intent.get("activity_type", "讲座"), templates.get("讲座", {}))
    else:
        template = {}
    state.budget = estimate_budget(template, state.participants, state.intent.get("activity_type", "讲座"))

    print("[Fallback] Step 8: 生成 HTML + L3记忆")
    state.html_output = build_html(state.plan, state.sorted_rooms, state.navigation, state.budget)
    auto_remember(state.plan, state.intent, state.participants)

    trace.event("fallback_complete", {"steps": 8})
    trace.dump()
    print(f"[Trace] {trace.report()}")

    if session_id:
        try:
            from agent.memory.session import remember
            remember(session_id, user_input, state.intent, state.plan, state.budget,
                     state.sorted_rooms, state.navigation)
        except Exception:
            pass

    return state.html_output
