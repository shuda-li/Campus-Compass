from engine.intent_parser import parse_intent
from engine.template_matcher import match_template
from engine.room_scorer import rank_rooms
from agent.llm_client import call_llm_for_ideation
from tools.db_service import query_rooms
from tools.navigation import generate_navigation
from tools.budget_calc import estimate_budget
from agent.formatter import build_html


def run_workflow(user_input: str, session_id: str = None) -> str:
    """
    主工作流 - 固定步骤执行:

    Step 0: 意图解析
    Step 1: 模板匹配
    Step 2: LLM创意生成
    Step 3: 生成活动方案
    Step 4: 查询教室
    Step 5: 教室打分排序
    Step 6: 生成导航
    Step 7: 计算预算
    Step 8: 组装输出HTML
    Step 9: 记忆存储 (L1+L2)
    """
    intent = parse_intent(user_input)
    print(f"[Step 0] 意图解析: {intent['activity_type']} {intent['participants']}人")

    template = match_template(intent)
    print(f"[Step 1] 匹配模板: {template['activity_type']}")

    ideas = call_llm_for_ideation(intent)
    print(f"[Step 2] LLM创意: {ideas.get('recommended_title', '')}")

    plan = _build_plan(intent, template, ideas)
    print(f"[Step 3] 活动方案: {plan.get('title', '')}")

    rooms = query_rooms(capacity_min=intent["participants"], building=intent["building"])
    print(f"[Step 4] 查询到 {len(rooms)} 间教室（{intent['building']}）")

    sorted_rooms = rank_rooms(rooms, intent, plan)
    print(f"[Step 5] 首选教室: {sorted_rooms[0].get('room_id', '?') if sorted_rooms else '无'}")

    top_room = sorted_rooms[0] if sorted_rooms else {}
    navigation = generate_navigation(top_room)
    print(f"[Step 6] 导航已生成")

    budget = estimate_budget(template, intent.get("participants", 50))
    print(f"[Step 7] 预算: {budget.get('合计', 0)}元")

    html = build_html(plan, sorted_rooms, navigation, budget)
    print(f"[Step 8] HTML输出已生成")

    if session_id:
        try:
            from agent.memory import remember
            remember(session_id, user_input, intent, plan, budget, sorted_rooms, navigation)
            print(f"[Step 9] 记忆已存储 (session: {session_id})")
        except Exception as e:
            print(f"[Step 9] 记忆存储失败: {e}")

    return html


def _build_plan(intent: dict, template: dict, ideas: dict) -> dict:
    return {
        "title": ideas.get("recommended_title", f"{intent['activity_type']}策划方案"),
        "timeline": ideas.get("activity_timeline", template.get("default_timeline", [])),
        "resources": ideas.get("resource_list", template.get("default_resources", [])),
        "promotion": ideas.get("promotion_suggestion", ""),
    }
