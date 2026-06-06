"""
Campus Compass Agent Loop — 缓存优先（Cache-First）架构
========================================================

参考 DeepSeek-Reasonix 的 "Immutable Prefix + Append-Only Log" 设计：

  不可变前缀（Immutable Prefix）
    ├─ System Prompt（含工具定义、记忆块）
    └─ 第一条用户输入
  追加日志（Append-Only Log）
    ├─ LLM 回复 + 工具调用
    └─ 工具返回结果
  易变暂存（Volatile Scratch）
    └─ 系统提醒 / 效率警告（每轮刷新，追加到末尾）

核心原则：
  1. 永远不删除消息（保护前缀缓存）
  2. 系统干预统一收集到 scratch，作为单条消息追加
  3. 仅在线性预算临界时做一次性压缩（而非每轮裁剪）
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import LLM_API_KEY
from agent.state import AgentState
from agent.tools.registry import TOOL_DEFINITIONS, dispatch_tool
from agent.memory.trim import (
    estimate_tokens,
    soft_trim_check,
    hard_trim_to_budget,
    DEFAULT_TOKEN_BUDGET,
    HARD_TOKEN_BUDGET,
)
from agent.memory.persistence import load_memory_block
from agent.harness.observ import Trace
from agent.skill_loader import match_skill, load_all_skills


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
6. calculate_budget — 计算预算
7. finalize — 生成最终HTML

## 行为规则

- 不要猜测结果，调用工具获取真实数据
- 工具返回空或出错时，不要卡住，继续下一步
- 工具调用之间的文字输出简短即可
- 用户有长期记忆时，参考记忆中的偏好
- 如果用户在活动中表现出偏好（常用建筑、惯用人数），调用 save_user_preference 保存
- 对于不熟悉的活动主题，可以使用 search_web 搜索背景知识和案例来丰富方案内容"""


# ═══════════════════════════════════════════════════════════════
# 环境信息（P1-5：启动时注入可用场地概况）
# ═══════════════════════════════════════════════════════════════

def _build_env_info() -> str:
    """查询数据库，生成当前环境信息块。只执行一次（保护前缀缓存）。"""
    try:
        from tools.db_service import query_rooms
        all_rooms = query_rooms(capacity_min=1)
        if not all_rooms:
            return ""

        # 按建筑分组
        buildings = {}
        for r in all_rooms:
            bld = r.get("building", "未知")
            buildings.setdefault(bld, []).append(r)

        lines = ["\n## 当前可用场地"]
        for bld, rooms in buildings.items():
            caps = sorted([r["capacity"] for r in rooms])
            room_ids = [r["room_id"] for r in rooms]
            lines.append(f"- **{bld}**（{len(rooms)} 个）：{', '.join(room_ids)}")
            lines.append(f"  容量范围：{min(caps)}~{max(caps)} 人")

        lines.append("\n### 场地路由规则")
        lines.append("- 体育类活动（篮球/足球/运动会等）→ 查 **体育区**（体育馆/田径场）")
        lines.append("- 电竞/电子竞技类 → 查 **机房区**（E506/E507，各100机位）")
        lines.append("- 讲座/竞赛/展览/演出/实践等 → 查 **E教学楼**（21间教室）")
        lines.append("- 查教室时如果该区无结果，可尝试扩大搜索或去掉设备筛选")

        return "\n".join(lines)
    except Exception as e:
        print(f"[EnvInfo] 获取场地信息失败: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════
# 不可变前缀构建（只执行一次）
# ═══════════════════════════════════════════════════════════════

def _format_skill_block(skill: dict) -> str:
    """将匹配到的 Skill 格式化为系统提示注入块。"""
    if not skill:
        return ""

    title = skill.get("title", skill.get("name", ""))
    lines = [f"\n## 当前技能指引：{title}"]

    # ── SOP 流程表 ──
    phases = skill.get("phases", [])
    if phases:
        lines.append("\n### 标准活动流程（请参考此结构设计活动环节）")
        lines.append("| 环节 | 时长 | 内容 | 互动方式 |")
        lines.append("|------|------|------|----------|")
        for p in phases:
            lines.append(f"| {p.get('phase','')} | {p.get('duration','')} | {p.get('content','')} | {p.get('interaction','')} |")

    # ── 主持引导语 ──
    host_guides = skill.get("host_guides", {})
    if host_guides:
        lines.append("\n### 主持引导语参考")
        for key, val in host_guides.items():
            lines.append(f"- **{key}**: {val}")

    # ── 建议物资 ──
    materials = skill.get("materials", [])
    if materials:
        lines.append("\n### 建议物资清单（请在此基础上根据主题调整）")
        lines.append("| 物资 | 规格 | 数量 |")
        lines.append("|------|------|------|")
        for m in materials:
            lines.append(f"| {m.get('name','')} | {m.get('spec','')} | {m.get('qty','')} |")

    # ── 约束 ──
    constraints = skill.get("constraints", {})
    if constraints:
        lines.append("\n### 活动约束")
        for key, val in constraints.items():
            lines.append(f"- {key}: {val}")

    return "\n".join(lines)


def _build_system_prompt(user_input: str = "") -> tuple:
    """
    构建系统提示。

    返回 (system_prompt_text, matched_skill_name, matched_skill_dict)。
    记忆块 + 技能指引在启动时加载一次，之后不再变化（保护前缀缓存）。
    """
    parts = [SYSTEM_PROMPT]

    # ── 环境信息（P1-5：让模型知道有什么可用）──
    env_info = _build_env_info()
    if env_info:
        parts.append(env_info)

    # ── 匹配技能指引（P0-1）──
    matched_name = ""
    matched_skill = {}
    if user_input:
        try:
            matched_name, matched_skill = match_skill(user_input)
            if matched_skill:
                skill_block = _format_skill_block(matched_skill)
                if skill_block:
                    parts.append(skill_block)
                    print(f"[Skill] 匹配到活动类型: {matched_name} ({matched_skill.get('title', '')})")
        except Exception as e:
            print(f"[Skill] 匹配失败: {e}")

    # ── 长期记忆 ──
    memory_block = load_memory_block()
    if memory_block:
        parts.append("\n## 用户长期记忆\n" + memory_block)

    return "\n".join(parts), matched_name, matched_skill


# ═══════════════════════════════════════════════════════════════
# 易变暂存（Volatile Scratch）
# ═══════════════════════════════════════════════════════════════

BREAKER_THRESHOLD = 3  # 同一工具+同一参数连续 N 次触发断路


def _tool_fingerprint(tool_name: str, tool_args: dict) -> str:
    """生成工具调用的指纹（用于检测重复调用）。"""
    # 对参数做稳定序列化（忽略 key 顺序差异）
    args_key = json.dumps(tool_args, ensure_ascii=False, sort_keys=True)
    return f"{tool_name}|{args_key}"


def _check_circuit_breaker(state: AgentState) -> str:
    """
    检测死循环：同一工具+同一参数连续调用 ≥ BREAKER_THRESHOLD 次。

    返回断路提醒消息，如果没有触发则返回空字符串。
    """
    history = state.tool_call_history
    if len(history) < BREAKER_THRESHOLD:
        return ""

    # 取最近 N 次调用
    recent = history[-BREAKER_THRESHOLD:]
    if len(set(recent)) == 1:
        # 全部相同 → 死循环
        state.breaker_triggered = True
        tool_name = recent[0].split("|")[0]
        return (
            f"[Circuit Breaker] ⚠️ 你已连续 {BREAKER_THRESHOLD} 次调用 `{tool_name}` "
            f"且参数完全相同。结果不会改变。\n"
            f"请立即换一种方式：跳过此步、尝试不同参数、或标记此步骤失败后继续推进。"
        )

    return ""

def _render_todo_section(todos: list) -> str:
    """渲染当前待办列表（用于 nag 消息）"""
    if not todos:
        return ""
    lines = ["\n[Current Todo List]"]
    for t in todos:
        status = t.get("status", "pending")
        mark = "☑" if status == "completed" else ("▶" if status == "in_progress" else "☐")
        lines.append(f"  {mark} {t['content']}")
    return "\n".join(lines)


def _collect_scratch_notes(state: AgentState, messages: list) -> list:
    """
    收集本轮的系统干预消息（nag / 效率提醒），返回 scratch 列表。

    缓存友好的关键设计：
    - 所有系统干预收集到此列表，统一追加到消息末尾
    - 不在消息历史中间插入任何内容
    - scratch 内容每轮可变，但追加位置固定（始终在最末尾）
    """
    notes = []

    # ── Nag 1: TodoWrite 提醒 ──
    if state.rounds_since_todo >= TODO_NAG_THRESHOLD and state.todos:
        pending = [t for t in state.todos if t["status"] != "completed"]
        if pending:
            nag = (
                f"[System Reminder] 你有 {len(pending)} 个未完成的待办项，"
                f"请更新 todowrite 后继续。\n"
                + _render_todo_section(state.todos)
            )
            notes.append(("nag_todo", nag))

    # ── Nag 2: Circuit Breaker（死循环检测）──
    cb_msg = _check_circuit_breaker(state)
    if cb_msg:
        notes.append(("breaker", cb_msg))
        trace.nag("circuit_breaker")

    # ── 效率提醒：Token 预算 ──
    should_warn, should_hard_trim = soft_trim_check(messages)
    if should_warn and not should_hard_trim:
        est = estimate_tokens(messages)
        notes.append((
            "budget_warn",
            f"[System Info] 当前上下文约 {est} tokens（软预算 {DEFAULT_TOKEN_BUDGET}），请精简输出、加快进度。"
        ))

    return notes


def _flush_scratch(messages: list, scratch_notes: list, trace: Trace) -> list:
    """
    将 scratch 合并为一条 user 消息追加到末尾。

    始终返回新的 messages 列表（不修改原列表）。
    如果 scratch 为空，返回原列表。
    """
    if not scratch_notes:
        return messages

    parts = []
    for tag, text in scratch_notes:
        parts.append(text)
        if tag == "nag_todo":
            trace.nag(text[:80])

    combined = "\n\n".join(parts)
    return messages + [{"role": "user", "content": combined}]


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

def _call_llm(messages: list, tools: list = None):
    from agent.llm import chat
    return chat(messages, tools)


# ═══════════════════════════════════════════════════════════════
# Agent 主循环
# ═══════════════════════════════════════════════════════════════

def run_agent(user_input: str, session_id: str = None) -> str:
    state = AgentState()
    trace = Trace(session_id or "")
    t0 = time.time()

    # ── 构建不可变前缀（含技能指引 + 长期记忆）──
    system_content, skill_name, skill_dict = _build_system_prompt(user_input)
    state.matched_skill_name = skill_name
    state.matched_skill = skill_dict
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_input},
    ]

    if LLM_API_KEY:
        for turn in range(MAX_TURNS):
            state.round_count = turn + 1
            state.rounds_since_todo += 1

            # ═══════════════════════════════════════════════
            # Step A: 收集 Scratch（系统干预，不修改历史）
            # ═══════════════════════════════════════════════
            scratch_notes = _collect_scratch_notes(state, messages)

            # ═══════════════════════════════════════════════
            # Step B: 刷新 Scratch 到消息末尾
            # ═══════════════════════════════════════════════
            messages = _flush_scratch(messages, scratch_notes, trace)
            if scratch_notes:
                # 重置计数器（避免同一 nag 反复触发）
                for tag, _ in scratch_notes:
                    if tag == "nag_todo":
                        state.rounds_since_todo = 0

            # ═══════════════════════════════════════════════
            # Step C: 紧急压缩（仅在接近模型上限时触发）
            # ═══════════════════════════════════════════════
            _, should_hard_trim = soft_trim_check(messages)
            if should_hard_trim:
                prev_count = len(messages)
                messages = hard_trim_to_budget(messages)
                if len(messages) < prev_count:
                    print(f"[Agent] [CACHE] 紧急压缩: {prev_count} → {len(messages)} 条消息（一次性缓存断裂）")
                    trace.event("hard_trim", {"before": prev_count, "after": len(messages)})

            est_tokens = estimate_tokens(messages)
            print(f"[Agent] Turn {turn + 1}/{MAX_TURNS}  tokens≈{est_tokens}  messages={len(messages)}")

            # ═══════════════════════════════════════════════
            # Step D: LLM 调用
            # ═══════════════════════════════════════════════
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

            # ═══════════════════════════════════════════════
            # Step E: 无工具调用检测 → 推回（立即追加 nag）
            # ═══════════════════════════════════════════════
            if not tool_calls:
                pending = [t for t in state.todos if t["status"] != "completed"] if state.todos else None
                if pending:
                    nag = (
                        "[System] 你必须调用工具来执行步骤，而不是描述你要做什么。"
                        "当前待办：" + _render_todo_section(state.todos) +
                        "\n请调用对应的工具函数（如 parse_user_input），不要只说'正在调用'。"
                    )
                    # 注意：这里是立即追加（需要 LLM 在下一次调用中纠正）
                    # 追加位置在消息末尾，Prefix 到 nag 之前的部分仍然缓存命中
                    messages.append({"role": "user", "content": nag})
                    state.rounds_since_todo = 0
                    print("[Agent] [WARN] LLM 描述而非调工具，已推回并要求调工具")
                    continue
                print("[Agent] [OK] 无工具调用，Agent 认为任务完成")
                break

            # ═══════════════════════════════════════════════
            # Step F: 追加 LLM 回复 + 工具结果
            # ═══════════════════════════════════════════════
            messages.append(msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}

                # ── P0-3：记录工具调用指纹（用于死循环检测）──
                fp = _tool_fingerprint(func_name, func_args)
                state.tool_call_history.append(fp)
                print(f"[Agent] [tool] {func_name}({json.dumps(func_args, ensure_ascii=False)[:100]})")

                t_tool0 = time.time()
                result = dispatch_tool(func_name, func_args, state)
                t_tool1 = time.time()
                trace.tool_exec(func_name, json.loads(result).get("ok", False), (t_tool1 - t_tool0) * 1000)

                result_preview = result[:200] if len(result) > 200 else result
                print(f"[Agent] [result] {result_preview}")

                # 追加工具结果到消息末尾
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

        # ── LLM 循环结束但未 finalize ──
        if state.plan and not state.html_output:
            print("[Agent] [WARN] 未调用 finalize，用已有数据生成")
            from agent.formatter import build_html
            from agent.memory.persistence import auto_remember
            state.html_output = build_html(state.plan, state.sorted_rooms, state.budget)
            if state.intent:
                auto_remember(state.plan, state.intent, state.participants)

        trace.dump()
        print(f"[Trace] {trace.report()}")
        if state.html_output:
            return state.html_output

    print("[Agent] [Fallback] 降级为确定性流水线模式")
    return _run_fallback_pipeline(user_input, state, session_id, trace)


# ═══════════════════════════════════════════════════════════════
# 降级流水线（无 API Key 时使用）
# ═══════════════════════════════════════════════════════════════

def _run_fallback_pipeline(user_input: str, state: AgentState, session_id: str, trace: Trace) -> str:
    from engine.intent_parser import parse_intent
    from engine.topic_analyzer import analyze_topic
    from engine.plan_generator import generate_plan
    from engine.room_scorer import rank_rooms
    from tools.db_service import query_rooms
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

    print("[Fallback] Step 6: 预算计算")
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "templates.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            templates = json.load(f)
        template = templates.get(state.intent.get("activity_type", "讲座"), templates.get("讲座", {}))
    else:
        template = {}
    state.budget = estimate_budget(template, state.participants, state.intent.get("activity_type", "讲座"))

    print("[Fallback] Step 7: 生成 HTML + L3记忆")
    state.html_output = build_html(state.plan, state.sorted_rooms, state.budget)
    auto_remember(state.plan, state.intent, state.participants)

    trace.event("fallback_complete", {"steps": 8})
    trace.dump()
    print(f"[Trace] {trace.report()}")

    if session_id:
        try:
            from agent.memory.session import remember
            remember(session_id, user_input, state.intent, state.plan, state.budget,
                     state.sorted_rooms)
        except Exception:
            pass

    return state.html_output
