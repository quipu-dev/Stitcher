def path_to_logical_fqn(rel_path_str: str) -> str:
    # Normalize path separators to dots
    fqn = rel_path_str.replace("/", ".")

    # Strip .py extension
    if fqn.endswith(".py"):
        fqn = fqn[:-3]

    # Handle __init__ files (e.g., 'pkg.__init__' -> 'pkg')
    if fqn.endswith(".__init__"):
        fqn = fqn[: -len(".__init__")]

    return fqn
