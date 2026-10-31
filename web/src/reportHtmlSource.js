import { dialogFocusTargets } from "./dialogFocus";

// Parse in an inert template, never in the app document. The original verified
// artifact is retained; this preview cannot execute its code or fetch assets.
export function reportHtmlPreview(text, ownerDocument = document) {
  const template = ownerDocument.createElement("template");
  template.innerHTML = text;
  template.content.querySelectorAll("script,noscript,base,meta,link,iframe,frame,frameset,object,embed,form,input,button,textarea,select,title").forEach((element) => element.remove());
  for (const element of template.content.querySelectorAll("*")) {
    // SVG mutation elements could add a new navigable href after preparation.
    // Static KaTeX paths remain intact; the preview has no active animation.
    if (/^(?:animate.*|set|discard)$/i.test(element.localName)) { element.remove(); continue; }
    const source = element.localName === "a" ? element.getAttribute("href") : null;
    const image = element.localName === "img" ? element.getAttribute("src") : null;
    for (const attribute of [...element.attributes]) {
      if (/^on/i.test(attribute.name) || /^(?:src|srcset|href|xlink:href|action|formaction|srcdoc|target|download|ping|autofocus|contenteditable|data-report-source)$/i.test(attribute.name)) element.removeAttribute(attribute.name);
    }
    if (source !== null) {
      element.setAttribute("data-report-source", source);
      element.setAttribute("href", "#");
    }
    if (/^data:image\//i.test(image || "")) element.setAttribute("src", image);
  }
  const policy = "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; font-src data:; img-src data:; connect-src 'none'; form-action 'none'; base-uri 'none'; object-src 'none'; frame-src 'none'";
  return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}"><meta name="referrer" content="no-referrer"></head><body>${template.innerHTML}</body></html>`;
}

const fragmentName = (value) => { try { return decodeURIComponent(value); } catch { return value; } };

// Parent-owned handlers bridge the sandbox boundary. Authored scripts remain
// disabled, while Escape, Tab and source navigation use the existing dialog.
export function bindReportHtmlFrame(frame, { fragment = "", onClose, onSourceLink, onMissingAnchor }) {
  const sourceDocument = frame?.contentDocument;
  if (!sourceDocument) return () => {};
  const focusAnchor = (name) => {
    const matches = name ? [...sourceDocument.querySelectorAll("[id]")].filter((element) => element.id === name) : [];
    const target = name ? matches.length === 1 ? matches[0] : null : sourceDocument.body;
    onMissingAnchor(target || !name ? "" : name);
    if (!target) return;
    target.setAttribute("tabindex", "-1");
    target.scrollIntoView({ block: "start" });
    target.focus({ preventScroll: true });
  };
  const click = (event) => {
    const link = event.target.closest?.("a");
    if (!link) return;
    event.preventDefault();
    const source = link.getAttribute("data-report-source") || "";
    if (source.startsWith("#")) focusAnchor(fragmentName(source.slice(1)));
    else onSourceLink(source, link.textContent, link);
  };
  const keydown = (event) => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); onClose(); }
    if (event.key !== "Tab") return;
    const inside = dialogFocusTargets(sourceDocument.body);
    if (inside.length && sourceDocument.activeElement !== (event.shiftKey ? inside[0] : inside.at(-1))) return;
    const dialog = frame.closest('[role="dialog"]');
    if (!dialog) return;
    const outside = dialogFocusTargets(dialog);
    const index = outside.indexOf(frame);
    if (index < 0) return;
    event.preventDefault();
    outside[(index + (event.shiftKey ? -1 : 1) + outside.length) % outside.length]?.focus({ preventScroll: true });
  };
  sourceDocument.addEventListener("click", click, true);
  sourceDocument.addEventListener("keydown", keydown);
  focusAnchor(fragment);
  return () => { sourceDocument.removeEventListener("click", click, true); sourceDocument.removeEventListener("keydown", keydown); };
}
