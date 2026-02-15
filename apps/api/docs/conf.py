"""Sphinx configuration for Pathfinder API documentation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "Pathfinder API"
copyright = "2025"
author = "VEuPathDB"
release = "1.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "show-inheritance": True,
}
python_use_unqualified_type_names = True

# Include type hints in parameter descriptions for clarity.
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented_params"

templates_path = ["_templates"]
exclude_patterns = []

html_theme = "alabaster"
html_static_path = []

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "kani": ("https://kani.readthedocs.io/en/latest/", None),
}
