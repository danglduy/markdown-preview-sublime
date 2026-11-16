"""Run with plain Python from the repo root: python3 tests/check_render.py (Sublime only loads top-level .py files)."""
import os
import sys
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
if markdown_preview.pygments:
    assert '<span class="nb">puts</span>' in page, "code should be coloured"
print("ok, pygments:", bool(markdown_preview.pygments), path)
