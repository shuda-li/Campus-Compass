import json

DEFAULT_TOKEN_BUDGET = 8000


def estimate_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        text = json.dumps(m, ensure_ascii=False)
        total += max(1, len(text) // 3)
    return total


def trim_to_budget(messages: list, budget: int = DEFAULT_TOKEN_BUDGET) -> list:
    system_msgs = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]

    while rest and estimate_tokens(system_msgs + rest) > budget:
        removed = rest.pop(0)
        if removed.get("role") == "tool":
            continue
        if rest and rest[0].get("role") == "tool":
            rest.pop(0)

    return system_msgs + rest


def build_summary(discarded: list) -> str:
    if not discarded:
        return ""

    topics = set()
    last_error = ""
    for m in discarded:
        c = m.get("content", "")
        if isinstance(c, str) and "error" in c.lower() and len(c) < 500:
            last_error = c

    lines = ["[Summary of earlier context]"]
    if last_error:
        lines.append(f"Last encountered error: {last_error[:200]}")
    lines.append(f"(Approximately {len(discarded)} earlier messages compressed)")

    return "\n".join(lines)
