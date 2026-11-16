"""Run with plain Python from the repo root: python3 tests/check_render.py (Sublime only loads top-level .py files).

The Python part checks rendering, the page structure and image embedding. Sanitizing happens in the browser, so the
second part opens previews in headless Chrome/Chromium and checks the DOM it actually shows; it's skipped if none
is found.
"""
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types
import webbrowser

sys.modules["sublime"] = types.SimpleNamespace(Region=lambda a, b: (a, b))
sys.modules["sublime_plugin"] = types.SimpleNamespace(TextCommand=object)
# Load the repo as a package, the way Sublime does, so the plugin's relative imports resolve.
package = types.ModuleType("markdown_preview_sublime")
package.__path__ = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")]
sys.modules[package.__name__] = package
from markdown_preview_sublime import markdown_preview  # noqa: E402
from markdown_preview_sublime.preview import files, render as renderer  # noqa: E402

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# A throwaway project: <outside>/secret.png sits outside it, and docs/escape.png is a symlink pointing at it.
OUTSIDE = tempfile.mkdtemp()
PROJECT = os.path.join(OUTSIDE, "my project")
DOCS = os.path.join(PROJECT, "docs")
os.makedirs(os.path.join(DOCS, "img"))
os.makedirs(os.path.join(PROJECT, "assets"))
for path, data in [
    (os.path.join(DOCS, "img", "pic.png"), PNG),
    (os.path.join(PROJECT, "assets", "logo.svg"), b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
    (os.path.join(OUTSIDE, "secret.png"), PNG),
    (os.path.join(DOCS, "notes.txt"), b"not an image"),
]:
    with open(path, "wb") as out:
        out.write(data)
os.symlink(os.path.join(OUTSIDE, "secret.png"), os.path.join(DOCS, "escape.png"))
DOC = os.path.join(DOCS, "readme.md")

SOURCE = """# Title

[jump to title](#title) [site](https://example.com) [again](https://example.com) <https://example.net> <a href="https://example.org" target="_self" rel="opener">raw</a>

- outer
  - nested with two spaces

| a | b |
|---|---|
| 1 | 2 |

- [x] done
~~gone~~ and a note[^1]

![pic](img/pic.png) <img src="../assets/logo.svg" width="40">
![secret](../../secret.png) ![text](notes.txt) ![link](escape.png)

```ruby
puts "hi"
```

```mermaid
graph LR
  A[Start] --> B{Done?}
```

[^1]: The note.
"""

HOSTILE = """<script>alert(1)</script>

hi <img/onerror="alert(2)" src=x> <img src="x"onerror="alert(3)"> [a](javascript:alert(4))
<a href="javascript&#58;alert(5)">encoded</a> <a href="data:text/html;base64,PHNjcmlwdD4=">data</a>
<a href="file:///etc/passwd">local</a> <img name="getElementById" src="a.png">

<div style="position:fixed;inset:0">overlay</div>

<meta http-equiv="refresh" content="0;url=https://example.com">

<details><summary>Kept</summary>safe html</details>

</script><script>alert(6)</script> %(scripts)s %(nonce)s

<textarea>
swallow the rest
"""


class FakeView:
    def __init__(self, source, folders):
        self.source = source
        self.folders = folders

    def file_name(self):
        return DOC

    def substr(self, region):
        return self.source

    def size(self):
        return len(self.source)

    def window(self):
        return types.SimpleNamespace(folders=lambda: self.folders)


def render(source, folders=(PROJECT,)):
    """Return the preview's path, the page as written, and the rendered HTML and images held in its JSON blocks."""
    opened = []
    webbrowser.open = opened.append
    command = markdown_preview.MarkdownPreviewInBrowserCommand()
    command.view = FakeView(source, list(folders))
    command.run(None)
    path = opened[0][len("file://"):]
    page = open(path, encoding="utf-8").read()

    def block(name):
        data = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % name, page, re.S).group(1)
        return json.loads(data)

    return path, page, block("source"), block("images")


# Rendering.
path, page, body, images = render(SOURCE)
assert "<title>readme.md</title>" in page
assert '<h1 id="title"><a class="header-anchor" href="#title"><svg class="octicon octicon-link"' in body
assert body.count("<ul") >= 2, "two-space nested list should nest"
assert "<table>" in body and "<s>gone</s>" in body
assert 'class="task-list-item-checkbox"' in body and 'class="footnotes"' in body
assert '<pre class="mermaid">graph LR\n  A[Start] --&gt; B{Done?}\n</pre>' in body
if renderer.pygments:
    assert '<span class="nb">puts</span>' in body, "code should be coloured"

# Nothing points back at the original file or the plugin's folder.
for leak in [PROJECT, OUTSIDE, renderer.VENDOR, "<base", "file://"]:
    assert leak not in page, leak

# Local images are embedded only from inside the document's folder or its project folder, and only images.
assert images["img/pic.png"] == "data:image/png;base64," + base64.b64encode(PNG).decode()
assert images["../assets/logo.svg"].startswith("data:image/svg+xml;base64,"), "project folder images embed"
for refused in ["../../secret.png", "notes.txt", "escape.png"]:
    assert refused not in images, refused
assert "../assets/logo.svg" not in render(SOURCE, folders=())[3], "without a project, only the document's folder"

# Page structure: the document is only ever an inert string, and only our scripts carry the nonce.
assert oct(os.stat(path).st_mode & 0o777) == "0o600"
assert "<h1" not in page, "rendered HTML must not appear in the page as markup"
csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', page).group(1)
assert '<meta name="referrer" content="no-referrer">' in page
assert "script-src 'nonce-" in csp and " http:" not in csp and "file:" not in csp and "base-uri 'none'" in csp
assert page.count('<script nonce="') == 4, "DOMPurify, its init, Mermaid and its init"
plain_page = render("# No diagrams")[1]
assert "mermaid.initialize" not in plain_page and plain_page.count('<script nonce="') == 2, "Mermaid only if needed"

hostile_path, hostile_page, hostile_body, _ = render(HOSTILE)
assert "<img" not in hostile_page and "alert(6)</script>" not in hostile_page, "can't break out of the JSON block"
assert hostile_page.count('<script nonce="') == 2, "a placeholder in the document is never filled in"
assert "%(scripts)s %(nonce)s" in hostile_body

# Previews older than a day are removed; newer ones stay.
old = tempfile.mkstemp(prefix=files.PREVIEW_PREFIX, suffix=".html")[1]
os.utime(old, (time.time() - 2 * files.PREVIEW_MAX_AGE,) * 2)
render("# again")
assert not os.path.exists(old) and os.path.exists(path)


# Sanitizing, as the browser shows it.
def find_browser():
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.exists(mac):
        return mac
    return next(filter(None, map(shutil.which, ["google-chrome", "chromium", "chromium-browser"])), None)


def dump_dom(browser, preview_path):
    """The page's DOM after its scripts ran."""
    return subprocess.run(
        [browser, "--headless", "--disable-gpu", "--virtual-time-budget=8000", "--dump-dom", "file://" + preview_path],
        capture_output=True, text=True, timeout=60,
    ).stdout


def shown(browser, preview_path):
    """The <main> content after the page's scripts ran."""
    main = re.search(r'<main id="content">(.*?)</main>', dump_dom(browser, preview_path), re.S)
    assert main, "preview content missing: the page was redirected or replaced (e.g. by an unsanitized <meta> refresh)"
    return main.group(1)


browser = find_browser()
if browser:
    hostile = shown(browser, hostile_path)
    # Look at real tags and attributes only: escaped text such as "&lt;img/onerror=…&gt;" is harmless.
    for tag in re.findall(r"<[a-zA-Z][^>]*>", hostile):
        assert not re.search(r"\son\w+=|\sstyle=|\sname=\"getElementById\"", tag), tag
        assert not re.search(r"\s(href|src)=\"\s*(javascript|data:text|file:)", tag, re.I), tag
        assert not re.match(r"<(script|meta|textarea|style|form)\b", tag, re.I), tag
    assert "<details><summary>Kept</summary>safe html</details>" in hostile, "safe HTML should still render"
    assert "swallow the rest" in hostile, "a forbidden tag's text stays as plain text"

    normal = shown(browser, path)
    anchor = '<a class="header-anchor" href="#user-content-title" aria-label="Link to Title"><svg class="octicon'
    assert '<h1 id="user-content-title">' + anchor in normal and '<path d="m7.775' in normal, "GitHub's link icon"
    assert '<a href="#user-content-title">jump to title</a>' in normal, "in-page links stay in the same tab"
    # Both links, including the raw one asking for target="_self" rel="opener": new tab, no opener, no referrer.
    for site in ["https://example.com", "https://example.org"]:
        link = re.search(r'<a href="%s"[^>]*>' % re.escape(site), normal).group(0)
        assert 'target="_blank"' in link and 'rel="noopener noreferrer"' in link, link
    for name in ["site", "raw"]:
        assert re.search(r'>%s<svg class="octicon external-icon"[^>]*aria-hidden="true"><path d="M4\.53' % name, normal), name
    assert normal.count("external-icon") == 4, "only outbound links get the new-tab arrow"
    # For printing: notes after links (numbered on from the one document footnote, repeats share a number), none for
    # a link that already shows its address, and the addresses listed at the end.
    refs = re.findall(r'<a href="([^"]*)"[^>]*>(?:(?!</a>).)*</a><sup class="print-only print-ref">\[(\d)\]</sup>', normal)
    assert refs == [("https://example.com", "2"), ("https://example.com", "2"), ("https://example.org", "3")], refs
    assert '<ol start="2"><li>https://example.com</li><li>https://example.org</li></ol>' in normal
    assert 'href="#user-content-fn1"' in normal and 'id="user-content-fn1"' in normal, "footnotes still link"
    assert 'type="checkbox"' in normal, "task-list checkboxes survive"
    assert 'src="data:image/png;base64,' in normal and 'src="data:image/svg+xml;base64,' in normal, "images embed"
    assert "<svg" in normal, "Mermaid draws after sanitizing"
    # Click a heading link inside the page and record what the browser does. The probe carries the page's nonce,
    # like our own scripts, so the CSP lets it run.
    page = open(path, encoding="utf-8").read()
    nonce = re.search(r"'nonce-([^']+)'", page).group(1)
    probe = """<script nonce="%s">
    window.addEventListener("load", () => {
      const anchor = document.querySelector(".header-anchor");
      const resting = getComputedStyle(anchor);
      const restingDelay = resting.transitionDelay, restingOpacity = resting.opacity;
      anchor.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      setTimeout(() => {
        const style = getComputedStyle(anchor);
        document.body.dataset.probe = JSON.stringify({
          focused: document.activeElement === anchor, hash: location.hash, opacity: style.opacity,
          outline: style.outlineStyle, restingOpacity, restingDelay,
          scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
          scrollMargin: getComputedStyle(anchor.parentElement).scrollMarginTop,
        });
      }, 1500);
    });
    </script></body>""" % nonce
    probed = path.replace(".html", "-probe.html")
    with open(probed, "w", encoding="utf-8") as out:
        out.write(page[:page.rindex("</body>")] + probe + page[page.rindex("</body>") + len("</body>"):])
    dom = dump_dom(browser, probed)
    os.remove(probed)
    result = json.loads(re.search(r"data-probe=\"([^\"]*)\"", dom).group(1).replace("&quot;", '"'))
    assert result["restingOpacity"] == "0" and result["restingDelay"] == "0.15s", result
    assert result["focused"] and result["hash"] == "#user-content-title", "clicked link keeps focus: %s" % result
    assert result["opacity"] == "1" and result["outline"] == "auto", "focused link shows with a native ring"
    assert result["scrollBehavior"] == "smooth" and result["scrollMargin"] == "24px", result
    print("ok, pygments:", bool(renderer.pygments), "| browser checks: passed")
else:
    print("ok, pygments:", bool(renderer.pygments), "| browser checks: skipped (no Chrome/Chromium)")

shutil.rmtree(OUTSIDE)
