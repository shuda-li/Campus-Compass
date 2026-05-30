import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "todowrite",
            "description": "Write or update the task todo list. Call at start of complex tasks to plan, and after each step to mark progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                            },
                            "required": ["content", "status"]
                        }
                    }
                },
                "required": ["todos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_user_input",
            "description": "解析用户的自然语言输入，提取：活动类型、参与人数、偏好建筑、设备需求",
            "parameters": {
                "type": "object",
                "properties": {"user_input": {"type": "string"}},
                "required": ["user_input"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_and_expand_topic",
            "description": "分析活动主题复杂度，简略主题自动扩展",
            "parameters": {
                "type": "object",
                "properties": {"topic": {"type": "string"}},
                "required": ["topic"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_activity_plan",
            "description": "生成结构化活动方案：目的+5个环节+物资清单",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "participants": {"type": "integer"}
                },
                "required": ["topic", "participants"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_classrooms",
            "description": "查询可用教室，按容量/建筑/设备筛选",
            "parameters": {
                "type": "object",
                "properties": {
                    "capacity_min": {"type": "integer"},
                    "building": {"type": "string"},
                    "required_equipment": {"type": "array", "items": {"type": "string"}}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "score_classrooms",
            "description": "多维度综合评分排序教室",
            "parameters": {
                "type": "object",
                "properties": {
                    "participants": {"type": "integer"},
                    "building": {"type": "string"},
                    "equipment": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["participants"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_navigation",
            "description": "获取到推荐教室的步行路线",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_budget",
            "description": "计算活动预算",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_type": {"type": "string"},
                    "participants": {"type": "integer"}
                },
                "required": ["activity_type", "participants"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finalize",
            "description": "生成最终HTML策划方案并结束",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_user_preference",
            "description": "保存用户偏好到长期记忆，如'我习惯在E座办活动''我通常50人规模'",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "偏好名"},
                    "value": {"type": "string", "description": "偏好值"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_subagent",
            "description": "派一个子代理在隔离上下文中执行专项任务。可用类型: classroom_scout（查教室）| budget_analyst（算预算）。子代理的完整对话会被丢弃，只返回最终摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {"type": "string", "description": "子代理类型: classroom_scout 或 budget_analyst"},
                    "prompt": {"type": "string", "description": "给子代理的任务描述"}
                },
                "required": ["agent_type", "prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "搜索互联网获取实时信息。可用于：了解活动主题的背景知识、查找类似活动案例、获取创意灵感。返回搜索结果摘要和链接",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词，建议包含'校园活动'相关词以提高相关性"},
                    "max_results": {"type": "integer", "description": "最大结果数，默认3，最大5"}
                },
                "required": ["query"]
            }
        }
    },
]


def dispatch_tool(tool_name: str, arguments: dict, state) -> str:
    try:
        if tool_name == "todowrite":
            todos = arguments.get("todos", [])
            state.todos = todos
            state.rounds_since_todo = 0
            pending = sum(1 for t in todos if t["status"] == "pending")
            in_progress = sum(1 for t in todos if t["status"] == "in_progress")
            completed = sum(1 for t in todos if t["status"] == "completed")
            return json.dumps({
                "ok": True,
                "total": len(todos),
                "pending": pending,
                "in_progress": in_progress,
                "completed": completed,
            }, ensure_ascii=False)

        if tool_name == "parse_user_input":
            from engine.intent_parser import parse_intent
            user_input = arguments.get("user_input", "")
            state.raw_input = user_input
            state.intent = parse_intent(user_input)
            state.participants = state.intent.get("participants", 50)
            return json.dumps({
                "ok": True,
                "activity_type": state.intent["activity_type"],
                "participants": state.participants,
                "building": state.intent["building"],
                "equipment": state.intent["equipment"],
                "theme": state.intent["theme"],
            }, ensure_ascii=False)

        if tool_name == "analyze_and_expand_topic":
            from engine.topic_analyzer import analyze_topic
            from agent.llm import expand_topic as llm_expand
            topic = arguments.get("topic", state.raw_input)
            try:
                expanded = llm_expand(topic)
                result = analyze_topic(topic, lambda t: expanded) if expanded else analyze_topic(topic)
            except Exception:
                result = analyze_topic(topic)
            state.expanded_topic = result.get("expanded") or topic
            return json.dumps({
                "ok": True,
                "is_simple": result["is_simple"],
                "original": result["original"],
                "expanded": state.expanded_topic,
            }, ensure_ascii=False)

        if tool_name == "generate_activity_plan":
            from engine.plan_generator import generate_plan
            from agent.llm import generate_plan as llm_plan
            topic = state.expanded_topic or arguments.get("topic", state.raw_input)
            participants = arguments.get("participants", state.participants)
            state.participants = participants
            llm_fn = None
            try:
                llm_plan(topic, participants)
                llm_fn = lambda t, p: llm_plan(t, p)
            except Exception:
                pass
            state.plan = generate_plan(topic, participants, state.sorted_rooms, llm_fn)
            return json.dumps({
                "ok": True,
                "topic": state.plan.get("activity_topic", topic),
                "content_count": len(state.plan.get("activity_content", [])),
                "materials_count": len(state.plan.get("activity_materials", [])),
                "purpose_preview": state.plan.get("activity_purpose", "")[:80],
            }, ensure_ascii=False)

        if tool_name == "find_classrooms":
            from tools.db_service import query_rooms
            capacity_min = arguments.get("capacity_min", state.participants)
            building = arguments.get("building", state.intent.get("building") if state.intent else None)
            required_equipment = arguments.get("required_equipment", None)
            state.rooms = query_rooms(capacity_min=capacity_min, building=building, required_equipment=required_equipment)
            return json.dumps({
                "ok": True,
                "count": len(state.rooms),
                "preview": [{"room_id": r.get("room_id"), "building": r.get("building"), "capacity": r.get("capacity")} for r in state.rooms[:5]],
            }, ensure_ascii=False)

        if tool_name == "score_classrooms":
            from engine.room_scorer import rank_rooms
            participants = arguments.get("participants", state.participants)
            building = arguments.get("building", state.intent.get("building", "") if state.intent else "")
            equipment = arguments.get("equipment", state.intent.get("equipment", []) if state.intent else [])
            intent_for_scoring = {"building": building, "equipment": equipment, "participants": participants}
            state.sorted_rooms = rank_rooms(state.rooms, intent_for_scoring)
            top3 = [{"rank": i + 1, "room_id": r.get("room_id"), "capacity": r.get("capacity")} for i, r in enumerate(state.sorted_rooms[:3])]
            return json.dumps({"ok": True, "total": len(state.sorted_rooms), "top3": top3}, ensure_ascii=False)

        if tool_name == "get_navigation":
            from tools.navigation import generate_navigation
            top_room = state.sorted_rooms[0] if state.sorted_rooms else {}
            state.navigation = generate_navigation(top_room)
            return json.dumps({"ok": True, "navigation_preview": state.navigation[:200]}, ensure_ascii=False)

        if tool_name == "calculate_budget":
            from tools.budget_calc import estimate_budget
            activity_type = arguments.get("activity_type", state.intent.get("activity_type", "讲座") if state.intent else "讲座")
            participants = arguments.get("participants", state.participants)
            template_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "templates.json")
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    templates = json.load(f)
                template = templates.get(activity_type, templates.get("讲座", {}))
            else:
                template = {}
            state.budget = estimate_budget(template, participants, activity_type)
            return json.dumps({"ok": True, "total": state.budget.get("合计", 0), "level": state.budget.get("预算等级", "")}, ensure_ascii=False)

        if tool_name == "finalize":
            from agent.formatter import build_html
            from agent.memory.persistence import auto_remember
            state.html_output = build_html(state.plan, state.sorted_rooms, state.navigation, state.budget)
            if state.intent:
                auto_remember(state.plan, state.intent, state.participants)
            return json.dumps({"ok": True, "done": True, "html_length": len(state.html_output)}, ensure_ascii=False)

        if tool_name == "save_user_preference":
            from agent.memory.persistence import save_preference
            key = arguments.get("key", "")
            value = arguments.get("value", "")
            save_preference("_manual", key, value)
            return json.dumps({"ok": True, "saved": f"{key}={value}"}, ensure_ascii=False)

        if tool_name == "dispatch_subagent":
            from agent.tools.subagent import run_subagent
            agent_type = arguments.get("agent_type", "classroom_scout")
            prompt = arguments.get("prompt", "")
            return run_subagent(agent_type, prompt, state)

        if tool_name == "search_web":
            from agent.mcp.tavily_search import search_web
            query = arguments.get("query", "")
            max_results = min(arguments.get("max_results", 3), 5)
            return search_web(query, max_results=max_results)

        return json.dumps({"ok": False, "error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    except Exception as e:
        import traceback
        return json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()[-500:]}, ensure_ascii=False)
