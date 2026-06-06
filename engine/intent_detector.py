"""
通用修改意图检测器 —— 覆盖 时间 / 场地 / 人数 / 内容 / 预算

三层漏斗：关键词正则 → LLM 语义 → 学习沉淀
区分硬约束（"必须"、"改成"）与软偏好（"最好"、"尽量"）

用法:
    from engine.intent_detector import detect_intent, apply_intents_to_prompt
    intents = detect_intent("活动时间改为10月7号，换个大教室")
    # → [{"type": "time", "value": "2027年10月7日", "hard": True, "source": "keyword"},
    #    {"type": "venue", "value": "大容量教室", "hard": False, "source": "keyword"}]

    prompt_hint = apply_intents_to_prompt(intents)
    # → 注入到 plan_generator prompt 中
"""

import re
import json
import os
from datetime import datetime

PATTERNS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".memory", "intent_patterns.json")

# ═══════════════════════════════════════════════════
#  意图类型定义：关键词 + 正则 + 提取策略
# ═══════════════════════════════════════════════════

INTENT_SCHEMAS = {
    "time": {
        "triggers": [
            "活动时间", "时间改", "改成", "改为", "改到", "换成", "换到",
            "调整到", "调到", "修改为", "变更为", "更改为", "调整为",
            "日期", "定在", "放在", "安排到", "设在",
            "提前", "推迟", "延后", "延期", "延迟", "往后推", "往前移",
            "提前到", "推迟到", "延迟到", "什么时候", "几点", "几号",
        ],
        "patterns": [
            (r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "full_date"),
            (r"(\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "short_year"),
            (r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", "iso_date"),
            (r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", "month_day"),
            (r"(上午|下午|晚上|早晨|中午)\s*(\d{1,2})\s*[:：]\s*(\d{2})", "time_range"),
            (r"(上午|下午|晚上|早晨|中午)\s*(\d{1,2})\s*点", "time_period"),
            (r"(\d{1,2})\s*[:：]\s*(\d{2})\s*[-~到至]\s*(\d{1,2})\s*[:：]\s*(\d{2})", "time_span"),
            (r"(下+)\s*周\s*([一二三四五六日天])", "next_week"),
            (r"(明|后)\s*天", "relative_day"),
        ],
        "llm_prompt": "从以下用户消息中提取\"活动时间\"。只返回时间字符串（如\"2027年10月7日\"），无法提取则返回\"NONE\"。",
    },

    "venue": {
        "triggers": [
            "换教室", "换房间", "换场地", "换到", "换成",
            "大教室", "更大的", "小一点", "宽敞", "大一点",
            "要E", "换成E", "改到E", "换E", "改E",
            "机房", "体育", "体育馆", "田径场", "E教学楼",
            "阶梯教室", "普通教室", "录播", "模拟法庭",
            "容量", "座位", "坐得下",
        ],
        "patterns": [
            (r"[Ee]\s*(\d{3})", "room_e"),                    # E101, E507
            (r"(机房|体育[馆区场]|田径场|E教学楼)", "building"),  # 建筑名
            (r"(阶梯|普通|录播|模拟法庭|多媒体)\s*教室", "room_type"),  # 教室类型
            (r"(\d{2,3})\s*人\s*(以[上下])\s*的?\s*教室", "capacity_range"),  # 50人以上的教室
            (r"(更?大|宽敞|大一点|更大)\s*(的?\s*)?(教室|场地|房间)?", "bigger"),
            (r"(更?小|小一点|小一[点些])\s*(的?\s*)?(教室|场地|房间)?", "smaller"),
        ],
        "llm_prompt": "从以下用户消息中提取\"场地要求\"。只返回简短描述（如\"E101教室\"\"大容量阶梯教室\"\"体育区\"），无法提取则返回\"NONE\"。",
    },

    "participants": {
        "triggers": [
            "人数", "增加到", "减少到", "改成.*人", "改为.*人",
            "加到", "减到", "扩展到", "缩小到",
            "多了", "少了", "不够", "太多人",
        ],
        "patterns": [
            (r"(增加?|加到|改成|改为|扩[展充]?到|上调到?)\s*(\d{1,3})\s*(人|位|名)?", "increase"),
            (r"(减少?|减到|降到|下调到?|缩小到?)\s*(\d{1,3})\s*(人|位|名)?", "decrease"),
            (r"(\d{2,3})\s*(人|位|名)", "exact_count"),
        ],
        "llm_prompt": "从以下用户消息中提取\"参与人数\"变更。返回数字（如\"80\"）或\"NONE\"。",
    },

    "content": {
        "triggers": [
            "增加环节", "添加环节", "加一个", "去掉", "删除",
            "互动", "游戏", "讨论", "问答", "颁奖", "表演",
            "缩短", "延长", "扩展", "精简", "合并",
            "开场", "闭幕", "致辞", "分享", "交流",
        ],
        "patterns": [
            (r"增加\s*(.{1,10}?)\s*(环节|部分|阶段)", "add_phase"),
            (r"去掉\s*(.{1,10}?)\s*(环节|部分|阶段)", "remove_phase"),
            (r"缩短\s*(.{1,10}?)\s*(环节|部分|阶段)?", "shorten"),
            (r"延长\s*(.{1,10}?)\s*(环节|部分|阶段)?", "extend"),
            (r"(增加|加强|多一些)\s*(互动|游戏|讨论|交流)", "add_interaction"),
        ],
        "llm_prompt": "从以下用户消息中提取\"活动内容修改要求\"。返回简短描述（如\"增加互动环节\"\"去掉开场致辞\"），无法提取则返回\"NONE\"。",
    },

    "budget": {
        "triggers": [
            "预算", "费用", "花费", "成本", "资金",
            "控制在", "限制", "不超过", "大约",
        ],
        "patterns": [
            (r"预算\s*(控制?在?|不?超过?|限制?在?)?\s*(\d{2,5})\s*(元|块)?", "budget_limit"),
            (r"(\d{2,5})\s*(元|块)\s*(以[下内]|预算)", "budget_limit2"),
            (r"预算\s*(减半|减\s*半|砍半|对半)", "budget_half"),
        ],
        "llm_prompt": "从以下用户消息中提取\"预算要求\"。返回金额（如\"500元\"）或简短描述，无法提取则返回\"NONE\"。",
    },
}


# ═══════════════════════════════════════════════════
#  硬约束 vs 软偏好
# ═══════════════════════════════════════════════════

HARD_CONSTRAINT_KEYWORDS = [
    "必须", "一定", "务必", "改成", "改为", "换成", "换到",
    "改到", "修改为", "变更为", "要", "就要", "只要",
]

SOFT_PREFERENCE_KEYWORDS = [
    "最好", "尽量", "可以的话", "如果可以的", "优先",
    "差不多", "大概", "左右", "稍微", "建议",
]


def _classify_hardness(full_text: str, match_start: int = 0, match_end: int = 0) -> bool:
    """
    判断是否为硬约束。按句子分隔符拆分后，只检查匹配位置所在的分句。
    偏向硬约束：默认 True，只有所在分句中明确出现软偏好词才返回 False。
    """
    # 找到匹配位置所在的分句
    clause_start = 0
    clause_end = len(full_text)
    for sep in ['，', '。', '！', '？', '；', ',', '.', '!', '?', ';']:
        # 找匹配位置之前的最近分隔符
        pos = full_text.rfind(sep, 0, match_start)
        if pos != -1 and pos + 1 > clause_start:
            clause_start = pos + 1
        # 找匹配位置之后的最近分隔符
        pos = full_text.find(sep, match_end)
        if pos != -1 and pos < clause_end:
            clause_end = pos

    clause = full_text[clause_start:clause_end]

    # 先检查软偏好（优先级高）
    for kw in SOFT_PREFERENCE_KEYWORDS:
        if kw in clause:
            return False
    # 再检查硬约束
    for kw in HARD_CONSTRAINT_KEYWORDS:
        if kw in clause:
            return True
    return True  # 默认硬约束


# ═══════════════════════════════════════════════════
#  值提取器
# ═══════════════════════════════════════════════════

def _extract_time(match, ptype: str) -> str | None:
    try:
        if ptype == "full_date":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{y}年{m}月{d}日"
        elif ptype == "short_year":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{2000 + y if y < 100 else y}年{m}月{d}日"
        elif ptype == "iso_date":
            y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
            return f"{y}年{m}月{d}日"
        elif ptype == "month_day":
            m, d = int(match.group(1)), int(match.group(2))
            y = datetime.now().year
            if m < datetime.now().month:
                y += 1
            return f"{y}年{m}月{d}日"
        elif ptype in ("time_range", "time_period", "time_span",
                        "next_week", "relative_day"):
            return match.group(0)
    except (ValueError, IndexError):
        pass
    return None


def _extract_venue(match, ptype: str) -> str | None:
    if ptype == "room_e":
        return f"E{match.group(1)}教室"
    elif ptype == "building":
        return match.group(1)
    elif ptype == "room_type":
        return f"{match.group(1)}教室"
    elif ptype == "capacity_range":
        count, direction = int(match.group(1)), match.group(2)
        return f"{count}人{direction}的教室"
    elif ptype in ("bigger", "smaller"):
        return "更大容量教室" if ptype == "bigger" else "更小容量教室"
    return None


def _extract_participants(match, ptype: str) -> str | None:
    try:
        if ptype in ("increase", "decrease", "exact_count"):
            return match.group(2) if ptype != "exact_count" else match.group(1)
    except (ValueError, IndexError):
        pass
    return None


def _extract_content(match, ptype: str) -> str | None:
    return match.group(0)


def _extract_budget(match, ptype: str) -> str | None:
    if ptype == "budget_limit":
        return f"{match.group(2)}元"
    elif ptype == "budget_limit2":
        return f"{match.group(1)}元"
    elif ptype == "budget_half":
        return "减半"
    return None


_EXTRACTORS = {
    "time": _extract_time,
    "venue": _extract_venue,
    "participants": _extract_participants,
    "content": _extract_content,
    "budget": _extract_budget,
}


# ═══════════════════════════════════════════════════
#  学习机制（Token 集合匹配，替代全文正则）
# ═══════════════════════════════════════════════════

def _load_patterns() -> dict:
    try:
        if os.path.exists(PATTERNS_FILE):
            with open(PATTERNS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"entries": []}


def _save_patterns(entries: list):
    try:
        os.makedirs(os.path.dirname(PATTERNS_FILE), exist_ok=True)
        # 去重 + 上限
        seen = set()
        deduped = []
        for e in reversed(entries):
            key = e.get("raw", "")
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        deduped.reverse()
        deduped = deduped[-100:]
        with open(PATTERNS_FILE, "w", encoding="utf-8") as f:
            json.dump({"entries": deduped, "updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[IntentDetector] 保存失败: {e}")


def _tokenize(text: str) -> set:
    """将中文文本拆分为 2-3 字 token 集合，用于模糊匹配。"""
    tokens = set()
    # 提取关键词：日期、数字、中文词
    for m in re.finditer(r'\d+|[一-龥]{2,3}', text):
        tokens.add(m.group(0))
    return tokens


def _token_similarity(tokens_a: set, tokens_b: set) -> float:
    """Jaccard 相似度。"""
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _match_learned(intent_type: str, text: str) -> str | None:
    """
    用 token 相似度匹配历史学习数据。
    相似度 ≥ 0.6 → 复用历史提取结果。
    """
    data = _load_patterns()
    tokens = _tokenize(text)
    best_score = 0.0
    best_value = None

    for entry in data.get("entries", []):
        if entry.get("type") != intent_type:
            continue
        stored_tokens = set(entry.get("tokens", []))
        score = _token_similarity(tokens, stored_tokens)
        if score > best_score and score >= 0.6:
            best_score = score
            best_value = entry.get("value")

    if best_value:
        print(f"[IntentDetector] Token匹配 '{intent_type}': score={best_score:.2f}")
    return best_value


def _learn(intent_type: str, raw_text: str, extracted_value: str):
    """存储学习数据：token 集合 + 提取结果。"""
    data = _load_patterns()
    tokens = list(_tokenize(raw_text))
    if not tokens:
        return

    entry = {
        "type": intent_type,
        "raw": raw_text[:200],
        "tokens": tokens,
        "value": extracted_value,
        "learned_at": datetime.now().isoformat(),
    }
    data["entries"].append(entry)
    _save_patterns(data["entries"])
    print(f"[IntentDetector] 学习 '{intent_type}': {raw_text[:30]} → {extracted_value}")


# ═══════════════════════════════════════════════════
#  LLM 兜底
# ═══════════════════════════════════════════════════

def _llm_extract(intent_type: str, text: str) -> str | None:
    schema = INTENT_SCHEMAS.get(intent_type, {})
    llm_prompt = schema.get("llm_prompt", "")
    if not llm_prompt:
        return None

    try:
        from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL
        if not LLM_API_KEY:
            return None
        import requests
        from agent.proxy import get_proxy

        prompt = f'{llm_prompt}\n\n用户消息："{text}"\n\n提取结果:'
        session = requests.Session()
        session.trust_env = False
        kwargs = {"timeout": 10}
        proxy = get_proxy()
        if proxy:
            kwargs["proxies"] = proxy

        resp = session.post(
            LLM_API_URL,
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": "你是一个信息提取器。只返回提取到的值，不要解释。无法提取则返回 NONE。"},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1, "max_tokens": 50,
            },
            **kwargs,
        )
        content = resp.json()["choices"][0]["message"]["content"].strip()
        if content and content.upper() != "NONE":
            return content
    except Exception as e:
        print(f"[IntentDetector] LLM提取 '{intent_type}' 失败: {e}")
    return None


# ═══════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════

def detect_intent(user_msg: str) -> list[dict]:
    """
    从用户反馈中检测所有修改意图。

    Returns:
        [{"type": "time", "value": "2027年10月7日", "hard": True, "source": "keyword"}, ...]
    """
    if not user_msg or not user_msg.strip():
        return []

    results = []

    for intent_type, schema in INTENT_SCHEMAS.items():
        # 检查触发关键词
        has_trigger = any(kw in user_msg for kw in schema["triggers"])
        if not has_trigger:
            continue

        hard = True  # default
        value = None
        source = "keyword"
        match_start = 0
        match_end = 0

        # 第 1 层：内置正则
        for pattern, ptype in schema["patterns"]:
            m = re.search(pattern, user_msg)
            if m:
                extractor = _EXTRACTORS.get(intent_type)
                if extractor:
                    value = extractor(m, ptype)
                    if value:
                        source = "keyword"
                        match_start = m.start()
                        match_end = m.end()
                        break

        # 根据匹配位置的局部上下文判断硬/软
        hard = _classify_hardness(user_msg, match_start, match_end)

        # 第 2 层：学习数据匹配
        if not value:
            value = _match_learned(intent_type, user_msg)
            if value:
                source = "learned"

        # 第 3 层：LLM 语义分析
        if not value:
            print(f"[IntentDetector] '{intent_type}' 触发词命中但无正则匹配，调用LLM...")
            value = _llm_extract(intent_type, user_msg)
            if value:
                source = "llm"
                _learn(intent_type, user_msg, value)

        if value:
            results.append({
                "type": intent_type,
                "value": value,
                "hard": hard,
                "source": source,
            })

    return results


def apply_intents_to_prompt(intents: list[dict]) -> str:
    """
    将检测到的意图格式化为 prompt 提示块。
    硬约束用 ⚠️ 警告格式，软偏好用 💡 建议格式。
    """
    if not intents:
        return ""

    hard_parts = []
    soft_parts = []

    type_labels = {
        "time": "活动时间",
        "venue": "场地要求",
        "participants": "参与人数",
        "content": "活动内容",
        "budget": "预算限制",
    }

    for intent in intents:
        label = type_labels.get(intent["type"], intent["type"])
        line = f"  - {label}：{intent['value']}"
        if intent["hard"]:
            hard_parts.append(line)
        else:
            soft_parts.append(line)

    result = ""
    if hard_parts:
        result += "\n===== ⚠️ 用户明确要求的修改（必须遵守）=====\n"
        result += "\n".join(hard_parts)
        result += "\n请严格遵守以上要求，不要自行修改。\n==========================================\n"
    if soft_parts:
        result += "\n===== 💡 用户偏好的调整（尽量满足）=====\n"
        result += "\n".join(soft_parts)
        result += "\n请在合理范围内尽量满足以上偏好。\n==========================================\n"

    return result
