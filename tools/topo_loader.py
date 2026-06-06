"""
拓扑地图加载器

从 data/map.json（Graphviz xdot 格式）读取 E 座拓扑图，
提供教室坐标查询、距离计算等功能。

拓扑图结构：
  - 节点: 教室 (101~133) + 路径点 (C1~C28) + 起点 (C2)
  - 边:  走廊/通道连接关系，构成无向图
"""

import json
import os
import math
from collections import deque

MAP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "map.json")

# ═══════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════

def _load_graph() -> dict:
    """加载 xdot 格式的拓扑图，返回 {node_name: (x, y, label)} 和 edges 列表。"""
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    nodes = {}   # name → (x, y, label)
    edges = []   # [(from_name, to_name), ...]

    for obj in raw.get("objects", []):
        name = obj["name"]
        pos_str = obj.get("pos", "")
        label = obj.get("label", name).replace("\\n", "\n")
        if "," in pos_str:
            x, y = pos_str.split(",")
            nodes[name] = (float(x), float(y), label)

    for edge in raw.get("edges", []):
        tail_idx = edge["tail"]
        head_idx = edge["head"]
        tail_name = raw["objects"][tail_idx]["name"]
        head_name = raw["objects"][head_idx]["name"]
        edges.append((tail_name, head_name))

    return nodes, edges


def _classroom_number(node_label: str, node_name: str = "") -> int | None:
    """从节点标签提取真实教室号。

    拓扑图命名规则：内部名 F1→101教室, F2→102教室, ...
    优先从标签（如 "101教室"）提取，回退到内部名。
    """
    import re
    # 优先从标签中提取（如 "101教室" → 101, "起点\\nC2" → skip）
    m = re.search(r"(\d+)教室", node_label)
    if m:
        return int(m.group(1))
    # 回退：内部名 F1 → 1（但这不是真实教室号，需查标签）
    if node_name.startswith("F") and node_name[1:].isdigit():
        return int(node_name[1:])
    return None


# ═══════════════════════════════════════════════
# 路径距离计算（BFS 最短路径）
# ═══════════════════════════════════════════════

def _build_adjacency(edges: list, weighted: bool = False) -> dict:
    """
    构建邻接表（无向图）。

    weighted=False: 邻接表存 [neighbor, ...]（跳数相等）
    weighted=True:  邻接表存 [(neighbor, weight), ...]（边有权重）
                    边权重由两端节点的欧几里得距离决定：
                    - 距离 < 150: weight=1（短走廊）
                    - 距离 >= 150: weight=2（长走廊/转角）
    """
    if not weighted:
        adj = {}
        for a, b in edges:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        return adj

    # 加权模式：需要节点坐标
    global _graph_cache
    nodes, _ = _graph_cache if _graph_cache else (None, None)
    if not nodes:
        return _build_adjacency(edges, weighted=False)

    pos = {n: (v[0], v[1]) for n, v in nodes.items()}
    adj = {}
    for a, b in edges:
        dist = _euclidean(pos.get(a, (0, 0)), pos.get(b, (0, 0)))
        w = 1 if dist < 150 else 2
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    return adj


def _euclidean(p1: tuple, p2: tuple) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def _shortest_path_length(start: str, end: str, nodes: dict, adj: dict) -> float:
    """BFS 沿边计算最短路径的几何长度（非跳数）。"""
    if start == end:
        return 0.0
    if start not in adj or end not in adj:
        # 节点不在图中 → 回退为直线距离
        return _euclidean(nodes[start], nodes[end])

    queue = deque([(start, 0.0)])
    visited = {start}

    while queue:
        current, dist = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor == end:
                return dist + _euclidean(nodes[current], nodes[end])
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, dist + _euclidean(nodes[current], nodes[neighbor])))

    # 不可达 → 回退为直线距离
    return _euclidean(nodes[start], nodes[end])


# ═══════════════════════════════════════════════
# 公开接口
# ═══════════════════════════════════════════════

_graph_cache = None


def get_distance_to_entrance(room_name: str) -> float | None:
    """
    计算指定教室到起点（C2）的路径距离。

    room_name 格式: "E101", "E302" 等（去掉 E 前缀取数字）,
                  或直接用教室号如 "101", "302"。
    """
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = _load_graph()

    nodes, edges = _graph_cache
    adj = _build_adjacency(edges)

    # 解析教室号
    room_num = None
    if room_name.startswith("E"):
        room_num = int(room_name[1:])
    else:
        try:
            room_num = int(room_name)
        except ValueError:
            pass

    if room_num is None:
        return None

    # 在节点中查找匹配的教室（用标签中的教室号匹配）
    target_node = None
    for name, (x, y, label) in nodes.items():
        cn = _classroom_number(label, name)
        if cn == room_num:
            target_node = name
            break

    if target_node is None:
        return None

    entrance_node = "C2"  # 拓扑图中标记为"起点"
    if entrance_node not in nodes:
        for name, (x, y, label) in nodes.items():
            if "起点" in label or name == "C2":
                entrance_node = name
                break

    # 转换为旧格式 (x, y) 给距离函数
    pos_only = {n: (v[0], v[1]) for n, v in nodes.items()}
    return _shortest_path_length(entrance_node, target_node, pos_only, adj)


def get_all_classroom_distances() -> dict:
    """获取所有教室到起点的路径距离。返回 {教室号: 距离}。"""
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = _load_graph()

    nodes, edges = _graph_cache
    adj = _build_adjacency(edges)

    entrance_node = "C2"
    for name, (x, y, label) in nodes.items():
        if "起点" in label or name == "C2":
            entrance_node = name
            break

    pos_only = {n: (v[0], v[1]) for n, v in nodes.items()}
    distances = {}
    for name, (x, y, label) in nodes.items():
        cn = _classroom_number(label, name)
        if cn is not None:
            dist = _shortest_path_length(entrance_node, name, pos_only, adj)
            distances[cn] = round(dist, 1)

    return distances


def _weighted_shortest_path(start: str, end: str, adj: dict) -> float:
    """
    Dijkstra 加权最短路径。
    边权: 短走廊=1, 长走廊=2。
    返回路径总权重（非几何距离）。
    """
    import heapq
    if start == end:
        return 0.0
    if start not in adj:
        return float('inf')

    dist = {start: 0.0}
    pq = [(0.0, start)]

    while pq:
        d, current = heapq.heappop(pq)
        if d > dist.get(current, float('inf')):
            continue
        if current == end:
            return d
        for neighbor_tuple in adj.get(current, []):
            if isinstance(neighbor_tuple, tuple):
                neighbor, weight = neighbor_tuple
            else:
                neighbor, weight = neighbor_tuple, 1
            nd = d + weight
            if nd < dist.get(neighbor, float('inf')):
                dist[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))

    return float('inf')


def get_weighted_distance(room_name: str) -> float | None:
    """
    计算教室到起点的加权路径距离。

    边权规则：
    - 短走廊（节点间距 < 150 单位）：权重 1
    - 长走廊（节点间距 >= 150 单位）：权重 2

    这反映了实际步行体感：长走廊需要更多时间/体力。
    """
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = _load_graph()

    nodes, edges = _graph_cache
    adj = _build_adjacency(edges, weighted=True)

    # 解析教室号
    room_num = None
    if room_name.startswith("E"):
        room_num = int(room_name[1:])
    else:
        try:
            room_num = int(room_name)
        except ValueError:
            pass
    if room_num is None:
        return None

    # 查找教室节点
    target_node = None
    for name, (x, y, label) in nodes.items():
        cn = _classroom_number(label, name)
        if cn == room_num:
            target_node = name
            break
    if target_node is None:
        return None

    # 起点
    entrance_node = "C2"
    for name, (x, y, label) in nodes.items():
        if "起点" in label or name == "C2":
            entrance_node = name
            break

    return _weighted_shortest_path(entrance_node, target_node, adj)


def get_all_weighted_distances() -> dict:
    """获取所有教室到起点的加权距离。"""
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = _load_graph()

    nodes, edges = _graph_cache
    adj = _build_adjacency(edges, weighted=True)

    entrance_node = "C2"
    for name, (x, y, label) in nodes.items():
        if "起点" in label or name == "C2":
            entrance_node = name
            break

    distances = {}
    for name, (x, y, label) in nodes.items():
        cn = _classroom_number(label, name)
        if cn is not None:
            d = _weighted_shortest_path(entrance_node, name, adj)
            if d != float('inf'):
                distances[cn] = round(d, 1)

    return distances


def distance_to_score(distance: float, min_dist: float = 50, max_dist: float = 2000) -> float:
    """
    将距离映射到 0~12 分（位置便利性评分）。

    - 距离 < 50: 满分 12（就在入口旁边）
    - 距离 > 2000: 最低 1 分
    - 中间线性映射
    """
    if distance <= min_dist:
        return 12.0
    if distance >= max_dist:
        return 1.0
    return round(12.0 - (distance - min_dist) / (max_dist - min_dist) * 11.0, 1)


# ═══════════════════════════════════════════════
# CLI 调试入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    distances = get_all_classroom_distances()
    print("教室到起点的路径距离：")
    print(f"{'教室':<8} {'距离':<10} {'便利分'}")
    print("-" * 30)
    for room_num in sorted(distances.keys()):
        d = distances[room_num]
        s = distance_to_score(d)
        print(f"{room_num:<8} {d:<10.1f} {s}")
