"""
Campus Compass — 教室多维评分算法
===================================

评分原则（按用户要求）：
  1. 容量填充率 —— 最核心（~55% 权重）。人数尽量坐满教室，不过挤不过空
  2. 位置便利性 —— 次重要（~20% 权重）。低楼层优先，便于出入和搬运
  3. 设备匹配度 —— 降权（~10% 权重）。E座教室设备普遍齐全，区分度低
  4. 建筑偏好   —— 微调（~15% 权重）。用户指定建筑时加分

总分区间约 0~55 分。
"""

import json


def rank_rooms(rooms: list, intent: dict, plan: dict = None) -> list:
    """
    对教室列表多维加权打分排序，返回得分从高到低的教室列表。
    """
    preferred_building = intent.get("building", "")
    needed_equipment = set(intent.get("equipment", []))
    participants = max(1, int(intent.get("participants", 50)))

    # ═══════════════════════════════════════════
    # 维度一：容量适配度（0~30 分）—— 核心维度
    # ═══════════════════════════════════════════
    def _capacity_score(ratio: float) -> float:
        """
        容量余量 ratio = (capacity - participants) / participants

        峰值在 10%~30% 余量（留一点空间但不浪费），
        太挤（<5%）或太空（>80%）快速降分。

        30 ┤               ╱‾‾‾╲
           │              ╱      ╲
        20 ┤             ╱        ╲___
           │            ╱             ╲___
        10 ┤           ╱                  ╲___
           │          ╱                       ╲
         0 ┤─────────╱                          ╲___
           └────────────────────────────────────────
              0%  10%   30%       80%      150%   ratio
        """
        if ratio < 0:
            # 容量不够 → 0 分（不应被推荐）
            return 0
        elif ratio <= 0.10:
            # 非常紧凑（0~10%）：线性 0 → 25
            return (ratio / 0.10) * 25.0
        elif ratio <= 0.30:
            # 最佳区间（10%~30%）：峰值 30 分
            # 在 20% 余量处达到满分（略松但不空旷）
            dist_from_peak = abs(ratio - 0.20)
            return 30.0 - (dist_from_peak / 0.10) * 5.0
        elif ratio <= 0.80:
            # 偏空（30%~80%）：线性 25 → 10
            return 25.0 - ((ratio - 0.30) / 0.50) * 15.0
        elif ratio <= 1.50:
            # 太空（80%~150%）：线性 10 → 3
            return 10.0 - ((ratio - 0.80) / 0.70) * 7.0
        else:
            # 严重浪费（>150%）：最多 3 分
            return max(1.0, 3.0 - ((ratio - 1.50) / 1.0) * 2.0)

    # ═══════════════════════════════════════════
    # 维度二：位置便利性（0~12 分）—— 次重要
    # ═══════════════════════════════════════════
    def _location_score(floor: int) -> float:
        """
        低楼层 = 便于出入、搬运设备、紧急疏散。
        细分更多档位以体现真实差异。
        """
        if floor <= 1:
            return 12.0   # 一楼，最方便
        elif floor == 2:
            return 9.0    # 二楼，走一层楼梯
        elif floor == 3:
            return 5.0    # 三楼，需要等电梯
        elif floor == 4:
            return 2.0    # 四楼及以上，不便利
        else:
            return 1.0

    # ═══════════════════════════════════════════
    # 维度三：设备匹配度（0~5 分）—— 降权
    # ═══════════════════════════════════════════
    def _equipment_score(room_equipment: list, needed: set) -> float:
        """
        E 座教室设备普遍齐全（投影仪、音响、空调），
        所以设备维度区分度低，降低权重。
        每匹配一项 +1.5 分，上限 5 分。
        """
        if not needed:
            return 3.0  # 无特殊设备需求 → 给基础分
        equip_text = " ".join(room_equipment).lower()
        match_count = 0
        for need in needed:
            if need.lower() in equip_text:
                match_count += 1
        return min(5.0, match_count * 1.5)

    # ═══════════════════════════════════════════
    # 维度四：建筑偏好（0~8 分）—— 微调
    # ═══════════════════════════════════════════
    def _building_score(building_name: str, preferred: str) -> float:
        if preferred and preferred in building_name:
            return 8.0
        return 0.0

    # ═══════════════════════════════════════════
    # 综合评分
    # ═══════════════════════════════════════════
    def score(room):
        capacity = room.get("capacity", 0)
        floor = room.get("floor", 1)
        building_name = room.get("building", "")

        # 解析设备列表
        equip_raw = room.get("equipment", "[]")
        if isinstance(equip_raw, str):
            try:
                equip_list = json.loads(equip_raw)
            except (json.JSONDecodeError, TypeError):
                equip_list = []
        else:
            equip_list = equip_raw if isinstance(equip_raw, list) else []

        total = 0.0

        # 容量不足 → 直接 0 分（不推荐装不下的教室）
        if capacity < participants:
            return 0.0

        ratio = (capacity - participants) / participants
        total += _capacity_score(ratio)
        total += _location_score(floor)
        total += _equipment_score(equip_list, needed_equipment)
        total += _building_score(building_name, preferred_building)

        return round(total, 1)

    scored = [(score(r), r) for r in rooms]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]
