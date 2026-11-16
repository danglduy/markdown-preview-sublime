# Markdown Preview (Sublime Text)

Preview the current Markdown buffer in your browser with GitHub styling, rendered locally by [pandoc](https://pandoc.org).

- Renders the buffer, so unsaved edits show up
- GitHub-flavoured Markdown: tables, task lists, fenced code with highlighting
- GitHub look, following the system light/dark mode, no network requests
- Relative images and links resolve against the file's folder
- Output is a private temp file (readable only by you)

## Requirements

- Sublime Text 4
- pandoc: `brew install pandoc` or `apt install pandoc`

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
