"""Sphinx configuration for the Reservation Management System documentation.

Lightweight setup: MyST turns the root-level USER_GUIDE.md, DEVELOPER_GUIDE.md,
TESTING.md, API_GUIDE.md and INSTALLATION.md into the documentation source
(via the `{include}` directive in the matching docs/*.md stub), so nothing here
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

# Included root files contain relative links to sibling .md files; those are
# plain repository links, so don't warn about them in the site build.
suppress_warnings = ["myst.xref_missing", "myst.header"]

# -- HTML output --------------------------------------------------------------

html_theme = "alabaster"
html_static_path = []
