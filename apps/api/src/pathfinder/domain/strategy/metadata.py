"""Small helpers related to strategy graph metadata."""

_MAX_NAME_LENGTH = 80
_TRUNCATED_NAME_LENGTH = 77


def derive_graph_metadata(raw_goal: str) -> tuple[str, str]:
    clean = " ".join((raw_goal or "").strip().split())
    description = clean
    name = description
    if len(name) > _MAX_NAME_LENGTH:
        name = name[:_TRUNCATED_NAME_LENGTH].rstrip() + "..."
    if not name:
        name = "Strategy Draft"
    return name, description
