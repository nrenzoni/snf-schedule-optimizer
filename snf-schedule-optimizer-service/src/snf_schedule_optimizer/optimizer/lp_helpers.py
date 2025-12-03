def build_lp_variable_name(*args: str) -> str:
    """Utility to build safe LP variable names by joining parts."""
    safe_parts = ["X"] + [part.replace("-", "_").replace(" ", "_") for part in args]
    return "__".join(safe_parts)
