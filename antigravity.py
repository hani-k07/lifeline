n
import math
import random
from typing import List, Dict, Any

def run_force_layout(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], iterations: int = 50, width: float = 500.0, height: float = 500.0) -> List[Dict[str, Any]]:
    """Runs a 2D force-directed layout simulation for N iterations."""
    pos = {}
    
    # Initialize position dictionary
    for node in nodes:
        node_id = node.get("id", node.get("name"))
        # Start nodes at random positions around center if not already set
        pos[node_id] = [
            node.get("x", random.uniform(-150, 150)),
            node.get("y", random.uniform(-150, 150))
        ]

    # Ideal edge length/spacing constant
    k = math.sqrt((width * height) / max(1, len(nodes)))
    # Initial temperature for annealing
    t = width / 10.0

    for _ in range(iterations):
        # Repulsive forces (all pairs repel)
        disp = {node_id: [0.0, 0.0] for node_id in pos}
        node_ids = list(pos.keys())
        for i in range(len(node_ids)):
            u = node_ids[i]
            for j in range(i + 1, len(node_ids)):
                v = node_ids[j]
                dx = pos[u][0] - pos[v][0]
                dy = pos[u][1] - pos[v][1]
                dist = math.hypot(dx, dy)
                if dist == 0:
                    dist = 0.1
                # Repulsion force
                fr = (k * k) / dist
                disp[u][0] += (dx / dist) * fr
                disp[u][1] += (dy / dist) * fr
                disp[v][0] -= (dx / dist) * fr
                disp[v][1] -= (dy / dist) * fr

        # Attractive forces (connected edges attract)
        for edge in edges:
            u = edge.get("from", edge.get("source"))
            v = edge.get("to", edge.get("target"))
            if u not in pos or v not in pos:
                continue
            dx = pos[u][0] - pos[v][0]
            dy = pos[u][1] - pos[v][1]
            dist = math.hypot(dx, dy)
            if dist == 0:
                dist = 0.1
            # Attraction force
            fa = (dist * dist) / k
            disp[u][0] -= (dx / dist) * fa
            disp[u][1] -= (dy / dist) * fa
            disp[v][0] += (dx / dist) * fa
            disp[v][1] += (dy / dist) * fa

        # Limit displacement by temperature and update positions
        for u in pos:
            dx, dy = disp[u]
            dist = math.hypot(dx, dy)
            if dist > 0:
                lim = min(dist, t)
                pos[u][0] += (dx / dist) * lim
                pos[u][1] += (dy / dist) * lim

        # Anneal temperature
        t *= 0.95

    # Update nodes with final positions
    updated_nodes = []
    for node in nodes:
        node_id = node.get("id", node.get("name"))
        new_node = dict(node)
        new_node["x"] = round(pos[node_id][0], 2)
        new_node["y"] = round(pos[node_id][1], 2)
        updated_nodes.append(new_node)

    return updated_nodes
