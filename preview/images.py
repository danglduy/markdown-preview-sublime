"""Local images, embedded as data: URIs since the page never points back at the document's folder."""
import base64
import html
import os
import re
import urllib.parse

# SVG is safe here: inside <img> its scripts never run.
IMAGE_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".svg": "image/svg+xml", ".bmp": "image/bmp", ".ico": "image/x-icon",
}
IMAGE_MAX_BYTES = 10 * 1024 * 1024
IMAGE_SRC = re.compile(r"""<img\b[^>]*?\ssrc\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)


def is_within(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:  # different drives on Windows
        return False


def embed_local_images(body, file_name, folders):
    """Map each relative <img src> in the rendered HTML to a data: URI of the file it names.

    Like VS Code's preview, only files inside the document's folder or a Sublime project folder that contains it
    are read, and only image types, so a hostile document can't pull in ~/.ssh/id_rsa with "../../".
    """
    doc_dir = os.path.realpath(os.path.dirname(file_name))
    roots = [doc_dir] + [root for root in map(os.path.realpath, folders) if is_within(doc_dir, root)]
    images = {}
    for match in IMAGE_SRC.finditer(body):
        src = html.unescape(next(group for group in match.groups() if group is not None))
        url = urllib.parse.urlsplit(src)
        if src in images or url.scheme or url.netloc or not url.path or src.startswith(("/", "\\")):
            continue
        path = os.path.realpath(os.path.join(doc_dir, urllib.parse.unquote(url.path)))
        mime = IMAGE_TYPES.get(os.path.splitext(path)[1].lower())
        if not mime or not any(is_within(path, root) for root in roots):
            continue
        try:
            if os.path.getsize(path) > IMAGE_MAX_BYTES:
                continue
            with open(path, "rb") as image:
                images[src] = "data:%s;base64,%s" % (mime, base64.b64encode(image.read()).decode("ascii"))
        except OSError:
            pass
    return images
