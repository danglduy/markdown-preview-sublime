// Raw HTML in the document stays allowed (READMEs use details blocks, image widths, centred paragraphs), so the
// rendered HTML is never written into the page as markup. It arrives as an inert JSON string, and this script cleans
// it with DOMPurify, using the browser's own parser, before anything is shown. If the script can't run, the page
// stays empty.
//
// Beyond DOMPurify's defaults, like GitHub: no style tags or attributes (no overlays or CSS beacons), no form
// controls except task-list checkboxes, and every id/name gets a "user-content-" prefix so the document can't
// replace page properties this script relies on (DOM clobbering). In-page links are pointed at the prefixed ids to
// match. Local images are swapped for the data: URIs the plugin embedded, since the page has no base URL to find
// them by.
(() => {
  const content = document.getElementById("content");
  const source = JSON.parse(document.getElementById("source").textContent);
  const images = new Map(Object.entries(JSON.parse(document.getElementById("images").textContent)));
  const clean = DOMPurify.sanitize(source, {
    RETURN_DOM_FRAGMENT: true,
    SANITIZE_NAMED_PROPS: true,
    FORBID_TAGS: ["style", "form", "button", "textarea", "select"],
    FORBID_ATTR: ["style"],
  });
  for (const link of clean.querySelectorAll("a[href]")) {
    const href = link.getAttribute("href");
    if (href.startsWith("#")) {
      const target = href.slice(1);
      if (target && !target.startsWith("user-content-")) link.setAttribute("href", "#user-content-" + target);
    } else {
      // Leaving the preview opens a new tab, which gets no handle on this page and no referrer.
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }
  }
  for (const anchor of clean.querySelectorAll(".header-anchor")) {
    anchor.setAttribute("aria-label", "Link to " + anchor.parentElement.textContent.trim());
  }
  for (const image of clean.querySelectorAll("img[src]")) {
    const embedded = images.get(image.getAttribute("src"));
    if (embedded) image.setAttribute("src", embedded);
  }
  content.append(clean);
  // A clicked heading link keeps focus (Safari doesn't focus links on click), so its ring stays after scrolling.
  content.addEventListener("click", (event) => {
    const anchor = event.target.closest(".header-anchor");
    if (!anchor) return;
    anchor.focus({ preventScroll: true });
    requestAnimationFrame(() => anchor.focus({ preventScroll: true }));
  });
})();
