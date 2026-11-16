"""The preview page: a template filled with the rendered HTML as inert data, and our scripts inlined."""
import functools
import html
import json
import os
import re
import secrets

from .images import embed_local_images
from .render import MARKDOWN, VENDOR

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "template.html"), encoding="utf-8") as template:
    PAGE = template.read()
PLACEHOLDER = re.compile(r"%\((nonce|title|body|images|scripts)\)s")

# DOMPurify and the script that sanitizes with it always run first: Mermaid must only ever see the cleaned page.
SCRIPTS = [os.path.join(VENDOR, "dompurify", "purify.min.js"), os.path.join(HERE, "sanitize.js")]
MERMAID_SCRIPTS = [os.path.join(VENDOR, "mermaid", "mermaid.min.js"), os.path.join(HERE, "mermaid-init.js")]


@functools.lru_cache(maxsize=None)
def script_source(path):
    """A script's source, for putting straight into the page so it never references the plugin's folder."""
    with open(path, encoding="utf-8") as script:
        source = script.read()
    # Inside an inline <script>, "</script" would end it early and "<script" can stop the real end tag counting.
    if re.search(r"</?script", source, re.IGNORECASE):
        raise RuntimeError("%s can't be inlined safely: it contains a <script or </script sequence" % path)
    return source


def inert_json(value):
    """JSON for a <script type="application/json"> block. Escaping < > & means the text can never close the
    block or start markup, so the browser only ever sees it as a string."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_page(source, file_name, folders):
    """The whole preview page for a Markdown document. file_name may be None for an unsaved buffer."""
    body = MARKDOWN.render(source)
    # The page never points back at the original file: no <base>, no folder path, no file:// URLs.
    # Only the file's name is kept, as the tab title. Local images are embedded instead, which needs the
    # project folders to know what may be read.
    images = embed_local_images(body, file_name, folders) if file_name else {}
    # A fresh nonce per preview: only our own script tags carry it, so scripts in the document can't run.
    nonce = secrets.token_urlsafe(16)
    scripts = SCRIPTS + (MERMAID_SCRIPTS if '<pre class="mermaid">' in body else [])
    values = {
        "nonce": nonce,
        "title": html.escape(os.path.basename(file_name) if file_name else "Untitled"),
        "body": inert_json(body),
        "images": inert_json(images),
        "scripts": "".join('<script nonce="%s">%s</script>\n' % (nonce, script_source(path)) for path in scripts),
    }
    # One pass, so nothing filled in is scanned again: the document's text can't smuggle in a placeholder.
    # (The CSS's literal % signs never match the placeholder pattern.)
    return PLACEHOLDER.sub(lambda match: values[match.group(1)], PAGE)
