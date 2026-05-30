from dataclasses import dataclass, field


@dataclass
class AgentState:
    raw_input: str = ""
    intent: dict = None
    expanded_topic: str = None
    plan: dict = None
    rooms: list = field(default_factory=list)
    sorted_rooms: list = field(default_factory=list)
    navigation: str = ""
    budget: dict = field(default_factory=dict)
    participants: int = 50
    html_output: str = ""

    todos: list = field(default_factory=list)
    rounds_since_todo: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    round_count: int = 0
