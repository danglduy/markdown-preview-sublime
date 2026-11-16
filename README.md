# Markdown Preview (Sublime Text)

Preview the current Markdown buffer in your browser with GitHub styling, rendered locally by [markdown-it-py](https://github.com/executablebooks/markdown-it-py). Nothing to install besides the package.

- Renders the buffer, so unsaved edits show up
- GitHub-flavoured Markdown (CommonMark): tables, strikethrough, task lists, footnotes, heading anchors, 2-space nested lists
- Code highlighting with Pygments, installed automatically by Package Control
- Mermaid diagrams from ```mermaid blocks, drawn by a bundled copy of Mermaid (loaded only when a document has one)
- GitHub look, following the system light/dark mode, no network requests
- Relative images and links resolve against the file's folder
- Output is a private temp file (readable only by you)

## Requirements

Sublime Text 4. When installing by hand, run **Package Control: Satisfy Libraries** afterwards to get Pygments for code highlighting; without it code blocks render uncoloured.

## Install

Package Control:

1. Command Palette → **Package Control: Add Repository** → `https://github.com/danglduy/markdown-preview-sublime`
2. Command Palette → **Package Control: Install Package** → `markdown-preview-sublime`

Manual: clone into the Packages folder (Command Palette → **Preferences: Browse Packages**).

```sh
git clone https://github.com/danglduy/markdown-preview-sublime "$HOME/Library/Application Support/Sublime Text/Packages/markdown-preview-sublime"
```

## Usage

Open a Markdown file, then Command Palette → **Markdown Preview: Open in Browser**.

## Security

Previewing a Markdown file you didn't write (a README from a cloned repo, say) is safe:

- Scripts in the document never run. The page carries a Content Security Policy that only trusts the plugin's own scripts, using a fresh random nonce per preview.
- The rendered HTML is cleaned in the browser by a bundled [DOMPurify](https://github.com/cure53/DOMPurify) before it's shown. It uses the browser's own HTML parser, so what it checks is exactly what you see. Like GitHub, it also drops `<style>`, `style=` and form controls, and prefixes ids with `user-content-` so a document can't hijack the page's own functions. Safe HTML such as `<details>` or `<img width>` still renders.
- Until DOMPurify has cleaned it, the HTML is only an inert JSON string in the page, so if JavaScript is off or a script fails, the preview stays empty instead of showing raw HTML.
- Mermaid runs at its strict security level, so diagram labels can't inject HTML or click handlers.
- Previews are written readable only by you and are deleted after a day.
- `scripts/update-vendor.sh` checks every download against a pinned sha256 before unpacking it.

Remote images load over `https` only, as in VS Code's strict preview. They still let a document's author see that you opened it; GitHub avoids that by fetching images through its own proxy.

## Development

`vendor/` holds unmodified copies of markdown-it-py 3.0.0, mdurl 0.1.2 and mdit-py-plugins 0.4.2, plus the browser builds of Mermaid 12.2.0 (MIT) and DOMPurify 3.4.17 (MPL-2.0 or Apache-2.0), licences alongside. The Python libraries are the last releases that still support the Python 3.8 plugin host of older Sublime Text 4 builds.

To update them, change the pinned versions in `scripts/update-vendor.sh` and run it. It rebuilds `vendor/` from PyPI.

Check rendering outside Sublime with `python3 tests/check_render.py`. With Chrome or Chromium installed, it also opens hostile documents headlessly and checks what the browser actually shows.
