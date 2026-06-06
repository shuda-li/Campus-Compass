"""
Plan-Aware 关键词锚定 —— 从用户反馈中定位要修改的 Plan 元素。

核心思路（用户的洞察）：
  用户提出改进时，其输入必然与刚生成的方案存在关键词重叠。
  通过反向匹配（plan 词 → user feedback），精准定位要修改的目标。

三层匹配策略：
  1. 精确匹配：feedback 包含 plan 关键词原文
  2. 子串匹配：feedback 包含 plan 关键词的一部分（≥2 字）
  3. 模糊匹配：编辑距离 ≤ 1（同义/错别字容错）

用法:
    from engine.plan_anchor import build_plan_index, anchor_feedback, format_anchor_hint

    # 生成 plan 后
    plan_index = build_plan_index(plan)
    state["plan_index"] = plan_index
    state["last_plan"] = plan

    # 用户反馈时
    anchors = anchor_feedback(plan, feedback)
    hint = format_anchor_hint(anchors, plan)
    # → 注入到 prompt 中
"""

import re
from typing import Any

# ── 从 plan 中提取关键词的字段配置 ──
# (section, field, weight) — weight 越大越优先提取
INDEXABLE_FIELDS = [
    # activity_content 各环节
    ("activity_content", "phase", 3),       # "开幕致辞" — 最重要
    ("activity_content", "content", 1),     # 内容描述中的关键词
    ("activity_content", "interaction", 1), # "问答+讨论"
    ("activity_content", "host_guide", 1),  # 引导语
    # activity_materials
    ("activity_materials", "name", 3),      # "投影仪"
    ("activity_materials", "spec", 1),      # "高清"
    # 顶层字段
    ("activity_purpose", None, 2),          # 活动目的
    ("activity_time", None, 3),            # 活动时间
    ("organizer", None, 1),
    ("host", None, 1),
]

# ── 字段名 → 中文别名（用户反馈中常用的说法）──
# 用户说"主办单位"时要能锚定到 organizer 字段
FIELD_ALIASES = {
    "organizer": ["主办单位", "主办方", "主办", "组织单位", "组织方"],
    "host": ["承办单位", "承办方", "承办", "协办单位", "协办方"],
    "activity_time": ["活动时间", "时间", "日期", "什么时候", "几点"],
    "activity_purpose": ["活动目的", "目的", "宗旨", "目标"],
    "activity_content": ["活动环节", "环节", "流程", "内容"],
    "activity_materials": ["物资", "材料", "设备", "道具", "用品"],
}

# ── 停用词（太通用，不参与匹配）──
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "这个", "那个", "什么", "怎么", "如何", "可以", "我们", "他们",
    "进行", "通过", "以及", "或者", "还是", "因为", "所以", "但是", "然而",
    "分钟", "小时", "环节", "部分", "内容", "方式", "互动", "引导",
}


def _tokenize(text: str, min_len: int = 2, max_len: int = 6) -> set[str]:
    """从文本中提取有意义的词 token 集合。"""
    if not text:
        return set()
    tokens = set()
    # 提取中文词（2-6 字）
    for m in re.finditer(r'[一-鿿]{%d,%d}' % (min_len, max_len), text):
        word = m.group(0)
        if word not in STOP_WORDS:
            tokens.add(word)
    # 提取数字+单位
    for m in re.finditer(r'\d+\s*[台套张把个瓶人位名元块]?', text):
        tokens.add(m.group(0).strip())
    # 提取英文/缩写
    for m in re.finditer(r'[A-Za-z0-9]{2,}', text):
        tokens.add(m.group(0))
    return tokens


def build_plan_index(plan: dict) -> dict[str, list[dict]]:
    """
    从 plan 构建倒排索引：关键词 → 位置列表。

    Returns:
        {"开幕致辞": [{"section": "activity_content", "index": 0, "field": "phase", "value": "开幕致辞"}], ...}
    """
    index: dict[str, list[dict]] = {}

    def _add(keyword: str, location: dict):
        if not keyword or len(keyword) < 2:
            return
        if keyword in STOP_WORDS:
            return
        if keyword not in index:
            index[keyword] = []
        # 去重：同关键词同位置只存一次
        for existing in index[keyword]:
            if (existing.get("section") == location["section"]
                    and existing.get("index") == location.get("index")
                    and existing.get("field") == location.get("field")):
                return
        index[keyword].append(location)

    for section, field, weight in INDEXABLE_FIELDS:
        if field is None:
            # 顶层标量字段（如 activity_time, organizer）
            value = plan.get(section, "")
            if isinstance(value, str) and value:
                for token in _tokenize(value):
                    _add(token, {"section": section, "field": "_top", "value": value, "weight": weight})
        else:
            # 数组字段（如 activity_content[].phase）
            items = plan.get(section, [])
            if not isinstance(items, list):
                items = [items] if items else []
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                field_value = item.get(field, "")
                if isinstance(field_value, str) and field_value:
                    for token in _tokenize(field_value):
                        _add(token, {
                            "section": section,
                            "index": i,
                            "field": field,
                            "value": field_value,
                            "weight": weight,
                            "full_item": item,
                        })

    # ── 注入字段别名：用户说"主办单位"能锚定到 organizer ──
    for section, aliases in FIELD_ALIASES.items():
        value = plan.get(section, "")
        location = {"section": section, "field": "_top", "value": value, "weight": 3}
        for alias in aliases:
            _add(alias, location)

    return index


def _substring_match(feedback: str, keyword: str) -> bool:
    """子串匹配：feedback 包含 keyword 或 keyword 包含 feedback 的一部分。"""
    if len(keyword) < 2:
        return False
    # keyword 出现在 feedback 中
    if keyword in feedback:
        return True
    # keyword 的子串（≥2 字）出现在 feedback 中
    for i in range(len(keyword) - 1):
        for j in range(i + 2, len(keyword) + 1):
            sub = keyword[i:j]
            if sub in feedback:
                return True
    return False


def _fuzzy_match(feedback: str, keyword: str) -> float:
    """模糊匹配：编辑距离 / len(keyword)，返回相似度 0~1。"""
    if len(keyword) < 2:
        return 0.0

    # 简单编辑距离（Levenshtein）
    def levenshtein(a: str, b: str) -> int:
        if len(a) < len(b):
            a, b = b, a
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(
                    prev[j + 1] + 1,      # deletion
                    curr[j] + 1,           # insertion
                    prev[j] + (0 if ca == cb else 1),  # substitution
                ))
            prev = curr
        return prev[-1]

    dist = levenshtein(keyword, feedback[:len(keyword) + 2])
    max_len = max(len(keyword), 1)
    similarity = 1.0 - (dist / max_len)
    return max(0.0, similarity)


def anchor_feedback(plan: dict, feedback: str) -> list[dict]:
    """
    从用户反馈中锚定要修改的 plan 元素。

    三步策略：
      1. 精确匹配（exact）：feedback 包含 plan 关键词
      2. 子串匹配（substring）：部分重叠
      3. 模糊匹配（fuzzy）：编辑距离 ≤ 1

    Returns:
        [{"keyword": "开幕致辞", "section": "activity_content", "index": 0,
          "field": "phase", "value": "开幕致辞", "match_type": "exact",
          "confidence": 1.0, "full_item": {...}}, ...]
    """
    if not plan or not feedback:
        return []

    plan_index = build_plan_index(plan)
    if not plan_index:
        return []

    exact_matches = []
    substring_matches = []
    fuzzy_matches = []

    for keyword, locations in plan_index.items():
        # 第 1 层：精确匹配
        if keyword in feedback:
            for loc in locations:
                exact_matches.append({
                    "keyword": keyword,
                    **loc,
                    "match_type": "exact",
                    "confidence": 1.0,
                })
            continue

        # 第 2 层：子串匹配
        if _substring_match(feedback, keyword):
            for loc in locations:
                substring_matches.append({
                    "keyword": keyword,
                    **loc,
                    "match_type": "substring",
                    "confidence": 0.7,
                })
            continue

        # 第 3 层：模糊匹配
        sim = _fuzzy_match(feedback, keyword)
        if sim >= 0.6:
            for loc in locations:
                fuzzy_matches.append({
                    "keyword": keyword,
                    **loc,
                    "match_type": "fuzzy",
                    "confidence": sim,
                })

    # 合并：精确优先，去重
    seen = set()
    results = []

    for match in exact_matches + substring_matches + fuzzy_matches:
        key = (match["section"], match.get("index", -1), match.get("field", ""))
        if key not in seen:
            seen.add(key)
            results.append(match)

    # 按 weight 降序 + confidence 降序
    results.sort(key=lambda m: (m.get("weight", 0), m["confidence"]), reverse=True)

    return results


def format_anchor_hint(anchors: list[dict], plan: dict) -> str:
    """
    将锚定结果格式化为 prompt 提示块。
    包含「要修改什么」和「原内容是什么」。
    """
    if not anchors:
        return ""

    lines = []
    lines.append("===== 🎯 关键词锚定：已定位到以下要修改的 Plan 元素 =====")

    for a in anchors[:5]:  # 最多展示 5 个锚点
        section = a["section"]
        keyword = a["keyword"]
        match_type = a["match_type"]

        if section == "activity_content" and "full_item" in a:
            item = a["full_item"]
            idx = a.get("index", 0)
            lines.append(f"\n  📍 活动环节 [{idx}]「{keyword}」({match_type} 匹配)")
            lines.append(f"     当前内容：phase={item.get('phase','')}, duration={item.get('duration','')}")
            lines.append(f"     content={item.get('content','')[:60]}...")
            lines.append(f"     → 用户要求修改此环节，请基于反馈进行调整，保持其他环节不变")
        elif section == "activity_materials" and "full_item" in a:
            item = a["full_item"]
            lines.append(f"\n  📍 活动物资「{keyword}」({match_type} 匹配)")
            lines.append(f"     当前内容：{item.get('name','')} ×{item.get('qty','')} ({item.get('spec','')})")
            lines.append(f"     → 用户要求修改此物资，请基于反馈进行调整")
        elif section == "activity_time":
            val = a.get("value", "")
            lines.append(f"\n  📍 活动时间「{keyword}」({match_type} 匹配)")
            lines.append(f"     当前时间：{val}")
            lines.append(f"     → 用户要求修改活动时间")
        elif section == "activity_purpose":
            val = a.get("value", "")
            lines.append(f"\n  📍 活动目的 ({match_type} 匹配)")
            lines.append(f"     当前目的摘要：{val[:80]}...")
            lines.append(f"     → 用户要求修改活动目的")
        else:
            lines.append(f"\n  📍 {section}.{a.get('field','')}「{keyword}」({match_type} 匹配)")

    lines.append("\n⚠️ 请只修改锚定的元素，不要改动未锚定的部分。")
    lines.append("==========================================\n")

    return "\n".join(lines)


def derive_intent_from_anchors(anchors: list[dict]) -> list[dict]:
    """
    从锚定结果推导 intent 类型，供 intent_detector 格式兼容。

    Returns:
        [{"type": "content", "value": "修改开幕致辞", "hard": True, "source": "anchor"}, ...]
    """
    section_to_intent = {
        "activity_time": "time",
        "activity_content": "content",
        "activity_materials": "content",
        "activity_purpose": "content",
        "organizer": "content",
        "host": "content",
    }

    intents = []
    seen_types = set()

    for a in anchors:
        intent_type = section_to_intent.get(a["section"], "content")
        if intent_type not in seen_types:
            seen_types.add(intent_type)
            intents.append({
                "type": intent_type,
                "value": f"修改{a.get('keyword','')}",
                "hard": True,
                "source": "anchor",
            })

    return intents
