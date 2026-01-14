import networkx as nx
from typing import List, Optional, Dict, Any, Set


def detect_circular_dependencies(graph: nx.DiGraph) -> List[Dict[str, Any]]:
    """
    Detects circular dependencies using an "Iterative Shortest Cycle Removal" strategy.

    Returns a list of dictionaries, where each dictionary represents a
    Strongly Connected Component (SCC) and contains:
    - 'scc': A set of file paths in the component.
    - 'cycles': A list of prioritized cycles (node lists) within that component.
    """
    scc_results = []

    sccs = list(nx.strongly_connected_components(graph))

    for scc in sccs:
        cycles_in_scc: List[List[str]] = []
        
        # Handle self-loop explicitly as a cycle of one
        if len(scc) == 1:
            node = list(scc)[0]
            if graph.has_edge(node, node):
                cycles_in_scc.append([node])
        
        # For larger components, find cycles iteratively
        elif len(scc) > 1:
            subgraph = graph.subgraph(scc).copy()
            max_iterations = 100

            while max_iterations > 0:
                cycle = _find_shortest_cycle_in_subgraph(subgraph)
                if not cycle:
                    break
                
                cycles_in_scc.append(cycle)
                
                # Virtual Fix: Remove the closing edge of the cycle
                u, v = cycle[-1], cycle[0]
                if subgraph.has_edge(u, v):
                    subgraph.remove_edge(u, v)

                max_iterations -= 1

        if cycles_in_scc:
            scc_results.append({"scc": scc, "cycles": cycles_in_scc})

    return scc_results


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