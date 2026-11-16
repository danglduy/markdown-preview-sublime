"""The Sublime Text command. Sublime only loads top-level .py files as plugins; the work happens in preview/."""
import pathlib
import sys
import webbrowser

import sublime
import sublime_plugin

# Sublime reloads only this file when it changes or the package upgrades. Drop the preview modules it already
# loaded, so they load fresh too instead of an old copy running against new code.
for name in [name for name in sys.modules if name.startswith(__package__ + ".preview")]:
    del sys.modules[name]

from .preview.files import remove_old_previews, write_preview  # noqa: E402
from .preview.page import build_page  # noqa: E402


class MarkdownPreviewInBrowserCommand(sublime_plugin.TextCommand):
    def is_visible(self):
        return self.view.match_selector(0, "text.html.markdown")

    def run(self, edit):
        window = self.view.window()
        # Read the buffer, not the file, so unsaved edits show up.
        source = self.view.substr(sublime.Region(0, self.view.size()))
        page = build_page(source, self.view.file_name(), window.folders() if window else [])
        remove_old_previews()
        webbrowser.open(pathlib.Path(write_preview(page)).as_uri())
