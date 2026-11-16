import html
import os
import pathlib
import sys
import tempfile
import webbrowser

import sublime
import sublime_plugin

# The vendored libraries import each other by top-level name (markdown_it, mdurl), so their folder must be on sys.path.
VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
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


# GitHub-flavoured: CommonMark plus tables, strikethrough, task lists, footnotes and heading anchors.
# ponytail: no bare-URL autolinking, vendor linkify-it-py + uc-micro-py and enable "linkify" if it's missed.
MARKDOWN = (
    MarkdownIt("commonmark", {"highlight": highlight_code})
    .enable(["table", "strikethrough"])
    .use(tasklists_plugin)
    .use(footnote_plugin)
    .use(anchors_plugin, max_level=6)
)

MERMAID_JS = pathlib.Path(VENDOR, "mermaid", "mermaid.min.js").as_uri()
# Loaded only when the document has a diagram; the theme follows the system light/dark mode like the page.
MERMAID_SCRIPT = """<script src="%s"></script>
<script>
mermaid.initialize({ startOnLoad: true, theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default" });
</script>
""" % html.escape(MERMAID_JS, quote=True)

default_fence = MARKDOWN.renderer.rules["fence"]


def render_fence(self, tokens, idx, options, env):
    """```mermaid blocks become <pre class="mermaid"> for Mermaid to draw; every other fence renders as code."""
    token = tokens[idx]
    if token.info.split()[:1] == ["mermaid"]:
        return '<pre class="mermaid">%s</pre>\n' % html.escape(token.content)
    return default_fence(tokens, idx, options, env)


MARKDOWN.add_render_rule("fence", render_fence)

# ponytail: hand-trimmed GitHub look, swap in the full github-markdown-css if something looks off.
PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
%(base)s<title>%(title)s</title>
<style>
:root {
  --fg: #1f2328; --muted: #59636e; --bg: #ffffff; --border: #d1d9e0; --code-bg: #f6f8fa;
  --link: #0969da; --row-alt: #f6f8fa;
  --kw: #cf222e; --str: #0a3069; --com: #59636e; --num: #0550ae; --fn: #6639ba; --type: #953800; --tag: #116329;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #f0f6fc; --muted: #9198a1; --bg: #0d1117; --border: #3d444d; --code-bg: #151b23;
    --link: #4493f8; --row-alt: #151b23;
    --kw: #ff7b72; --str: #a5d6ff; --com: #9198a1; --num: #79c0ff; --fn: #d2a8ff; --type: #ffa657; --tag: #7ee787;
  }
}
html { background: var(--bg); }
body {
  box-sizing: border-box; max-width: 980px; margin: 0 auto; padding: 45px;
  color: var(--fg); background: var(--bg);
  font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
  word-wrap: break-word;
}
@media (max-width: 767px) { body { padding: 15px; } }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
h1, h2, h3, h4, h5, h6 { margin: 24px 0 16px; font-weight: 600; line-height: 1.25; }
h1 { font-size: 2em; padding-bottom: .3em; border-bottom: 1px solid var(--border); }
h2 { font-size: 1.5em; padding-bottom: .3em; border-bottom: 1px solid var(--border); }
h3 { font-size: 1.25em; }
h4 { font-size: 1em; }
h5 { font-size: .875em; }
h6 { font-size: .85em; color: var(--muted); }
p, blockquote, ul, ol, dl, table, pre, details { margin: 0 0 16px; }
ul, ol { padding-left: 2em; }
li + li { margin-top: .25em; }
.task-list-item { list-style: none; }
.task-list-item-checkbox { margin: 0 .2em .25em -1.4em; vertical-align: middle; }
blockquote { padding: 0 1em; color: var(--muted); border-left: .25em solid var(--border); }
hr { height: .25em; margin: 24px 0; padding: 0; border: 0; background: var(--border); }
img { max-width: 100%; }
code, pre { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; font-size: 85%; }
code { padding: .2em .4em; border-radius: 6px; background: var(--code-bg); }
pre { padding: 16px; overflow: auto; line-height: 1.45; border-radius: 6px; background: var(--code-bg); }
pre code { padding: 0; font-size: 100%; background: transparent; }
table { display: block; width: max-content; max-width: 100%; overflow: auto; border-collapse: collapse; }
th, td { padding: 6px 13px; border: 1px solid var(--border); }
th { font-weight: 600; }
tr:nth-child(2n) { background: var(--row-alt); }
.footnotes-sep { display: none; }
.footnotes { margin-top: 32px; padding-top: 16px; font-size: 12px; color: var(--muted); border-top: 1px solid var(--border); }
pre .k, pre .kc, pre .kd, pre .kn, pre .kp, pre .kr, pre .ow, pre .o { color: var(--kw); }
pre .s, pre .s1, pre .s2, pre .sa, pre .sb, pre .sc, pre .sd, pre .se, pre .sh, pre .si, pre .sr, pre .ss, pre .sx { color: var(--str); }
pre .c, pre .c1, pre .ch, pre .cm, pre .cp, pre .cpf, pre .cs { color: var(--com); }
pre .m, pre .mb, pre .mf, pre .mh, pre .mi, pre .mo, pre .il, pre .nb, pre .bp, pre .no, pre .na { color: var(--num); }
pre .nf, pre .fm, pre .nc, pre .nd, pre .nn { color: var(--fn); }
pre .kt, pre .nv, pre .vc, pre .vg, pre .vi { color: var(--type); }
pre .nt { color: var(--tag); }
pre.mermaid { font-size: 100%; text-align: center; background: transparent; }
</style>
</head>
<body>
%(body)s
%(scripts)s</body>
</html>
"""


class MarkdownPreviewInBrowserCommand(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.match_selector(0, "text.html.markdown")

    def run(self, edit):
        file_name = self.view.file_name()
        # Read the buffer, not the file, so unsaved edits show up.
        source = self.view.substr(sublime.Region(0, self.view.size()))

        base = ""
        if file_name:
            # Resolve relative images and links against the markdown file's folder.
            base_url = pathlib.Path(os.path.dirname(file_name)).as_uri() + "/"
            base = '<base href="%s">\n' % html.escape(base_url, quote=True)

        # str.replace, not %: the CSS is full of literal % signs. Body goes last so its text is never rescanned.
        title = html.escape(os.path.basename(file_name) if file_name else "Untitled")
        body = MARKDOWN.render(source)
        scripts = MERMAID_SCRIPT if '<pre class="mermaid">' in body else ""
        page = (
            PAGE.replace("%(base)s", base)
            .replace("%(title)s", title)
            .replace("%(scripts)s", scripts)
            .replace("%(body)s", body)
        )

        # mkstemp creates the file readable only by the current user.
        fd, path = tempfile.mkstemp(prefix="markdown-preview-", suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(page)
        webbrowser.open(pathlib.Path(path).as_uri())
