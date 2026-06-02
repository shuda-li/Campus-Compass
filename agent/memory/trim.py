import json

# 软预算：超过此值开始发出效率提醒（不删除消息，保护前缀缓存）
DEFAULT_TOKEN_BUDGET = 8000

# 硬预算：接近模型上下文上限，必须压缩（会破坏一次缓存，但仅紧急时触发）
# DeepSeek V4 上下文窗口 128K，留 50% 安全余量
HARD_TOKEN_BUDGET = 64000


def estimate_tokens(messages: list) -> int:
    """估算 token 数：1 token ≈ 3 字符（中文场景偏保守）"""
    total = 0
    for m in messages:
        text = json.dumps(m, ensure_ascii=False)
        total += max(1, len(text) // 3)
    return total


# ── 缓存友好策略 ──────────────────────────────────────────
#
# DeepSeek 前缀缓存依赖「字节级前缀完全匹配」。
# 任何从 front 删除消息的操作都会改变后续所有字节前缀 → 全部缓存失效。
#
# 因此采用分层策略：
#   1. 软预算线（8000 tokens）：不删消息，只在下轮 scratch 中附加效率提醒
#   2. 硬预算线（64000 tokens）：生成摘要替换前半消息（一次性缓存断裂，而非每轮断裂）
#
# 这参考了 Reasonix 的 "Immutable Prefix + Append-Only Log" 架构。


def soft_trim_check(messages: list, soft_budget: int = DEFAULT_TOKEN_BUDGET,
                    hard_budget: int = HARD_TOKEN_BUDGET) -> tuple:
    """
    检查 token 预算，返回 (should_warn, should_hard_trim)。

    缓存友好的关键设计：
    - should_warn=True  → 下轮 scratch 中加入效率提醒（不删消息）
    - should_hard_trim=True → 仅在接近模型上限时触发一次性压缩
    """
    est = estimate_tokens(messages)
    return (est > soft_budget, est > hard_budget)


def hard_trim_to_budget(messages: list, budget: int = HARD_TOKEN_BUDGET) -> list:
    """
    紧急压缩：当上下文接近模型上限时，用摘要替换前半消息。

    这会破坏前缀缓存，但只在 ~64000 tokens 时触发，
    远低于 DeepSeek 128K 上限，正常情况下 15 轮 Agent 循环不会触及。
    如果触及，说明对话已经非常长，缓存断裂的代价可接受。

    策略：
    - 保留 system 消息（永远不删）
    - 保留最后 N 轮完整对话（约 4000 tokens）
    - 中间部分用一条摘要消息替代
    """
    system_msgs = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]

    # 如果总量在预算内，不动
    if estimate_tokens(system_msgs + rest) <= budget:
        return messages

    # 从尾部保留：找到最近 ~4000 tokens 的消息
    keep_tokens = min(budget // 2, 4000)
    kept = []
    kept_tokens = 0
    for m in reversed(rest):
        t = max(1, len(json.dumps(m, ensure_ascii=False)) // 3)
        if kept_tokens + t > keep_tokens and kept:
            break
        kept.insert(0, m)
        kept_tokens += t

    discarded = [m for m in rest if m not in kept]

    # 生成摘要
    summary = build_summary(discarded)
    summary_msg = {"role": "system", "content": summary}

    # 结果：system 消息 + 摘要 + 保留的尾部消息
    result = system_msgs + [summary_msg] + kept
    return result


# ── 保留旧接口（向后兼容）──────────────────────────────────

def trim_to_budget(messages: list, budget: int = DEFAULT_TOKEN_BUDGET) -> list:
    """
    [已弃用] 旧版裁剪函数——会从头部删除消息，破坏前缀缓存。

    现在直接返回原消息列表，不做删除。
    预算管理已迁移到 agent_loop.py 的 scratch 机制。
    紧急压缩使用 hard_trim_to_budget()。
    """
    return messages


def build_summary(discarded: list) -> str:
    """为被裁剪的消息生成压缩摘要"""
    if not discarded:
        return ""

    # 提取关键信息
    user_msgs = []
    tool_results = []
    last_error = ""

    for m in discarded:
        role = m.get("role", "")
        c = m.get("content", "")
        if isinstance(c, str):
            if role == "user" and len(c) > 20:
                user_msgs.append(c[:120])
            elif role == "tool":
                try:
                    d = json.loads(c)
                    if d.get("ok"):
                        tool_results.append("✓")
                    else:
                        tool_results.append(f"✗{d.get('error', '')[:60]}")
                except Exception:
                    pass
            if "error" in c.lower() and len(c) < 500:
                last_error = c

    lines = ["[上下文摘要 — 早期对话已压缩]"]
    if user_msgs:
        lines.append(f"用户曾询问: {'; '.join(user_msgs[-3:])}")
    if tool_results:
        ok_count = sum(1 for t in tool_results if t == "✓")
        lines.append(f"工具调用: {ok_count}/{len(tool_results)} 成功")
    if last_error:
        lines.append(f"最后错误: {last_error[:200]}")
    lines.append(f"(约 {len(discarded)} 条早期消息已压缩)")

    return "\n".join(lines)
