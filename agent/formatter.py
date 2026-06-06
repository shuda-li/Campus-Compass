import json


def build_html(plan: dict, rooms: list = None, budget: dict = None) -> str:
    topic = plan.get("activity_topic", plan.get("title", "活动策划书"))
    purpose = plan.get("activity_purpose", "")
    activity_time = plan.get("activity_time", "XXX")
    organizer = plan.get("organizer", "XXX")
    host = plan.get("host", "XXX")
    content_list = plan.get("activity_content", [])
    materials = plan.get("activity_materials", [])

    parts = []
    parts.append('<div class="bg-darkCard border border-white/5 rounded-2xl overflow-hidden">')

    parts.append('<div class="flex items-center gap-3 px-5 py-4 bg-pinkMuted border-b border-white/5">')
    parts.append('<div class="w-10 h-10 bg-pink/20 rounded-xl flex items-center justify-center text-lg flex-shrink-0">📋</div>')
    parts.append('<div class="min-w-0">')
    parts.append(f'<h2 class="text-base font-semibold text-white truncate">{topic}</h2>')
    parts.append(f'<p class="text-xs text-gray-400 mt-0.5">校园活动策划方案</p>')
    parts.append('</div></div>')

    parts.append('<div class="px-5 py-4 space-y-5">')

    if purpose:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-2">')
        parts.append('<span class="text-sm font-semibold text-gray-200">🎯 活动目的</span>')
        parts.append('</div>')
        parts.append(f'<p class="text-sm text-gray-300 leading-relaxed bg-darkInput/40 rounded-xl px-4 py-3">{purpose}</p>')
        parts.append('</div>')

    parts.append('<div>')
    parts.append('<div class="grid grid-cols-3 gap-2">')
    parts.append('<div class="bg-darkInput/40 rounded-xl px-4 py-3 text-center">')
    parts.append('<div class="text-xs text-gray-500 mb-1">活动时间</div>')
    parts.append(f'<div class="text-sm text-gray-200 font-semibold">{activity_time}</div>')
    parts.append('</div>')
    parts.append('<div class="bg-darkInput/40 rounded-xl px-4 py-3 text-center">')
    parts.append('<div class="text-xs text-gray-500 mb-1">主办单位</div>')
    parts.append(f'<div class="text-sm text-gray-200 font-semibold">{organizer}</div>')
    parts.append('</div>')
    parts.append('<div class="bg-darkInput/40 rounded-xl px-4 py-3 text-center">')
    parts.append('<div class="text-xs text-gray-500 mb-1">承办单位</div>')
    parts.append(f'<div class="text-sm text-gray-200 font-semibold">{host}</div>')
    parts.append('</div>')
    parts.append('</div></div>')

    if content_list:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">📝 活动内容</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">{len(content_list)}个环节</span>')
        parts.append('</div>')
        parts.append('<div class="space-y-3">')
        for i, item in enumerate(content_list):
            phase = item.get("phase", f"环节{i+1}")
            duration = item.get("duration", "")
            content_text = item.get("content", "")
            host_guide = item.get("host_guide", "")
            interaction = item.get("interaction", "")

            parts.append('<div class="bg-darkInput/30 rounded-xl px-4 py-3 border border-white/5">')
            parts.append('<div class="flex items-center gap-2 mb-2">')
            parts.append(f'<div class="w-6 h-6 bg-pink/20 rounded-md flex items-center justify-center text-xs font-bold text-pink">{i+1}</div>')
            parts.append(f'<span class="text-sm font-semibold text-gray-200">{phase}</span>')
            if duration:
                parts.append(f'<span class="text-xs text-gray-500 bg-darkInput/60 px-2 py-0.5 rounded ml-auto">{duration}</span>')
            parts.append('</div>')
            if content_text:
                parts.append(f'<p class="text-xs text-gray-400 mb-2 leading-relaxed">{content_text}</p>')
            if host_guide:
                parts.append(f'<div class="text-xs text-pink/70 bg-pinkMuted px-3 py-1.5 rounded-lg mb-1">💬 引导语：{host_guide}</div>')
            if interaction:
                parts.append(f'<span class="text-[10px] text-gray-500">互动方式：{interaction}</span>')
            parts.append('</div>')
        parts.append('</div></div>')

    if materials:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">📦 活动物资</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">{len(materials)}项</span>')
        parts.append('</div>')
        parts.append('<div class="space-y-1.5">')
        for m in materials:
            name = m.get("name", "")
            spec = m.get("spec", "")
            qty = m.get("qty", "")
            parts.append(f'<div class="flex items-center justify-between px-4 py-2.5 rounded-lg bg-darkInput/40 text-sm">')
            parts.append(f'<span class="text-gray-300">{name}</span>')
            parts.append(f'<span class="text-xs text-gray-500">{spec} · {qty}</span>')
            parts.append('</div>')
        parts.append('</div></div>')

    if rooms:
        parts.append('<div>')
        parts.append('<div class="flex items-center gap-2 mb-3">')
        parts.append('<span class="text-sm font-semibold text-gray-200">🏫 推荐教室</span>')
        parts.append(f'<span class="text-[10px] font-semibold text-pink bg-pinkMuted px-2 py-0.5 rounded">{len(rooms)}间可选</span>')
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
            equip_str = " · ".join(equip_list[:3]) if equip_list else ""
            parts.append('<div class="flex items-center gap-3 px-4 py-3 rounded-xl bg-darkInput/40 hover:bg-darkInput/60 transition-colors">')
            parts.append(f'<div class="w-7 h-7 {rank_bg} rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0">{i+1}</div>')
            parts.append('<div class="flex-1 min-w-0">')
            parts.append(f'<div class="text-sm font-semibold text-gray-200">{room.get("room_id","?")} · {room.get("building","")} {room.get("floor","")}F</div>')
            parts.append(f'<div class="text-xs text-gray-500 mt-0.5">{equip_str}</div>')
            parts.append('</div>')
            parts.append(f'<span class="text-sm font-bold text-pink whitespace-nowrap">👥 {room.get("capacity","?")}人</span>')
            parts.append('</div>')
        parts.append('</div></div>')

    parts.append('</div></div>')
    return "\n".join(parts)
