# Markdown Preview (Sublime Text)

Preview the current Markdown buffer in your browser with GitHub styling, rendered locally by [markdown-it-py](https://github.com/executablebooks/markdown-it-py). Nothing to install besides the package.

- Renders the buffer, so unsaved edits show up
- GitHub-flavoured Markdown (CommonMark): tables, strikethrough, task lists, footnotes, heading anchors, 2-space nested lists
- Code highlighting with Pygments, installed automatically by Package Control
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

## Development

`vendor/` holds unmodified copies of markdown-it-py 3.0.0, mdurl 0.1.2 and mdit-py-plugins 0.4.2 (all MIT, licences alongside). These are the last releases that still support the Python 3.8 plugin host of older Sublime Text 4 builds.

Check rendering outside Sublime with `python3 tests/check_render.py`.
