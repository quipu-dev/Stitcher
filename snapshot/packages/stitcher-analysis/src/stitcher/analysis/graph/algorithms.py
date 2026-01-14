from typing import List
import networkx as nx


def detect_circular_dependencies(graph: nx.DiGraph) -> List[List[str]]:
    """
    Detects circular dependencies by finding strongly connected components (SCCs)
    and then sampling one cycle from each non-trivial SCC. This is significantly
    more performant than enumerating all simple cycles.
    """
    cycles = []
    # 1. Find all strongly connected components (SCCs).
    # An SCC is a subgraph where every node is reachable from every other node.
    # Any cycle must exist entirely within an SCC.
    sccs = nx.strongly_connected_components(graph)

    for scc in sccs:
        # A non-trivial SCC (potential for a cycle) has more than one node,
        # or it's a single node that points to itself (a self-loop).
        is_trivial_scc = len(scc) < 2
        if is_trivial_scc:
            # The type hint for scc elements is `Node`, which is generic. In our
            # case, they are strings representing file paths.
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue  # Skip single-node SCCs without self-loops.

        # 2. For each non-trivial SCC, find just *one* representative cycle.
        # This avoids the combinatorial explosion of `nx.simple_cycles`.
        scc_subgraph = graph.subgraph(scc)
        try:
            # `find_cycle` is highly optimized to return as soon as it finds any cycle.
            # It returns a list of edges, e.g., [(u, v), (v, w), (w, u)].
            # We respect the original graph's directionality.
            cycle_edges = nx.find_cycle(scc_subgraph, orientation="original")

            # 3. Convert the edge list to a node list to maintain compatibility
            # with the reporting rule, which expects a list of nodes [u, v, w].
            cycle_nodes = [edge[0] for edge in cycle_edges]
            cycles.append(cycle_nodes)

        except nx.NetworkXNoCycle:
            # This should theoretically not happen for a non-trivial SCC,
            # but we include it for robustness.
            pass

    return cycles


def has_path(graph: nx.DiGraph, source: str, target: str) -> bool:
    return nx.has_path(graph, source, target)
