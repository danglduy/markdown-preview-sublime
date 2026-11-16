"""Preview files: private, and removed once old, since they hold the document's text."""
import glob
import os
import stat
import tempfile
import time

PREVIEW_PREFIX = "markdown-preview-"
PREVIEW_MAX_AGE = 24 * 60 * 60


def write_preview(page):
    """Write the page to a new temp file and return its path. mkstemp creates the file readable only by the
    current user, with a random name nobody can pre-create."""
    fd, path = tempfile.mkstemp(prefix=PREVIEW_PREFIX, suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(page)
    return path


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
