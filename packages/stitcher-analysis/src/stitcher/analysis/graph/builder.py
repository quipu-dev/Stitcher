from typing import Dict
import networkx as nx

from stitcher.spec import IndexStoreProtocol


class GraphBuilder:
    def build_dependency_graph(self, store: IndexStoreProtocol) -> nx.DiGraph:
        graph = nx.DiGraph()
        fqn_to_path_cache: Dict[str, str | None] = {}

        # 1. Add all source files as nodes
        all_files = store.get_all_files()
        for file_record in all_files:
            graph.add_node(file_record.path)

        # 2. Add edges based on import references
        all_edges = store.get_all_dependency_edges()
        for edge in all_edges:
            source_path = edge.source_path
            target_fqn = edge.target_fqn

            # Skip if we've already processed this FQN and found it unresolvable
            if (
                target_fqn in fqn_to_path_cache
                and fqn_to_path_cache[target_fqn] is None
            ):
                continue

            # Resolve FQN to a file path, following aliases to find the canonical definition
            if target_fqn not in fqn_to_path_cache:
                resolved_path = None
                current_fqn = target_fqn

                # Limit iterations to prevent infinite loops in case of malformed alias cycles
                for _ in range(10):
                    symbol_result = store.find_symbol_by_fqn(current_fqn)
                    if not symbol_result:
                        break  # Unresolvable (external or non-existent)

                    symbol, path = symbol_result
                    if symbol.kind != "alias" or not symbol.alias_target_fqn:
                        resolved_path = path
                        break  # Found the canonical definition

                    # It's an alias, continue resolving
                    current_fqn = symbol.alias_target_fqn

                fqn_to_path_cache[target_fqn] = resolved_path

            target_path = fqn_to_path_cache.get(target_fqn)

            # Add edge if the target is an internal, resolved file
            if target_path and source_path != target_path:
                if not graph.has_edge(source_path, target_path):
                    graph.add_edge(source_path, target_path, reasons=[])

                # Attach the reason for this specific dependency edge
                reason = f"{edge.target_fqn} (L{edge.lineno})"
                graph[source_path][target_path]["reasons"].append(reason)

        return graph
