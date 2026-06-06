from dataclasses import dataclass, field


@dataclass
class AgentState:
    raw_input: str = ""
    intent: dict = None
    expanded_topic: str = None
    plan: dict = None
    rooms: list = field(default_factory=list)
    sorted_rooms: list = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    participants: int = 50
    html_output: str = ""

    todos: list = field(default_factory=list)
    rounds_since_todo: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    round_count: int = 0

    # Skill 系统（P0-1：匹配到的活动策划技能）
    matched_skill_name: str = ""
    matched_skill: dict = field(default_factory=dict)

    # Circuit Breaker（P0-3：死循环检测）
    tool_call_history: list = field(default_factory=list)  # 最近 N 次工具调用 [{"name":..., "args_hash":...}, ...]
    breaker_triggered: bool = False  # 本轮是否已触发断路
