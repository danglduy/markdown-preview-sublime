"""Run with plain Python from the repo root: python3 tests/check_render.py (Sublime only loads top-level .py files)."""
import os
import sys
import tempfile
import time
import types
import webbrowser

sys.modules["sublime"] = types.SimpleNamespace(Region=lambda a, b: (a, b))
sys.modules["sublime_plugin"] = types.SimpleNamespace(TextCommand=object)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import markdown_preview  # noqa: E402

SOURCE = """# Title

- outer
  - nested with two spaces

| a | b |
|---|---|
| 1 | 2 |

- [x] done
~~gone~~ and a note[^1]

![pic](img/pic.png)

```ruby
puts "hi"
```

```mermaid
graph LR
  A[Start] --> B{Done?}
```

[^1]: The note.
"""


class FakeView:
    def __init__(self, source):
        self.source = source

    def file_name(self):
        return "/tmp/my notes/readme.md"

    def substr(self, region):
        return self.source

    def size(self):
        return len(self.source)


def render(source):
    opened = []
    webbrowser.open = opened.append
    command = markdown_preview.MarkdownPreviewInBrowserCommand()
    command.view = FakeView(source)
    command.run(None)
    path = opened[0][len("file://"):]
    return path, open(path, encoding="utf-8").read()


path, page = render(SOURCE)
assert '<base href="file:///tmp/my%20notes/">' in page
assert "<title>readme.md</title>" in page
assert '<h1 id="title">' in page
assert page.count("<ul") >= 2, "two-space nested list should nest"
assert "<table>" in page and "<s>gone</s>" in page
assert 'class="task-list-item-checkbox"' in page and 'class="footnotes"' in page
assert 'src="img/pic.png"' in page
assert oct(os.stat(path).st_mode & 0o777) == "0o600"
assert '<pre class="mermaid">graph LR\n  A[Start] --&gt; B{Done?}\n</pre>' in page
assert "mermaid.min.js" in page and os.path.exists(markdown_preview.VENDOR + "/mermaid/mermaid.min.js")
assert "mermaid.min.js" not in render("# No diagrams")[1], "Mermaid should load only when needed"
# Security: scripts in the document must not run, and the page must only trust its own nonce.
HOSTILE = """<script>alert(1)</script>

hi <img/onerror="alert(2)" src=x> <img src="x"onerror="alert(3)"> [a](javascript:alert(4))

<meta http-equiv="refresh" content="0;url=https://example.com">

<details><summary>Kept</summary>safe html</details>
"""
hostile = render(HOSTILE)[1]
for unsafe in ["<script>alert", "<img/onerror", '"onerror=', '<meta http-equiv="refresh', 'href="javascript:']:
    assert unsafe not in hostile, unsafe
assert "<details><summary>Kept</summary>" in hostile, "safe HTML should still render"
assert "Content-Security-Policy" in hostile and "script-src 'nonce-" in hostile
assert page.count('<script nonce="') == 2, "only Mermaid and its init script should carry the nonce"

# Previews older than a day are removed; newer ones stay.
old = tempfile.mkstemp(prefix=markdown_preview.PREVIEW_PREFIX, suffix=".html")[1]
os.utime(old, (time.time() - 2 * markdown_preview.PREVIEW_MAX_AGE,) * 2)
render("# again")
assert not os.path.exists(old) and os.path.exists(path)

if markdown_preview.pygments:
    assert '<span class="nb">puts</span>' in page, "code should be coloured"
print("ok, pygments:", bool(markdown_preview.pygments), path)
