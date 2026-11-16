"""Markdown to HTML, GitHub-flavoured, with the vendored markdown-it-py."""
import html
import os
import sys

# The vendored libraries import each other by top-level name (markdown_it, mdurl), so their folder must be on sys.path.
VENDOR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor")
if VENDOR not in sys.path:
    sys.path.append(VENDOR)

from markdown_it import MarkdownIt  # noqa: E402
from mdit_py_plugins.anchors import anchors_plugin  # noqa: E402
from mdit_py_plugins.footnote import footnote_plugin  # noqa: E402
from mdit_py_plugins.tasklists import tasklists_plugin  # noqa: E402

try:
    # Installed by Package Control from dependencies.json. Without it, code blocks render uncoloured.
    import pygments
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
except ImportError:
    pygments = None


def highlight_code(code, lang, attrs):
    """Return coloured spans for markdown-it to wrap in <pre><code>, or "" to fall back to plain escaped text."""
    if not pygments or not lang:
        return ""
    try:
        lexer = get_lexer_by_name(lang)
    except ClassNotFound:
        return ""
    return pygments.highlight(code, lexer, HtmlFormatter(nowrap=True))


def render_fence(self, tokens, idx, options, env):
    """```mermaid blocks become <pre class="mermaid"> for Mermaid to draw; every other fence renders as code."""
    token = tokens[idx]
    if token.info.split()[:1] == ["mermaid"]:
        return '<pre class="mermaid">%s</pre>\n' % html.escape(token.content)
    return self.fence(tokens, idx, options, env)


# GitHub's "link" octicon, shown beside each heading on hover. aria-hidden: the link gets a readable label instead.
LINK_ICON = (
    '<svg class="octicon octicon-link" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="'
    "m7.775 3.275 1.25-1.25a3.5 3.5 0 1 1 4.95 4.95l-2.5 2.5a3.5 3.5 0 0 1-4.95 0 .751.751 0 0 1 .018-1.042.751.751"
    " 0 0 1 1.042-.018 1.998 1.998 0 0 0 2.83 0l2.5-2.5a2.002 2.002 0 0 0-2.83-2.83l-1.25 1.25a.751.751 0 0 1-1.042"
    "-.018.751.751 0 0 1-.018-1.042Zm-4.69 9.64a1.998 1.998 0 0 0 2.83 0l1.25-1.25a.751.751 0 0 1 1.042.018.751.751"
    " 0 0 1 .018 1.042l-1.25 1.25a3.5 3.5 0 1 1-4.95-4.95l2.5-2.5a3.5 3.5 0 0 1 4.95 0 .751.751 0 0 1-.018 1.042.751"
    '.751 0 0 1-1.042.018 1.998 1.998 0 0 0-2.83 0l-2.5 2.5a1.998 1.998 0 0 0 0 2.83Z"></path></svg>'
)

# CommonMark plus tables, strikethrough, task lists, footnotes, and heading ids with a link to each heading,
# shown in the margin on hover like GitHub's.
# Bare URLs are not autolinked: that needs linkify-it-py and uc-micro-py vendored and the "linkify" rule enabled.
MARKDOWN = (
    MarkdownIt("commonmark", {"highlight": highlight_code})
    .enable(["table", "strikethrough"])
    .use(tasklists_plugin)
    .use(footnote_plugin)
    .use(
        anchors_plugin,
        max_level=6, permalink=True, permalinkSymbol=LINK_ICON, permalinkBefore=True, permalinkSpace=False,
    )
)
MARKDOWN.add_render_rule("fence", render_fence)
