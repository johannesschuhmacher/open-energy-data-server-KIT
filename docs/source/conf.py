# Configuration file for the Sphinx documentation builder.

# -- Project information

project = "Open Energy Data Server (KIT)"
copyright = "2026, IIP-KIT"
author = "IIP-KIT"

release = "0.1"
version = "0.1.0"

# -- General configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
]


intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
myst_enable_extensions = [
    "colon_fence",
    "deflist",
]

# -- Options for HTML output

html_theme = "pydata_sphinx_theme"
html_title = "Open Energy Data Server (KIT)"
html_theme_options = {
    "navigation_depth": 2,
    "show_nav_level": 1,
    "show_toc_level": 2,
}

# -- Options for EPUB output
epub_show_urls = "footnote"
