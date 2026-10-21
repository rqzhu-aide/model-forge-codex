import { isVisibleElement, availableFocusTarget } from "./dialogFocus.js";
import { restoreOpenDisclosures } from "./readingPosition.js";

export function captureRunOrigin(root, control, scope) {
  if (!root || !control?.getAttribute("data-run-origin")) return null;
  const disclosures = [];
  for (let parent = control.parentElement; parent && parent !== root; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS" && parent.open) disclosures.unshift({ summary: parent.querySelector(":scope > summary")?.textContent || "", anchor: parent.getAttribute("data-reading-anchor") || "" });
  }
  return { key: control.getAttribute("data-run-origin"), scope, disclosures };
}

export function beginRunReturn(origin) {
  let moved = false; let active = true;
  const track = (event) => { if (event.target !== document.body && event.target !== document.documentElement) moved = true; };
  document.addEventListener("focusin", track);
  const cancel = () => { active = false; document.removeEventListener("focusin", track); };
  return {
    prepare(root, scope) { if (active && !moved && origin?.scope === scope) restoreOpenDisclosures(root, origin.disclosures); },
    finish(root, scope) {
      if (!active) return;
      cancel();
      if (moved) return;
      const target = origin?.scope === scope && [...root.querySelectorAll("[data-run-origin]")].find((element) => element.getAttribute("data-run-origin") === origin.key && availableFocusTarget(element));
      const fallback = [...root.querySelectorAll("h1,h2")].find(isVisibleElement) || root;
      if (!target) fallback.setAttribute("tabindex", "-1");
      (target || fallback).focus({ preventScroll: true });
    },
    cancel,
  };
}
