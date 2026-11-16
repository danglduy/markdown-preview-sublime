import base64
import functools
import glob
import html
import json
import os
import pathlib
import re
import secrets
import stat
import sys
import tempfile
import time
import urllib.parse
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

@functools.lru_cache(maxsize=None)
def inline_script(*parts):
    """A vendored script's source, for putting straight into the page so it never references the plugin's folder."""
    with open(os.path.join(VENDOR, *parts), encoding="utf-8") as script:
        source = script.read()
    # Inside an inline <script>, "</script" would end it early and "<script" can stop the real end tag counting.
    if "<script" in source.lower() or "</script" in source.lower():
        raise RuntimeError("%s can't be inlined safely: it contains a <script or </script sequence" % "/".join(parts))
    return source


# Raw HTML in the document stays allowed (READMEs use <details>, <img width>, <p align>), so the rendered HTML is
# never written into the page as markup. It goes in as an inert JSON string, and this script cleans it with
# DOMPurify, using the browser's own parser, before anything is shown. If the script can't run, the page stays empty.
#
# Beyond DOMPurify's defaults, like GitHub: no <style> or style= (no overlays or CSS beacons), no form controls
# except task-list checkboxes, and every id/name gets a "user-content-" prefix so the document can't replace
# page properties our scripts rely on (DOM clobbering). In-page links are pointed at the prefixed ids to match.
# Local images are swapped for the data: URIs Python embedded, since the page has no <base> to find them by.
SANITIZE_SCRIPT = """<script nonce="%(nonce)s">
(() => {
  const content = document.getElementById("content");
  const source = JSON.parse(document.getElementById("source").textContent);
  const images = new Map(Object.entries(JSON.parse(document.getElementById("images").textContent)));
  const clean = DOMPurify.sanitize(source, {
    RETURN_DOM_FRAGMENT: true,
    SANITIZE_NAMED_PROPS: true,
    FORBID_TAGS: ["style", "form", "button", "textarea", "select"],
    FORBID_ATTR: ["style"],
  });
  for (const link of clean.querySelectorAll("a[href]")) {
    const href = link.getAttribute("href");
    if (href.startsWith("#")) {
      const target = href.slice(1);
      if (target && !target.startsWith("user-content-")) link.setAttribute("href", "#user-content-" + target);
    } else {
      // Leaving the preview opens a new tab, which gets no handle on this page and no referrer.
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  }
  for (const image of clean.querySelectorAll("img[src]")) {
    const embedded = images.get(image.getAttribute("src"));
    if (embedded) image.setAttribute("src", embedded);
  }
  content.append(clean);
})();
</script>
"""

# Loaded only when the document has a diagram; the theme follows the system light/dark mode like the page.
# "strict" makes Mermaid escape HTML in labels and ignore click handlers written in the diagram.
MERMAID_SCRIPT = """<script nonce="%(nonce)s">
mermaid.initialize({
  startOnLoad: true,
  securityLevel: "strict",
  theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default",
});
</script>
"""


def scripts_for(body, nonce):
    """Our scripts, with the vendored libraries inlined. Sanitize first: Mermaid must only ever see the cleaned page."""
    opening = '<script nonce="%s">' % nonce
    scripts = [opening + inline_script("dompurify", "purify.min.js") + "</script>\n", SANITIZE_SCRIPT]
    if '<pre class="mermaid">' in body:
        scripts += [opening + inline_script("mermaid", "mermaid.min.js") + "</script>\n", MERMAID_SCRIPT]
    return "".join(script.replace('<script nonce="%(nonce)s">', opening) for script in scripts)


def inert_json(value):
    """JSON for a <script type="application/json"> block. Escaping < > & means the text can never close the
    block or start markup, so the browser only ever sees it as a string."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


# Local images the page may embed. SVG is safe here: inside <img> its scripts never run.
IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".svg": "image/svg+xml", ".bmp": "image/bmp", ".ico": "image/x-icon",
}
IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_SRC = re.compile(r"""<img\b[^>]*?\ssrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)


def is_within(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def embed_local_images(body, file_name, folders):
    """Map each relative <img src> in the rendered HTML to a data: URI of the file it names.

    Like VS Code's preview, only files inside the document's folder or a Sublime project folder that contains it
    are read, and only image types, so a hostile document can't pull in ~/.ssh/id_rsa with "../../".
    """
    doc_dir = os.path.realpath(os.path.dirname(file_name))
    roots = [doc_dir] + [root for root in map(os.path.realpath, folders) if is_within(doc_dir, root)]
    images = {}
    for match in IMAGE_SRC.finditer(body):
        src = html.unescape(next(group for group in match.groups() if group is not None))
        url = urllib.parse.urlsplit(src)
        if src in images or url.scheme or url.netloc or not url.path or src.startswith(("/", "\\")):
            continue
        path = os.path.realpath(os.path.join(doc_dir, urllib.parse.unquote(url.path)))
        mime = IMAGE_TYPES.get(os.path.splitext(path)[1].lower())
        if not mime or not any(is_within(path, root) for root in roots):
            continue
        try:
            if os.path.getsize(path) > IMAGE_MAX_BYTES:
                continue
            with open(path, "rb") as image:
                images[src] = "data:%s;base64,%s" % (mime, base64.b64encode(image.read()).decode("ascii"))
        except OSError:
            pass
    return images


# Previews hold the document's text, so don't leave them in the temp folder for good.
PREVIEW_PREFIX = "markdown-preview-"
PREVIEW_MAX_AGE = 24 * 60 * 60


def remove_old_previews():
    cutoff = time.time() - PREVIEW_MAX_AGE
    for path in glob.glob(os.path.join(tempfile.gettempdir(), PREVIEW_PREFIX + "*.html")):
        try:
            info = os.lstat(path)
            # Only plain files we created: never follow a symlink or touch another user's file in a shared /tmp.
            if not stat.S_ISREG(info.st_mode) or (hasattr(os, "getuid") and info.st_uid != os.getuid()):
                continue
            if info.st_mtime < cutoff:
                os.remove(path)
        except OSError:
            pass


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
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'nonce-%(nonce)s'; style-src 'unsafe-inline'; img-src data: https:; media-src https:; font-src data:; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
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
<main id="content"></main>
<noscript>This preview needs JavaScript: it cleans the document's HTML in the browser before showing it.</noscript>
<script type="application/json" id="source">%(body)s</script>
<script type="application/json" id="images">%(images)s</script>
%(scripts)s</body>
</html>
"""


PLACEHOLDER = re.compile(r"%\((nonce|title|body|images|scripts)\)s")


class MarkdownPreviewInBrowserCommand(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.match_selector(0, "text.html.markdown")

    def run(self, edit):
        file_name = self.view.file_name()
        # Read the buffer, not the file, so unsaved edits show up.
        source = self.view.substr(sublime.Region(0, self.view.size()))

        # The page never points back at the original file: no <base>, no folder path, no file:// URLs.
        # Only the file's name is kept, as the tab title.
        # Local images are embedded instead, which needs the project folders to know what may be read.
        body = MARKDOWN.render(source)
        window = self.view.window()
        folders = window.folders() if window else []
        images = embed_local_images(body, file_name, folders) if file_name else {}
        # A fresh nonce per preview: only our own script tags carry it, so scripts in the document can't run.
        nonce = secrets.token_urlsafe(16)
        values = {
            "nonce": nonce,
            "title": html.escape(os.path.basename(file_name) if file_name else "Untitled"),
            "body": inert_json(body),
            "images": inert_json(images),
            "scripts": scripts_for(body, nonce),
        }
        # One pass, so nothing filled in is scanned again: the document's text can't smuggle in a placeholder.
        # (The CSS's literal % signs never match the placeholder pattern.)
        page = PLACEHOLDER.sub(lambda match: values[match.group(1)], PAGE)

        remove_old_previews()
        # mkstemp creates the file readable only by the current user, with a random name nobody can pre-create.
        fd, path = tempfile.mkstemp(prefix=PREVIEW_PREFIX, suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(page)
        webbrowser.open(pathlib.Path(path).as_uri())
