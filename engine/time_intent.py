"""
时间意图检测器 — 三层匹配：关键词正则 → LLM语义分析 → 学习沉淀

用法:
    from engine.time_intent import detect_time_intent
    result = detect_time_intent("活动时间改为27年10月7号")
    # → {"time_str": "2027年10月7日", "source": "keyword", "matched": "27年10月7号"}
    # → None 如果没有检测到时间意图
"""

import re
import json
import os
from datetime import datetime

# ── 持久化学习模式文件 ──
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".memory", "time_patterns.json")


# ═══════════════════════════════════════════════════
#  第 1 层：时间变更意图关键词（快速路径）
# ═══════════════════════════════════════════════════

TIME_CHANGE_TRIGGERS = [
    # 直接时间变更
    "活动时间", "时间改", "改成", "改为", "改到", "换成", "换到",
    "调整到", "调到", "修改为", "变更为", "更改为", "调整为",
    # 日期相关
    "日期", "定在", "放在", "安排到", "设在",
    # 时间推移
    "提前", "推迟", "延后", "延期", "延迟", "往后推", "往前移", "提前到", "推迟到", "延迟到",
    # 疑问（询问当前时间）
    "什么时候", "几点", "几号", "哪一天", "哪一天",
    # 明确指定
    "定于", "暂定", "拟定", "计划在",
]

# 内置时间正则库
BUILTIN_TIME_PATTERNS = [
    # 优先级高：完整年月日
    (r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "full"),    # 2027年10月7日
    (r"(\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "short_year"), # 27年10月7号
    (r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", "iso"),                       # 2027-10-07
    # 月日（今年）
    (r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "month_day"),                 # 10月7日
    # 上午/下午 N点（无冒号）
    (r"(上午|下午|晚上|早晨|中午)\s*(\d{1,2})\s*点", "time_period"),
    # 相对时间
    (r"(下+)\s*周\s*([一二三四五六日天])", "next_week"),
    (r"(下+)\s*个?\s*月\s*(\d{1,2})\s*[日号]?", "next_month"),
    (r"(明|后)\s*天", "relative_day"),
    # 时间段
    (r"(上午|下午|晚上|早晨|中午)\s*(\d{1,2})\s*[:：]\s*(\d{2})", "time_range"),
    (r"(\d{1,2})\s*[:：]\s*(\d{2})\s*[-~到至]\s*(\d{1,2})\s*[:：]\s*(\d{2})", "time_span"),
]


def _resolve_time(match, pattern_type: str) -> str | None:
    """将正则匹配结果解析为标准时间字符串。"""
    try:
        if pattern_type == "full":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{y}年{m}月{d}日"
        elif pattern_type == "short_year":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            # 两位数年份 → 20xx
            if y < 100:
                y = 2000 + y
            return f"{y}年{m}月{d}日"
        elif pattern_type == "iso":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{y}年{m}月{d}日"
        elif pattern_type == "month_day":
            m, d = int(match.group(1)), int(match.group(2))
            y = datetime.now().year
            # 如果月份已过，可能是明年
            now_month = datetime.now().month
            if m < now_month:
                y += 1
            return f"{y}年{m}月{d}日"
        elif pattern_type == "time_period":
            period = match.group(1)
            hour = int(match.group(2))
            return f"{period}{hour}点"
        elif pattern_type == "time_range":
            period = match.group(1)
            hour, minute = int(match.group(2)), int(match.group(3))
            return f"{period}{hour}:{minute:02d}"
        elif pattern_type == "time_span":
            h1, m1, h2, m2 = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
            return f"{h1}:{m1:02d}-{h2}:{m2:02d}"
        elif pattern_type == "next_week":
            return match.group(0)  # 保留下周X原文
        elif pattern_type == "next_month":
            return match.group(0)
        elif pattern_type == "relative_day":
            return match.group(0)
    except (ValueError, IndexError):
        pass
    return None


def _load_learned_patterns() -> list:
    """加载历史学习到的时间模式。"""
    try:
        if os.path.exists(PATTERNS_FILE):
            with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("patterns", [])
    except Exception:
        pass
    return []


def _save_learned_pattern(pattern: dict):
    """将新学到的时间模式持久化。"""
    try:
        os.makedirs(os.path.dirname(PATTERNS_FILE), exist_ok=True)
        existing = _load_learned_patterns()
        # 去重：同原始文本覆盖
        existing = [p for p in existing if p.get("raw") != pattern.get("raw")]
        existing.append(pattern)
        # 最多保留 50 条
        existing = existing[-50:]
        with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump({"patterns": existing, "updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TimeIntent] 保存学习模式失败: {e}")


def _has_time_keywords(text: str) -> bool:
    """检查文本是否包含时间变更意图关键词。"""
    for kw in TIME_CHANGE_TRIGGERS:
        if kw in text:
            return True
    return False


def _keyword_match(text: str) -> dict | None:
    """
    第 1 层：关键词 + 正则匹配。
    先用内置模式 + 学习到的模式尝试提取时间。
    返回 {"time_str": ..., "matched": ..., "source": "keyword"} 或 None。
    """
    # 先检查是否有时间意图关键词
    if not _has_time_keywords(text):
        return None

    # 尝试内置模式
    for pattern, ptype in BUILTIN_TIME_PATTERNS:
        m = re.search(pattern, text)
        if m:
            resolved = _resolve_time(m, ptype)
            if resolved:
                return {
                    "time_str": resolved,
                    "matched": m.group(0),
                    "source": "keyword",
                    "pattern_type": ptype,
                }

    # 尝试学习到的模式
    for lp in _load_learned_patterns():
        try:
            regex = lp.get("regex", "")
            if regex and re.search(regex, text):
                return {
                    "time_str": lp.get("time_str", ""),
                    "matched": lp.get("raw", ""),
                    "source": "learned",
                    "pattern_type": "learned",
                }
        except re.error:
            continue

    # 有意图关键词但没有匹配到具体时间 → 返回标记让调用方走 LLM
    return {"time_str": None, "matched": None, "source": "intent_only"}


def _llm_extract_time(text: str) -> str | None:
    """
    第 2 层：语义分析 —— 调用 LLM 从用户消息中提取时间。
    返回标准时间字符串或 None。
    """
    try:
        from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
        if not LLM_API_KEY:
            return None

        import requests
        from agent.proxy import get_proxy

        prompt = f"""从以下用户消息中提取"活动时间"。只返回提取到的时间字符串（如"2027年10月7日"），如果无法提取则返回"NONE"。

用户消息："{text}"

时间字符串:"""

        session = requests.Session()
        session.trust_env = False
        kwargs = {"timeout": 10}
        proxy = get_proxy()
        if proxy:
            kwargs["proxies"] = proxy

        resp = session.post(
            LLM_API_URL,
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是一个时间提取器。只返回提取到的时间，不要任何解释。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 50,
            },
            **kwargs,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()

        if content and content.upper() != "NONE":
            return content
    except Exception as e:
        print(f"[TimeIntent] LLM提取失败: {e}")

    return None


def _learn_from_llm(user_msg: str, extracted_time: str):
    """
    第 3 层：学习 —— 将 LLM 成功提取的案例沉淀为可复用的正则模式。
    """
    # 从用户消息中提取可能的模式片段
    # 尝试找到时间在原文中的位置并生成一个简单的包含式正则
    # 例："活动时间改为27年10月7号" → regex: r"27\s*年\s*10\s*月\s*7\s*[日号]"
    import re as _re

    # 提取消息中的数字序列作为锚点
    numbers = _re.findall(r'\d+', user_msg)
    time_numbers = _re.findall(r'\d+', extracted_time)

    if numbers and time_numbers:
        # 生成灵活匹配正则
        escaped = _re.escape(user_msg)
        # 将关键数字替换为 \d+ 通配
        for n in sorted(set(numbers), key=len, reverse=True):
            escaped = escaped.replace(n, r"\d+", 1)
        # 简化：保留核心结构
        pattern = {
            "raw": user_msg,
            "regex": escaped,
            "time_str": extracted_time,
            "learned_at": datetime.now().isoformat(),
        }
        _save_learned_pattern(pattern)
        print(f"[TimeIntent] 学习新模式: {user_msg[:30]} → {extracted_time}")
    else:
        # 兜底：保存原文作为精确匹配模式
        pattern = {
            "raw": user_msg,
            "regex": _re.escape(user_msg),
            "time_str": extracted_time,
            "learned_at": datetime.now().isoformat(),
        }
        _save_learned_pattern(pattern)


def detect_time_intent(user_msg: str) -> dict | None:
    """
    主入口：检测用户消息中的时间变更意图。

    三阶段流程：
      1. 关键词 + 正则（毫秒级）
      2. 意图存在但无匹配 → LLM 语义分析（~1s）
      3. LLM 成功 → 沉淀为可复用模式

    Returns:
        None — 没有时间变更意图
        {"time_str": "2027年10月7日", "source": "keyword|learned|llm", "matched": "..."}
    """
    if not user_msg or not user_msg.strip():
        return None

    # Step 1: 关键词 + 正则匹配
    result = _keyword_match(user_msg)

    if result is None:
        # 完全没有时间意图
        return None

    if result["time_str"] is not None:
        # 匹配成功（内置模式或学习模式）
        return result

    # Step 2: 有意图但无具体时间匹配 → LLM 语义分析
    print(f"[TimeIntent] 检测到时间变更意图但无正则匹配，调用LLM: {user_msg[:50]}")
    extracted = _llm_extract_time(user_msg)

    if extracted:
        # Step 3: LLM 成功 → 学习沉淀
        _learn_from_llm(user_msg, extracted)
        return {
            "time_str": extracted,
            "matched": user_msg,
            "source": "llm",
            "pattern_type": "llm",
        }

    # LLM 也失败了，但有意图关键词，返回一个标记
    return {"time_str": None, "matched": None, "source": "intent_unresolved"}


def get_time_override_hint(time_intent: dict) -> str:
    """
    将检测到的时间意图格式化为 prompt 提示语。
    用于注入到 plan_generator 的 prompt 中。
    """
    time_str = time_intent.get("time_str", "")
    source = time_intent.get("source", "")

    if not time_str:
        return ""

    return (
        f"\n\n【用户时间要求】\n"
        f"用户明确要求将活动时间设为：**{time_str}**\n"
        f"请在生成方案时严格遵守此时间，不要自行推断或修改。\n"
    )
