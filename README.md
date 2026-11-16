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
- Raw HTML that could run code, redirect, submit forms or restyle the page (`<script>`, `on…=` handlers, `<meta>` refresh, `<iframe>`, `<form>`, `<style>`…) is shown as text, much as GitHub strips it. Safe HTML such as `<details>` or `<img width>` still renders.
- Mermaid runs at its strict security level, so diagram labels can't inject HTML or click handlers.
- Previews are written readable only by you and are deleted after a day.
- `scripts/update-vendor.sh` checks every download against a pinned sha256 before unpacking it.

Remote images still load, as on GitHub, so a document can tell its author's server that you opened it.

## Development

`vendor/` holds unmodified copies of markdown-it-py 3.0.0, mdurl 0.1.2 and mdit-py-plugins 0.4.2, plus Mermaid 12.2.0's browser build (all MIT, licences alongside). The Python libraries are the last releases that still support the Python 3.8 plugin host of older Sublime Text 4 builds.

To update them, change the pinned versions in `scripts/update-vendor.sh` and run it. It rebuilds `vendor/` from PyPI.

Check rendering outside Sublime with `python3 tests/check_render.py`.
