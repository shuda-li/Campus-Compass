import os
import re
import json

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")


def scan_skills() -> dict:
    skills = {}
    if not os.path.isdir(SKILLS_DIR):
        return skills

    for name in os.listdir(SKILLS_DIR):
        skill_dir = os.path.join(SKILLS_DIR, name)
        md_path = os.path.join(skill_dir, "SKILL.md")
        if os.path.isdir(skill_dir) and os.path.isfile(md_path):
            skills[name] = {"dir": skill_dir, "md": md_path}
    return skills


def load_skill(name: str) -> dict:
    skills = scan_skills()
    entry = skills.get(name)
    if not entry:
        return {}

    with open(entry["md"], "r", encoding="utf-8") as f:
        text = f.read()

    skill = {
        "name": name,
        "title": _extract_section(text, r"^#\s*Skill:\s*(.+)", 1),
        "keywords": _parse_list_section(text, "触发条件", r"`([^`]+)`"),
        "phases": _parse_table(text, "标准流程"),
        "host_guides": _parse_key_value(text, "主持引导语"),
        "materials": _parse_table(text, "所需物资"),
        "constraints": _parse_key_value(text, "约束"),
    }
    return skill


def load_all_skills() -> dict:
    all_skills = {}
    for name in scan_skills():
        skill = load_skill(name)
        if skill:
            all_skills[name] = skill
    return all_skills


def match_skill(topic: str, available: dict = None) -> tuple:
    if available is None:
        available = load_all_skills()

    scores = {}
    for name, skill in available.items():
        kw = skill.get("keywords", [])
        score = sum(1 for k in kw if k in topic)
        if score > 0:
            scores[name] = score

    if scores:
        best = max(scores, key=scores.get)
        return best, available[best]

    return "lecture_planning", available.get("lecture_planning", {})


def _extract_section(text, pattern, group=1):
    m = re.search(pattern, text, re.MULTILINE)
    if m:
        return m.group(group).strip()
    return ""


def _parse_list_section(text, section_name, item_pattern):
    block = _get_section_block(text, section_name)
    items = re.findall(item_pattern, block)
    if len(items) == 1 and " " in items[0]:
        return items[0].split()
    flat = []
    for item in items:
        if " " in item:
            flat.extend(item.split())
        else:
            flat.append(item)
    return flat


def _parse_table(text, section_name):
    block = _get_section_block(text, section_name)
    if not block:
        return []

    lines = block.strip().split("\n")
    rows = []
    in_table = False
    header_idx = -1

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and "---" not in stripped:
            if not in_table:
                in_table = True
                header_idx = i
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            rows.append(cells)

    if section_name == "标准流程":
        result = []
        for row in rows:
            if len(row) >= 4:
                result.append({
                    "phase": row[0] if len(row) > 0 else "",
                    "duration": row[1] if len(row) > 1 else "",
                    "content": row[2] if len(row) > 2 else "",
                    "interaction": row[3] if len(row) > 3 else "",
                })
        return result

    if section_name == "所需物资":
        result = []
        for row in rows:
            if len(row) >= 3:
                result.append({
                    "name": row[0] if len(row) > 0 else "",
                    "spec": row[1] if len(row) > 1 else "",
                    "qty": row[2] if len(row) > 2 else "",
                })
        return result

    return rows


def _parse_key_value(text, section_name):
    block = _get_section_block(text, section_name)
    if not block:
        return {}

    result = {}
    for line in block.strip().split("\n"):
        m = re.match(r"-\s*(.+?)[:：]\s*(.+)$", line.strip())
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            result[key] = val
    return result


def _get_section_block(text, section_name):
    pattern = rf"##\s+{re.escape(section_name)}(?:\s*\([^)]*\))?\s*\n(.*?)(?=##\s|\Z)"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""
