import networkx as nx
from typing import List, Optional


def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    """
    Detects circular dependencies using an "Iterative Shortest Cycle Removal" strategy.

    Instead of enumerating all cycles (exponential) or just finding one (insufficient),
    this algorithm provides a heuristic "roadmap" for fixing the architecture:

    1. Decompose graph into Strongly Connected Components (SCCs).
    2. For each SCC, identify the *shortest* cycle.
    3. Report this cycle.
    4. Virtually "break" the cycle by removing one of its edges (simulating a fix).
    5. Repeat until the SCC is cycle-free.

    This ensures that:
    - We report the most critical (shortest) feedback loops first.
    - We provide a set of cycles that, if fixed, likely resolve the entire SCC.
    - Performance is kept efficient (Polynomial) compared to exhaustive enumeration.
    """
    cycles = []
    
    # 1. Find all SCCs initially
    sccs = list(nx.strongly_connected_components(graph))

    for scc in sccs:
        # Skip trivial SCCs (single node without self-loop)
        if len(scc) < 2:
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue
            # Handle self-loop explicitly
            cycles.append([node])
            continue

        # Create a working subgraph for this SCC to perform destructive analysis
        subgraph = graph.subgraph(scc).copy()

        # Safety break to prevent infinite loops in pathological cases
        max_iterations = 100

        while max_iterations > 0:
            cycle = _find_shortest_cycle_in_subgraph(subgraph)
            if not cycle:
                break

            cycles.append(cycle)

            # Virtual Fix: Remove the last edge of the cycle (u -> v)
            # cycle is a list of nodes [n1, n2, ... nk] representing n1->n2->...->nk->n1
            # We break the closing edge (nk, n1)
            u, v = cycle[-1], cycle[0]
            if subgraph.has_edge(u, v):
                subgraph.remove_edge(u, v)

            max_iterations -= 1

    return cycles


def _find_shortest_cycle_in_subgraph(graph: nx.DiGraph) -> List[str]:
    """
    Finds the shortest cycle in the graph by iterating over all edges (u, v)
    and finding the shortest path from v to u.
    Returns the list of nodes in the cycle: [n1, n2, ... nk].
    """
    best_cycle: Optional[List[str]] = None

    # We iterate over edges. If an edge (u, v) is part of a cycle,
    # there must be a path v -> ... -> u.
    # The cycle length would be len(path) + 1.
    for u, v in graph.edges():
        # Optimization: If we already found a cycle of length 2 (A <-> B),
        # it is impossible to find shorter. Stop immediately.
        if best_cycle and len(best_cycle) == 2:
            return best_cycle

        try:
            # BFS for shortest path from target(v) back to source(u)
            path = nx.shortest_path(graph, source=v, target=u)
            
            # If path is [v, x, u], and we have edge (u, v).
            # The full cycle sequence is v -> x -> u -> v.
            # The node list representation is [v, x, u].
            
            if best_cycle is None or len(path) < len(best_cycle):
                best_cycle = path

        except nx.NetworkXNoPath:
            continue

    return best_cycle if best_cycle else []