import html
import os
import pathlib
import shutil
import subprocess
import tempfile
import webbrowser

import sublime
import sublime_plugin

# GUI-launched Sublime on macOS doesn't inherit the shell PATH, so look in the usual spots too.
PANDOC_PATHS = ["/opt/homebrew/bin/pandoc", "/usr/local/bin/pandoc", "/usr/bin/pandoc"]

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
  --kw: #cf222e; --str: #0a3069; --com: #59636e; --num: #0550ae; --fn: #6639ba; --type: #953800;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fg: #f0f6fc; --muted: #9198a1; --bg: #0d1117; --border: #3d444d; --code-bg: #151b23;
    --link: #4493f8; --row-alt: #151b23;
    --kw: #ff7b72; --str: #a5d6ff; --com: #9198a1; --num: #79c0ff; --fn: #d2a8ff; --type: #ffa657;
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
ul.task-list { list-style: none; padding-left: 1em; }
blockquote { padding: 0 1em; color: var(--muted); border-left: .25em solid var(--border); }
hr { height: .25em; margin: 24px 0; padding: 0; border: 0; background: var(--border); }
img { max-width: 100%; }
code, pre { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; font-size: 85%; }
code { padding: .2em .4em; border-radius: 6px; background: var(--code-bg); }
pre { padding: 16px; overflow: auto; line-height: 1.45; border-radius: 6px; background: var(--code-bg); }
pre code { padding: 0; font-size: 100%; background: transparent; }
pre code span a { display: none; }
table { display: block; width: max-content; max-width: 100%; overflow: auto; border-collapse: collapse; }
th, td { padding: 6px 13px; border: 1px solid var(--border); }
th { font-weight: 600; }
tr:nth-child(2n) { background: var(--row-alt); }
.kw, .cf, .im, .op { color: var(--kw); }
.st, .ch, .ss, .vs, .sc { color: var(--str); }
.co, .do, .an, .cv, .in { color: var(--com); }
.dv, .bn, .fl, .cn, .bu { color: var(--num); }
.fu, .at, .ex { color: var(--fn); }
.dt, .va, .pp { color: var(--type); }
</style>
</head>
<body>
%(body)s
</body>
</html>
"""


def find_pandoc():
    return shutil.which("pandoc") or next((p for p in PANDOC_PATHS if os.path.exists(p)), None)


class MarkdownPreviewInBrowserCommand(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.match_selector(0, "text.html.markdown")

    def run(self, edit):
        pandoc = find_pandoc()
        if not pandoc:
            sublime.error_message("Markdown Preview: pandoc not found (brew install pandoc).")
            return

        file_name = self.view.file_name()
        # Read the buffer, not the file, so unsaved edits show up.
        source = self.view.substr(sublime.Region(0, self.view.size()))

        # No -s: pandoc's standalone page always forces its own styles, so wrap the fragment ourselves.
        result = subprocess.run(
            [pandoc, "-f", "gfm", "-t", "html5"],
            input=source.encode("utf-8"),
            capture_output=True,
        )
        if result.returncode != 0:
            sublime.error_message("Markdown Preview: pandoc failed\n\n" + result.stderr.decode("utf-8", "replace"))
            return

        base = ""
        if file_name:
            # Resolve relative images and links against the markdown file's folder.
            base_url = pathlib.Path(os.path.dirname(file_name)).as_uri() + "/"
            base = '<base href="%s">\n' % html.escape(base_url, quote=True)

        # str.replace, not %: the CSS is full of literal % signs. Body goes last so its text is never rescanned.
        title = html.escape(os.path.basename(file_name) if file_name else "Untitled")
        page = (
            PAGE.replace("%(base)s", base)
            .replace("%(title)s", title)
            .replace("%(body)s", result.stdout.decode("utf-8"))
        )

        # mkstemp creates the file readable only by the current user.
        fd, path = tempfile.mkstemp(prefix="markdown-preview-", suffix=".html")
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(page)
        webbrowser.open(pathlib.Path(path).as_uri())
