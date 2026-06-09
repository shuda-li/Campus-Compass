"""
Plan 直接补丁引擎 —— 确定性修改不走 LLM

对于简单、可确定的值变更（时间/主办方/承办方/人数），直接从
用户输入中提取新值，原地 patch Plan JSON，无需 LLM 参与。

复杂修改（增删环节、改写内容、调整物资结构）仍走 LLM，但以
last_plan 为 base 进行修改而非重新生成。

用法:
    from engine.plan_patcher import classify_modification, deterministic_patch

    mode, patches = classify_modification(anchors, intents, user_msg)
    if mode == "deterministic":
        new_plan, changes = deterministic_patch(last_plan, patches)
        # → 直接 rebuild HTML，跳过 LLM
    else:
        # → 走 LLM base-plan 修改模式
"""
import re
from datetime import datetime
from typing import Optional


# ── 字段 → 提取新值的 regex 模式 ──
# 格式：(regex_pattern, value_group_index, transform_fn)
_VALUE_EXTRACTORS = {
    "activity_time": [
        # "把活动时间改为27年2月3号" → "27年2月3号"
        (r'(?:改为|改成|换成|变更为|修改为|调整为|改成|变更成)\s*(\d{1,2})\s*[年\-\/]\s*(\d{1,2})\s*[月\-\/]\s*(\d{1,2})\s*[号日]?', "date"),
        # "改成2027-02-03"
        (r'(?:改为|改成|换成|变更为|修改为)\s*(\d{4}[年\-\/]\d{1,2}[月\-\/]\d{1,2}[号日]?)', 1),
        # "把时间改成明天下午3点" — 太模糊，跳过
    ],
    "organizer": [
        # "把主办单位改成电竞社"
        (r'(?:主办单位|主办方|主办|组织单位|组织方)\s*(?:改为|改成|换成|变更为|修改为|换成)\s*(.+?)(?:$|，|。|,|\.|\s{2})', 1),
    ],
    "host": [
        # "把承办单位改成学生会"
        (r'(?:承办单位|承办方|承办|协办单位|协办方)\s*(?:改为|改成|换成|变更为|修改为|换成)\s*(.+?)(?:$|，|。|,|\.|\s{2})', 1),
    ],
    "participants": [
        # "人数改成200人" → 200
        (r'(?:人数|参与人数|参加人数)\s*(?:改为|改成|换成|变更为|修改为|调整[为到])\s*(\d+)', 1),
        # "改成200人"
        (r'(?:改为|改成|换成|变更为|修改为|调整[为到])\s*(\d+)\s*(?:人|位|名)?', 1),
    ],
}

# ── 确定性修改支持的字段类型 ──
DETERMINISTIC_FIELDS = {
    "activity_time",   # 时间变更
    "organizer",       # 主办单位
    "host",            # 承办单位
    "participants",    # 参与人数
}


def _normalize_date(raw: str) -> str:
    """将各种日期格式统一为 'YYYY年MM月DD日'。"""
    # 匹配 "27年2月3号"
    m = re.match(r'(\d{1,2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[号日]?', raw)
    if m:
        y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # 2 位年份 → 加 2000
        if y < 100:
            y += 2000
        return f"{y}年{mth}月{d}日"

    # 匹配 "2027-02-03" 或 "2027/02/03"
    m = re.match(r'(\d{4})[年\-\/](\d{1,2})[月\-\/](\d{1,2})[号日]?', raw)
    if m:
        return f"{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日"

    return raw.strip()


def _normalize_org_name(raw: str) -> str:
    """清理提取的组织名称。"""
    raw = raw.strip()
    # 去掉尾部多余的标点
    raw = re.sub(r'[，。,\.\s]+$', '', raw)
    # 去掉可能的引号
    raw = raw.strip('"\'""「」')
    return raw


def _extract_by_type(user_msg: str, field_type: str, anchor_value: str = None) -> Optional[str]:
    """根据字段类型从用户输入中提取新值。返回 None 表示提取失败。"""
    extractors = _VALUE_EXTRACTORS.get(field_type, [])

    for extractor in extractors:
        pattern = extractor[0]
        group = extractor[1]

        m = re.search(pattern, user_msg)
        if not m:
            continue

        if group == "date":
            # 3 组日期匹配
            try:
                y, mth, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if y < 100:
                    y += 2000
                return f"{y}年{mth}月{d}日"
            except (ValueError, IndexError):
                continue
        else:
            raw = m.group(group)
            if field_type == "activity_time":
                return _normalize_date(raw)
            elif field_type in ("organizer", "host"):
                return _normalize_org_name(raw)
            else:
                return raw.strip()

    return None


def _extract_participants_from_intent(intent_value: str) -> Optional[int]:
    """从 intent_detector 的 value 中提取参与人数。"""
    m = re.search(r'(\d+)', str(intent_value))
    if m:
        return int(m.group(1))
    return None


def classify_modification(anchors: list[dict], intents: list[dict],
                           user_msg: str) -> tuple[str, list[dict]]:
    """
    分类修改类型，决定走确定性补丁还是 LLM。

    Returns:
        ("deterministic", patches) — 可以直接 patch JSON
        ("llm", None) — 需要 LLM 参与
    """
    patches = []

    # ── 从 intent_detector 提取确定值 ──
    for intent in intents:
        itype = intent.get("type", "")
        ivalue = intent.get("value", "")

        if itype == "time":
            normalized = _normalize_date(ivalue)
            if normalized:
                patches.append({"field": "activity_time", "value": normalized,
                                "source": "intent_detector"})

        elif itype == "participants":
            num = _extract_participants_from_intent(ivalue)
            if num and num > 0:
                patches.append({"field": "participants", "value": num,
                                "source": "intent_detector"})

        elif itype == "venue":
            # 场地不在 plan JSON 中（由 engine 查询），跳过
            pass

    # ── 从 anchor 提取确定值（补充 intent 未覆盖的字段）──
    fields_already = {p["field"] for p in patches}
    for anchor in anchors:
        section = anchor.get("section", "")
        if section not in DETERMINISTIC_FIELDS:
            continue
        if section in fields_already:
            continue

        anchor_val = anchor.get("value", "")
        new_val = _extract_by_type(user_msg, section, anchor_val)
        if new_val:
            patches.append({"field": section, "value": new_val,
                            "source": "anchor"})
            fields_already.add(section)

    if not patches:
        return "llm", None

    # ── 检查是否有非确定性 anchor 需要 LLM ──
    # 仅考虑高置信度 anchor（exact 匹配）；子串/模糊匹配可能是噪声
    for anchor in anchors:
        section = anchor.get("section", "")
        match_type = anchor.get("match_type", "")
        if section not in DETERMINISTIC_FIELDS and match_type == "exact":
            # 如 activity_content、activity_materials 的精确匹配 — 确实需要 LLM
            return "llm", None

    return "deterministic", patches


def deterministic_patch(plan: dict, patches: list[dict]) -> tuple[dict, list[str]]:
    """
    原地修改 plan dict（会修改传入的 plan）。

    Returns:
        (patched_plan, change_log) — 修改后的 plan 和变更日志列表
    """
    change_log = []

    for patch in patches:
        field = patch["field"]
        new_value = patch["value"]
        old_value = plan.get(field, "(无)")

        if field == "participants":
            # participants 存在 state 上而非 plan 中，返回标记
            plan["_participants_override"] = new_value
            change_log.append(f"参与人数: {old_value} → {new_value}人")
        else:
            plan[field] = new_value
            change_log.append(f"{field}: {old_value} → {new_value}")

    return plan, change_log


def build_base_plan_prompt(last_plan: dict, user_msg: str, anchors: list[dict] = None,
                            intents: list[dict] = None) -> str:
    """
    构建 base-plan 修改模式的 prompt 片段。

    将原始 plan JSON 传给 LLM，并指示只修改相关部分。
    """
    import json as _json

    parts = []

    parts.append("===== 📋 当前方案（请在此基础上修改，不要重新生成）=====")
    plan_json = _json.dumps(last_plan, ensure_ascii=False, indent=2)
    # 截断过长内容
    if len(plan_json) > 3000:
        plan_json = plan_json[:3000] + "\n... (已截断)"
    parts.append(plan_json)
    parts.append("===========================================")

    parts.append(f"\n用户修改请求：{user_msg}")

    if anchors:
        from engine.plan_anchor import format_anchor_hint
        parts.append(format_anchor_hint(anchors, last_plan))

    if intents:
        from engine.intent_detector import apply_intents_to_prompt
        parts.append(apply_intents_to_prompt(intents))

    parts.append("\n⚠️ 核心要求：")
    parts.append("1. 只修改用户要求的部分，其他字段和环节必须保持原样不动")
    parts.append("2. 保持原有的 JSON 结构，不要改变字段名")
    parts.append("3. 输出完整的修改后 JSON（不是 diff）")
    parts.append("4. 如果用户要求新增环节/物资，在原数组基础上增加条目")

    return "\n".join(parts)
