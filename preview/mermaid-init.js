// The theme follows the system light/dark mode like the page.
// "strict" makes Mermaid escape HTML in labels and ignore click handlers written in the diagram.
mermaid.initialize({
  startOnLoad: true,
  securityLevel: "strict",
  theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default",
});
