"""Sphinx configuration for the Reservation Management System documentation.

Lightweight setup: MyST turns the existing root-level USER_GUIDE.md and
API_GUIDE.md into the actual documentation source (via the `{include}`
directive in docs/user_guide.md and docs/api_guide.md), so nothing here
duplicates their content -- this file only wires up the site around them.
"""

project = "Reservation Management System"
copyright = "2026, Reservation Management System"
author = "Reservation Management System"
release = "1.0"
version = "1.0"

# -- General configuration --------------------------------------------------

extensions = [
    "myst_parser",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

root_doc = "index"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- MyST (Markdown) options --------------------------------------------------

myst_enable_extensions = [
    "colon_fence",
]
myst_heading_anchors = 3

# -- HTML output --------------------------------------------------------------

html_theme = "alabaster"
html_static_path = []
