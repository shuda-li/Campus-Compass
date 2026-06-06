"""
最优教室推荐引擎（双层评分）

第一层：填充率（50% 权重）
  - 活动人数占教室容量的 70%~80% → 满分 50
  - 太低（<70%）：浪费空间，线性扣分
  - 太高（>80%）：过于拥挤，线性扣分
  - >100%：装不下，0 分

第二层：加权距离（50% 权重）
  - 以拓扑图起点（图书馆前 C2）为原点
  - 沿走廊网络加权计算最短路径（短边=1，长边=2）
  - 距离最近 → 满分 50，线性递减

流程：
  1. 粗筛：capacity >= participants（装得下）
  2. 填充率评分 → 0~50 分
  3. 加权距离评分 → 0~50 分
  4. 总分 = 填充分 + 距离分（满分 100）
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.topo_loader import get_weighted_distance, get_all_weighted_distances


def _fill_rate_score(participants: int, capacity: int) -> float:
    """
    填充率评分（0~50）。

    峰值在 70%~80% 填充率：教室不太空也不太挤，刚好合适。
    """
    if capacity <= 0 or participants <= 0:
        return 0.0

    fill = participants / capacity  # 0.0 ~ 1.0+

    if fill > 1.0:
        # 装不下 → 0 分
        return 0.0
    elif 0.70 <= fill <= 0.80:
        # 最佳区间 → 50 分
        return 50.0
    elif fill < 0.70:
        # 太宽松 → 线性 0→50（fill 从 0→0.7）
        return round(50.0 * (fill / 0.70), 1)
    else:
        # 太挤（0.80 < fill <= 1.0）→ 线性 50→0
        return round(50.0 * (1.0 - (fill - 0.80) / 0.20), 1)


def _distance_score(weighted_distance: float, all_distances: dict) -> float:
    """
    距离评分（0~50）。

    以所有教室中最短/最长加权距离为参照，线性映射。
    最近教室 → 50 分，最远教室 → 0 分。
    不在拓扑中的场馆 → 25 分（中等，不偏袒也不惩罚）。
    """
    if weighted_distance == float('inf'):
        return 25.0  # 不在拓扑图中（如体育场馆）

    if not all_distances:
        return 25.0  # 无数据 → 中等分

    dists = list(all_distances.values())
    min_d = min(dists)
    max_d = max(dists)

    if max_d == min_d:
        return 50.0  # 只有一个教室

    # 线性映射：min_d → 50, max_d → 0
    score = 50.0 - 50.0 * (weighted_distance - min_d) / (max_d - min_d)
    return round(max(0.0, min(50.0, score)), 1)


def select_best_rooms(rooms: list, participants: int) -> list:
    """
    双层评分选出最优教室。

    参数:
        rooms: 教室列表（来自 query_rooms）
        participants: 活动参与人数

    返回:
        排序后的教室列表，每个教室附加 _score, _fill_score, _distance_score, _weighted_dist
    """
    if not rooms:
        return []

    # 第一层：粗筛（装得下）
    candidates = [r for r in rooms if r.get("capacity", 0) >= participants]
    if not candidates:
        # 所有教室都装不下 → 全部返回但标记 0 分
        candidates = rooms

    # 预计算所有教室的加权距离（用于归一化）
    all_dists = get_all_weighted_distances()

    # 第二层：逐个评分
    scored = []
    for r in candidates:
        cap = r.get("capacity", 0)
        room_id = r.get("room_id", "")

        fill_s = _fill_rate_score(participants, cap)
        wdist = get_weighted_distance(room_id)
        if wdist is None:
            wdist = float('inf')
        dist_s = _distance_score(wdist, all_dists) if wdist != float('inf') else 0.0
        total = round(fill_s + dist_s, 1)

        scored.append((total, fill_s, dist_s, wdist, r))

    # 按总分降序排列
    scored.sort(key=lambda x: x[0], reverse=True)

    # 附加评分字段到教室 dict
    result = []
    for total, fill_s, dist_s, wdist, room in scored:
        room["_score"] = total
        room["_fill_score"] = fill_s
        room["_distance_score"] = dist_s
        room["_weighted_dist"] = wdist
        result.append(room)

    return result


# ═══════════════════════════════════════════════
# CLI 调试入口
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    from data.init_db import init_database
    init_database()

    from tools.db_service import query_rooms
    rooms = query_rooms(capacity_min=1)

    for test_name, p in [("30人小活动", 30), ("80人中活动", 80), ("150人大讲座", 150)]:
        print(f"\n{'='*60}")
        print(f"  {test_name}（{p}人）")
        print(f"{'='*60}")
        result = select_best_rooms(rooms, p)
        print(f"{'#':<3} {'教室':<7} {'容量':<6} {'填充率':<8} {'填充分':<8} {'加权距离':<10} {'距离分':<8} {'总分':<7}")
        print("-" * 70)
        for i, r in enumerate(result[:8]):
            fill_pct = f"{p/r['capacity']*100:.0f}%"
            print(f"{i+1:<3} {r['room_id']:<7} {r['capacity']}人    {fill_pct:<8} {r['_fill_score']:<8} {r['_weighted_dist']:<10} {r['_distance_score']:<8} {r['_score']:<7}")
