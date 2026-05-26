import json
from dataclasses import dataclass

MAX_TURNS = 10


@dataclass
class SubAgentSpec:
    name: str
    description: str
    tool_names: list[str]
    max_turns: int = 10
    can_spawn_child: bool = False


REGISTRY = {
    "classroom_scout": SubAgentSpec(
        name="classroom_scout",
        description="专门查询和评估教室的只读探索者",
        tool_names=["find_classrooms", "score_classrooms", "get_navigation"],
        max_turns=6,
    ),
    "budget_analyst": SubAgentSpec(
        name="budget_analyst",
        description="专门计算和评估预算",
        tool_names=["calculate_budget"],
        max_turns=4,
    ),
}


def run_subagent(agent_type: str, prompt: str, state) -> str:
    spec = REGISTRY.get(agent_type)
    if not spec:
        return json.dumps({"ok": False, "error": f"未知子代理类型: {agent_type}"}, ensure_ascii=False)

    if agent_type == "classroom_scout":
        return _scout_classrooms(prompt, state)
    elif agent_type == "budget_analyst":
        return _analyze_budget(prompt, state)

    return json.dumps({"ok": False, "error": "未实现"}, ensure_ascii=False)


def _scout_classrooms(prompt: str, state) -> str:
    from tools.db_service import query_rooms
    from engine.room_scorer import rank_rooms
    from tools.navigation import generate_navigation

    participants = state.participants
    building = state.intent.get("building", "E教学楼") if state.intent else "E教学楼"
    rooms = query_rooms(capacity_min=participants, building=building)
    if not rooms:
        return json.dumps({"ok": True, "count": 0, "note": "暂无可匹配教室"}, ensure_ascii=False)

    intent_for_scoring = {"building": building, "equipment": [], "participants": participants}
    if state.intent:
        intent_for_scoring["equipment"] = state.intent.get("equipment", [])
        intent_for_scoring["building"] = state.intent.get("building", building)
    sorted_rooms = rank_rooms(rooms, intent_for_scoring)
    top = sorted_rooms[0] if sorted_rooms else {}
    nav = generate_navigation(top) if top else ""

    return json.dumps({
        "ok": True,
        "total": len(sorted_rooms),
        "top_room": {"room_id": top.get("room_id"), "building": top.get("building"), "capacity": top.get("capacity")} if top else None,
        "navigation_preview": nav[:200],
    }, ensure_ascii=False)


def _analyze_budget(prompt: str, state) -> str:
    from tools.budget_calc import estimate_budget
    activity_type = state.intent.get("activity_type", "讲座") if state.intent else "讲座"
    participants = state.participants

    template = {}
    import os
    template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "templates.json")
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
