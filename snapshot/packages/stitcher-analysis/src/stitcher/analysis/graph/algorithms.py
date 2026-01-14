from typing import List, Set, Tuple
import networkx as nx


def find_shortest_cycle(graph: nx.DiGraph) -> List[str]:
    """
    Finds one of the shortest cycles in a given directed graph component.
    This implementation iterates through each node and performs a BFS to find
    the shortest cycle starting and ending at that node.
    """
    shortest_cycle = None
    nodes = list(graph.nodes)

    for start_node in nodes:
        # BFS implementation to find the shortest path back to start_node
        # queue stores tuples of (node, path_list)
        queue: List[Tuple[str, List[str]]] = [(start_node, [start_node])]
        visited = {start_node}

        head = 0
        while head < len(queue):
            current_node, path = queue[head]
            head += 1

            # If we've already found a cycle and the current path is longer,
            # we can prune this search branch.
            if shortest_cycle is not None and len(path) >= len(shortest_cycle):
                continue

            for neighbor in graph.successors(current_node):
                if neighbor == start_node:
                    # Found a cycle. Since we are using BFS, this is the shortest
                    # cycle starting and ending at `start_node`.
                    found_cycle = path
                    if shortest_cycle is None or len(found_cycle) < len(shortest_cycle):
                        shortest_cycle = found_cycle
                    # Break from the inner loop to not explore further from this node
                    # as we already found the shortest cycle from it.
                    break
                
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
            else:
                # This `else` belongs to the `for` loop. It continues if `break` was not hit.
                continue
            # This `break` belongs to the `while` loop.
            break
            
    return shortest_cycle if shortest_cycle else []


def detect_circular_dependencies(graph: nx.DiGraph) -> List[Tuple[Set[str], List[str]]]:
    """
    Detects circular dependencies by finding strongly connected components (SCCs)
    and then finding the shortest cycle within each non-trivial SCC.
    
    Returns:
        A list of tuples, where each tuple contains:
        - A set of strings representing all nodes in the coupled component (SCC).
        - A list of strings representing the nodes in the shortest found cycle.
    """
    problematic_components = []
    sccs = nx.strongly_connected_components(graph)

    for scc in sccs:
        is_trivial_scc = len(scc) < 2
        if is_trivial_scc:
            node = list(scc)[0]
            if not graph.has_edge(node, node):
                continue

        scc_subgraph = graph.subgraph(scc)
        shortest_cycle_nodes = find_shortest_cycle(scc_subgraph)

        if shortest_cycle_nodes:
            problematic_components.append((scc, shortest_cycle_nodes))

    return problematic_components