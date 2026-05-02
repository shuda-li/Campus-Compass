import json


def build_markdown(plan: dict, rooms: list, navigation: str, budget: dict) -> str:
    lines = []
    lines.append("=" * 40)
    lines.append("  CAMPUS COMPASS - 活动策划书")
    lines.append("=" * 40)
    lines.append("")

    lines.append(f"## 活动标题: {plan.get('title', '未命名活动')}")
    lines.append("")

    lines.append("### 活动时间线")
    for item in plan.get("timeline", []):
        lines.append(f"- **{item['time']}**  {item['content']}")
    lines.append("")

    lines.append("### 预算明细")
    for key, value in budget.items():
        lines.append(f"- {key}: {value}元")
    lines.append("")

    lines.append("### 推荐教室")
    for i, room in enumerate(rooms[:3], 1):
        lines.append(f"{i}. **{room.get('room_id')}** ({room.get('building')}) — 容量{room.get('capacity')}人")
    lines.append("")

    lines.append("### 导航指引")
    lines.append(navigation)
    lines.append("")

    lines.append("=" * 40)
    return "\n".join(lines)


def build_html(plan: dict, rooms: list, navigation: str, budget: dict) -> str:
    title = plan.get("title", "活动策划书")
    timeline = plan.get("timeline", [])
    promotion = plan.get("promotion", "")
    resources = plan.get("resources", [])

    parts = []
    # 策划书卡片
    parts.append('<div class="bg-darkCard border border-white/5 rounded-2xl overflow-hidden">')

    # 头部
    parts.append('<div class="flex items-center gap-3 px-5 py-4 bg-pinkMuted border-b border-white/5">')
    parts.append('<div class="w-10 h-10 bg-pink/20 rounded-xl flex items-center justify-center text-lg flex-shrink-0">📋</div>')
    parts.append('<div class="min-w-0">')
    parts.append(f'<h2 class="text-base font-semibold text-white truncate">{title}</h2>')
    parts.append(f'<p class="text-xs text-gray-400 mt-0.5 truncate">{promotion[:60] if promotion else "校园活动策划方案"}</p>')
    parts.append('</div>')
    parts.append('</div>')

    # 内容区
    parts.append('<div class="px-5 py-4 space-y-5">')

    # 时间线
    if timeline:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">⏱ 活动时间线</span>')
        parts.append('<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">流程</span>')
        parts.append('</div>')
        parts.append('<div class="relative pl-5 border-l-2 border-pink/30 space-y-2">')
        for item in timeline:
            parts.append('<div class="relative pl-4">')
            parts.append('<div class="absolute left-[-29px] top-1.5 w-2 h-2 rounded-full bg-darkCard border-2 border-pink"></div>')
            parts.append(f'<span class="text-xs font-semibold text-pink bg-pinkMuted px-1.5 py-0.5 rounded mr-2">{item["time"]}</span>')
            parts.append(f'<span class="text-sm text-gray-300">{item["content"]}</span>')
            parts.append('</div>')
        parts.append('</div>')
        parts.append('</div>')

    # 预算
    if budget:
        budget_items = {k: v for k, v in budget.items() if k != "合计"}
        total = budget.get("合计", sum(budget_items.values()))
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">💰 预算明细</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">合计 ¥{total}</span>')
        parts.append('</div>')
        parts.append('<div class="grid grid-cols-2 gap-2">')
        for key, value in budget_items.items():
            parts.append(f'<div class="flex justify-between items-center px-3 py-2 rounded-lg bg-darkInput/50 text-sm"><span class="text-gray-400">{key}</span><span class="text-gray-200">¥{value}</span></div>')
        parts.append(f'<div class="flex justify-between items-center px-3 py-2 rounded-lg bg-pinkMuted font-semibold text-sm"><span class="text-pink">合计</span><span class="text-pink">¥{total}</span></div>')
        parts.append('</div>')
        parts.append('</div>')

    # 推荐教室
    if rooms:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">🏫 推荐教室</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">共{len(rooms)}间可用</span>')
        parts.append('</div>')
        parts.append('<div class="space-y-2">')
        for i, room in enumerate(rooms[:3]):
            rank_bg = "bg-pink" if i == 0 else ("bg-gray-500" if i == 1 else "bg-gray-600")
            equip_list = room.get("equipment", [])
            if isinstance(equip_list, str):
                try:
                    equip_list = json.loads(equip_list)
                except Exception:
                    equip_list = [equip_list]
            equip_str = " · ".join(equip_list[:3]) if equip_list else "无设备信息"
            parts.append('<div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-darkInput/40 hover:bg-darkInput/60 transition-colors">')
            parts.append(f'<div class="w-7 h-7 {rank_bg} rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0">{i + 1}</div>')
            parts.append('<div class="flex-1 min-w-0">')
            parts.append(f'<div class="text-sm font-semibold text-gray-200">{room.get("room_id", "?")} <span class="font-normal text-gray-500">· {room.get("building", "")} {room.get("floor", "")}F</span></div>')
            parts.append(f'<div class="text-xs text-gray-500 mt-0.5">{equip_str}</div>')
            parts.append('</div>')
            parts.append(f'<span class="text-sm font-bold text-pink whitespace-nowrap">👥 {room.get("capacity", "?")}人</span>')
            parts.append('</div>')
        parts.append('</div>')
        parts.append('</div>')

    # 导航
    if navigation:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">🧭 导航指引</span>')
        parts.append('<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">路线</span>')
        parts.append('</div>')
        parts.append(f'<div class="bg-pinkMuted border border-pink/10 rounded-xl px-4 py-3 text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{navigation}</div>')
        parts.append('</div>')

    # 资源
    if resources:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">📦 所需资源</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">{len(resources)}项</span>')
        parts.append('</div>')
        parts.append('<div class="grid grid-cols-2 gap-2">')
        for r in resources:
            parts.append(f'<div class="px-3 py-2 rounded-lg bg-darkInput/50 text-sm text-gray-300">{r}</div>')
        parts.append('</div>')
        parts.append('</div>')

    parts.append('</div>')  # 内容区结束
    parts.append('</div>')  # 卡片结束
    return "\n".join(parts)
