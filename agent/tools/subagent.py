"""
P0-2：真正的 Sub-Agent 实现
============================

从「纯 Python 函数调度器」重构为「LLM 驱动的微型 Agent Loop」：

  旧：classroom_scout → 直接调 query_rooms() + rank_rooms() → 返回 JSON
      如果教室查询返回 0 间 → 不会自己扩大搜索 → 原样返回空结果

  新：classroom_scout → 独立 messages[] + LLM + 白名单工具 → 自主决策
      如果第一次查询返回 0 间 → LLM 决定换建筑/降容量/去设备筛选 → 再次查询
      → 找到教室后自己评分 → 只返回摘要文本给父 Agent

核心原则（参考 agent.md 第五期）：
  1. 子代理有独立的 messages[]（上下文隔离）
  2. 子代理只有白名单工具（权限边界）
  3. 子代理的完整对话在返回后被丢弃（不写回父 Agent）
  4. 父子通过"工单式 prompt"交接（显式传递，不共享可变状态）
"""

import json
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════
# 子代理身份定义（花名册）
# ═══════════════════════════════════════════════════════════════

@dataclass
class SubAgentSpec:
    name: str
    description: str
    system_prompt: str
    tool_names: list[str]
    max_turns: int = 10
    can_spawn_child: bool = False


REGISTRY = {
    "classroom_scout": SubAgentSpec(
        name="classroom_scout",
        description="专门查询和评估教室的只读探索者。会自主尝试不同搜索策略（换建筑、降容量、去设备筛选），找到最优教室后返回摘要。",
        system_prompt="""你是教室勘探子代理（classroom_scout），专门负责查询和评估教室。

## 你的能力
- find_classrooms：按容量/建筑/设备查询可用教室
- score_classrooms：多维评分排序（容量适配+楼层+设备+建筑偏好）
- get_navigation：获取到推荐教室的步行导航

## 行为规则
- 先用主 Agent 提供的人数+建筑+设备偏好做首次查询
- 如果返回 0 间教室 → 自主扩大搜索：去掉建筑限制、降低容量要求、去掉设备筛选
- 找到教室后立即评分排序，选出最优 1-3 间
- 把你的发现总结成简短摘要（教室编号+容量+评分+为什么推荐）

## 输出格式
完成任务后，用纯文本简短总结你的发现，不要调用任何工具就直接回复。""",
        tool_names=["find_classrooms", "score_classrooms", "get_navigation"],
        max_turns=6,
    ),
    "budget_analyst": SubAgentSpec(
        name="budget_analyst",
        description="专门计算和评估活动预算。会根据活动类型和规模给出详细的费用分析和优化建议。",
        system_prompt="""你是预算分析子代理（budget_analyst），专门负责计算和评估活动预算。

## 你的能力
- calculate_budget：根据活动类型和参与人数计算预算

## 行为规则
- 调用 calculate_budget 获取预算明细
- 分析预算构成，指出主要支出项
- 给出优化建议（哪些可以节省，哪些不能省）
- 如果参与人数较少但预算较高，提示性价比

## 输出格式
完成任务后用纯文本简短总结：总预算金额、预算等级、主要支出分析、省钱建议。""",
        tool_names=["calculate_budget"],
        max_turns=4,
    ),
}


# ═══════════════════════════════════════════════════════════════
# 子代理核心循环
# ═══════════════════════════════════════════════════════════════

def _build_subagent_prompt(agent_type: str, user_prompt: str, state) -> str:
    """
    构建子代理的任务工单。

    原则：把子代理需要的上下文显式写进工单，不共享父 Agent 的可变状态。
    这就是"交接写进工单，不靠脑电波"（agent.md 第五期坑③）。
    """
    parts = [f"## 任务\n{user_prompt}\n"]

    if agent_type == "classroom_scout":
        participants = state.participants
        building = state.intent.get("building", "E教学楼") if state.intent else "E教学楼"
        equipment = state.intent.get("equipment", []) if state.intent else []
        parts.append("## 可用上下文")
        parts.append(f"- 参与人数: {participants} 人")
        parts.append(f"- 偏好建筑: {building}")
        if equipment:
            parts.append(f"- 需要设备: {', '.join(equipment)}")
        parts.append(f"\n请用以上参数做首次查询。如果结果为空，尝试去掉建筑限制或降低容量要求。")

    elif agent_type == "budget_analyst":
        activity_type = state.intent.get("activity_type", "讲座") if state.intent else "讲座"
        participants = state.participants
        parts.append("## 可用上下文")
        parts.append(f"- 活动类型: {activity_type}")
        parts.append(f"- 参与人数: {participants} 人")

    return "\n".join(parts)


def run_subagent(agent_type: str, prompt: str, state) -> str:
    """
    在隔离上下文中运行子代理，只返回最终摘要文本。

    这是 agent.md 第五期的核心：子代理的 messages 不写回父代理。
    """
    spec = REGISTRY.get(agent_type)
    if not spec:
        return json.dumps({"ok": False, "error": f"未知子代理类型: {agent_type}"}, ensure_ascii=False)

    # ── 检查 LLM 是否可用 ──
    from config import LLM_API_KEY
    if not LLM_API_KEY:
        # 降级：仍然用旧函数（保证基本功能）
        return _fallback_subagent(agent_type, prompt, state)

    from agent.llm import chat
    from agent.tools.registry import TOOL_DEFINITIONS, dispatch_tool

    # ── ① 构建白名单工具 ──
    whitelist_tools = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in spec.tool_names]

    # ── ② 创建隔离上下文 ──
    sub_messages = [
        {"role": "system", "content": spec.system_prompt},
        {"role": "user", "content": _build_subagent_prompt(agent_type, prompt, state)},
    ]

    # ── ③ 运行微型 Agent Loop ──
    final_summary = ""
    for turn in range(spec.max_turns):
        try:
            resp = chat(sub_messages, whitelist_tools, temperature=0.5, max_tokens=800, timeout=30)
        except Exception as e:
            final_summary = f"[子代理 {agent_type} LLM 调用失败: {e}]"
            break

        if resp is None:
            final_summary = f"[子代理 {agent_type} LLM 不可用]"
            break

        msg = resp["choices"][0]["message"]
        tool_calls = msg.get("tool_calls", [])

        # 有文本输出 → 可能是最终总结
        if msg.get("content"):
            final_summary = msg["content"].strip()

        # 没有工具调用 → 子代理认为任务完成
        if not tool_calls:
            break

        # ── ④ 追加 assistant 消息 + 执行工具 ──
        sub_messages.append(msg)

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            try:
                func_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                func_args = {}

            # 安全校验：只允许白名单工具
            if func_name not in spec.tool_names:
                result = json.dumps({"ok": False, "error": f"子代理无权调用 {func_name}"}, ensure_ascii=False)
            else:
                try:
                    result = dispatch_tool(func_name, func_args, state)
                except Exception as e:
                    result = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

            sub_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })

        # 到达最大轮次 → 取最后一轮文本作为摘要
        if turn == spec.max_turns - 1 and not final_summary:
            final_summary = f"[子代理 {agent_type} 达到最大轮次 {spec.max_turns}，任务可能未完成]"

    # ── ⑤ 返回摘要（子代理的 messages 在此刻成为垃圾，被 Python 回收）──
    if final_summary:
        return final_summary

    # 兜底：如果 LLM 始终没有文本输出，至少返回工具执行的事实摘要
    return f"[子代理 {agent_type} 完成探索，详见上方工具结果]"


# ═══════════════════════════════════════════════════════════════
# 降级模式（无 LLM 时的函数兜底）
# ═══════════════════════════════════════════════════════════════

def _fallback_subagent(agent_type: str, prompt: str, state) -> str:
    """无 LLM 时的确定性兜底（保留旧行为以保证基本可用）。"""
    if agent_type == "classroom_scout":
        from tools.db_service import query_rooms
        from engine.room_scorer import rank_rooms
        from tools.navigation import generate_navigation

        participants = state.participants
        building = state.intent.get("building", "E教学楼") if state.intent else "E教学楼"
        rooms = query_rooms(capacity_min=participants, building=building)
        if not rooms:
            # 扩大搜索
            rooms = query_rooms(capacity_min=max(10, participants // 2))
        if not rooms:
            return json.dumps({"ok": True, "count": 0, "note": "暂无可匹配教室"}, ensure_ascii=False)

        intent_for_scoring = {"building": building, "equipment": state.intent.get("equipment", []) if state.intent else [], "participants": participants}
        sorted_rooms = rank_rooms(rooms, intent_for_scoring)
        top = sorted_rooms[0] if sorted_rooms else {}
        nav = generate_navigation(top) if top else ""

        return json.dumps({
            "ok": True,
            "total": len(sorted_rooms),
            "top_room": {"room_id": top.get("room_id"), "building": top.get("building"), "capacity": top.get("capacity")} if top else None,
            "navigation_preview": nav[:200],
        }, ensure_ascii=False)

    elif agent_type == "budget_analyst":
        from tools.budget_calc import estimate_budget
        activity_type = state.intent.get("activity_type", "讲座") if state.intent else "讲座"
        participants = state.participants

        import os
        template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "templates.json")
        template = {}
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                templates = json.load(f)
            template = templates.get(activity_type, templates.get("讲座", {}))

        budget = estimate_budget(template, participants, activity_type)
        return json.dumps({
            "ok": True,
            "total": budget.get("合计", 0),
            "level": budget.get("预算等级", ""),
            "suggestion": f"建议{activity_type}类活动预留{budget.get('合计', 0)}元预算",
        }, ensure_ascii=False)

    return json.dumps({"ok": False, "error": "未实现"}, ensure_ascii=False)
