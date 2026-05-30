import re
import json


class AssessmentState:
    """追踪单次会话的信息补全进度"""

    def __init__(self):
        self.collected = {
            "has_time": False,        # 活动时间（日期 + 时段）
            "has_materials": False,   # 物资要求（种类 + 数量 + 规格）
            "has_personnel": False,   # 人员安排（人数 + 角色 + 职责）
        }
        self.detail = {
            "time_date": "",
            "time_period": "",
            "materials_list": [],
            "person_count": 0,
            "person_roles": [],
        }
        self.asked_order = []          # 已提问的顺序
        self._question_index = 0       # 当前提问指针
        self.all_messages = []         # 累积全部用户消息

    def feed(self, user_msg: str):
        self.all_messages.append(user_msg)

    def combined_text(self) -> str:
        return "\n".join(self.all_messages)


# 问题模板：按优先级排序
QUESTION_TEMPLATES = [
    {
        "key": "has_time",
        "anchor": "time",
        "question": "请问活动计划在**哪一天**举行？具体是什么**时段**呢？（比如 5月10日 下午14:00-16:00）",
        "retry_question": "还有，能再明确一下活动的具体**日期和时段**吗？",
    },
    {
        "key": "has_materials",
        "anchor": "materials",
        "question": "活动需要哪些**物资设备**？大概需要多少**数量**？有没有**特殊规格**要求？（比如投影仪2台、音响1套、A4打印纸200张等）",
        "retry_question": "关于物资这块，请再补充一下**种类、数量或规格**~",
    },
    {
        "key": "has_personnel",
        "anchor": "personnel",
        "question": "活动预计**多少人**参加？需要哪些**角色分工**（比如主持人、嘉宾、工作人员），各自的**职责**是什么？",
        "retry_question": "人员安排方面，能再说说**人数和角色**吗？",
    },
]


def evaluate_completeness(state: AssessmentState) -> dict:
    """
    评估当前已收集信息的完整度，返回:
    {
        "complete": True/False,
        "missing": ["time", "materials", ...],
        "next_question": "..." or None,
        "collected_summary": "..."
    }
    """
    text = state.combined_text()

    # === 检测时间信息 ===
    if _detect_time(text):
        state.collected["has_time"] = True

    # === 检测物资信息 ===
    if _detect_materials(text):
        state.collected["has_materials"] = True

    # === 检测人员信息 ===
    if _detect_personnel(text):
        state.collected["has_personnel"] = True

    missing = [k for k, v in state.collected.items() if not v]
    all_complete = len(missing) == 0

    next_q = None
    if not all_complete:
        next_q = _pick_next_question(state, missing)

    summary = _build_summary(state)

    return {
        "complete": all_complete,
        "missing": missing,
        "next_question": next_q,
        "collected_summary": summary,
        "collected": dict(state.collected),
    }


def _pick_next_question(state: AssessmentState, missing: list) -> str:
    """选出下一个要问的问题"""
    for tmpl in QUESTION_TEMPLATES:
        if tmpl["key"] in missing:
            anchor = tmpl["anchor"]
            if anchor not in state.asked_order:
                state.asked_order.append(anchor)
                return tmpl["question"]
            else:
                if state.asked_order[-1] == anchor:
                    return tmpl["retry_question"]
                state.asked_order.append(anchor)
                return tmpl["question"]

    return QUESTION_TEMPLATES[0]["question"]


def _detect_time(text: str) -> bool:
    patterns = [
        r"\d{1,2}月\d{1,2}日",       # 5月10日
        r"\d{1,2}月\d{1,2}号",
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",  # 2026-05-10
        r"下?周[一二三四五六日天]",
        r"明天|后天|今天|下周|下个月",
    ]
    for p in patterns:
        if re.search(p, text):
            return True

    time_keywords = ["上午", "下午", "晚上", "早晨", r"\d{1,2}:\d{2}", r"\d{1,2}点"]
    for tk in time_keywords:
        if re.search(tk, text):
            return True

    return False


def _detect_materials(text: str) -> bool:
    strong_keywords = [
        "需要.*台", "需要.*套", "需要.*个", "需要.*张",
        "准备.*台", "准备.*套", "准备.*个",
        r"\d+\s*台\s*\w+",        # 2台投影仪
        r"\d+\s*套\s*\w+",        # 1套音响
        r"\d+\s*张\s*\w+",        # 200张纸
        r"\d+\s*个\s*\w+",        # 3个麦克风
        r"\d+\s*把\s*\w+",        # 50把椅子
        "数量", "规格", "型号",
    ]
    for p in strong_keywords:
        if re.search(p, text):
            return True

    equipment_basic = ["投影仪", "投影", "音响", "麦克风", "白板", "黑板", "灯光",
                       "舞台", "桌椅", "电脑", "打印机", "话筒", "幕布"]
    matches = [e for e in equipment_basic if e in text]
    return len(matches) >= 2


def _detect_personnel(text: str) -> bool:
    num_match = re.search(r"(\d+)\s*(人|位|名)", text)
    has_number = num_match is not None

    role_keywords = ["主持", "嘉宾", "工作人员", "志愿者", "评委", "选手",
                     "观众", "组织者", "负责人", "讲师", "讲者", "分享者",
                     "表演", "演员", "签到", "引导", "安保", "摄影"]
    has_roles = any(k in text for k in role_keywords)

    return has_number or has_roles


def _build_summary(state: AssessmentState) -> str:
    parts = []
    if state.collected["has_time"]:
        parts.append("✅ 活动时间")
    else:
        parts.append("⬜ 活动时间")
    if state.collected["has_materials"]:
        parts.append("✅ 物资要求")
    else:
        parts.append("⬜ 物资要求")
    if state.collected["has_personnel"]:
        parts.append("✅ 人员安排")
    else:
        parts.append("⬜ 人员安排")
    return "  |  ".join(parts)


def format_question_html(question: str, summary: str) -> str:
    """将问题格式化为好看的 HTML 气泡"""
    return f'''<div class="bg-darkCard border border-pink/10 rounded-2xl px-5 py-4">
    <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">📋</span>
        <span class="text-sm font-semibold text-gray-200">信息补全助手</span>
    </div>
    <p class="text-sm text-gray-300 leading-relaxed mb-3">{question}</p>
    <div class="flex items-center gap-2">
        <span class="text-xs text-gray-500">📊 已收集进度:</span>
        <span class="text-xs text-pink bg-pinkMuted px-2 py-0.5 rounded">{summary}</span>
    </div>
</div>'''


def format_complete_html(summary: str) -> str:
    """当信息完整时，提示即将生成策划书"""
    return f'''<div class="bg-pinkMuted border border-pink/20 rounded-2xl px-5 py-3">
    <p class="text-sm text-pink font-semibold">✅ 信息收集完成！正在为你生成活动策划方案…</p>
    <p class="text-xs text-gray-400 mt-1">已收集: {summary}</p>
</div>'''
