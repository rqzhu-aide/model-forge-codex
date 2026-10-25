import { availableFocusTarget, isVisibleElement } from "./dialogFocus.js";
import { captureReadingPosition, restoreReadingPosition } from "./readingPosition.js";

const unavailable = "This source has changed or is no longer available here. Review the current rerun summary and try again.";
const headingSelector = "h1,h2,h3,h4,h5,h6,[role=heading]";

// Compare attribute values directly. Exact question identities contain JSON and
// source pointers, so interpolating them into a selector is unsafe and brittle.
export function phaseInputDestination(root, anchor) {
  if (!root || typeof anchor !== "string" || !anchor) return null;
  const matches = [...root.querySelectorAll("[data-reading-anchor]")].filter((element) => {
    if (element.getAttribute("data-reading-anchor") !== anchor || element.closest("[hidden],[inert]")) return false;
    for (let parent = element; parent && parent !== root; parent = parent.parentElement) {
      const style = getComputedStyle(parent);
      if (style.display === "none" || style.visibility === "hidden") return false;
    }
    return true;
  });
  return matches.length === 1 ? matches[0] : null;
}

function openDestination(root, target) {
  const path = [];
  for (let parent = target; parent && parent !== root; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS") path.unshift(parent);
  }
  for (const disclosure of path) disclosure.open = true;
}

function destinationFocus(target) {
  if (target.tagName === "DETAILS") {
    const summary = target.querySelector(":scope > summary");
    return summary && isVisibleElement(summary) ? summary : target;
  }
  if (target.matches(headingSelector) || target.tagName === "SUMMARY") return target;
  return [...target.querySelectorAll(headingSelector)].find(isVisibleElement) || target;
}

export function phaseInputStickyOffset(root) {
  const toolbar = root.querySelector(".project-toolbar");
  if (!toolbar || !isVisibleElement(toolbar)) return 16;
  const rect = toolbar.getBoundingClientRect();
  const style = getComputedStyle(toolbar);
  return (rect.height ?? rect.bottom - rect.top) + Math.max(0, parseFloat(style.top) || 0) + 16;
}

function originControl(root, origin, key, rowAnchor) {
  if (origin?.isConnected && root.contains(origin) && availableFocusTarget(origin)) return origin;
  if (key) {
    const matches = [...root.querySelectorAll("[data-phase-input-origin]")]
      .filter((element) => element.getAttribute("data-phase-input-origin") === key && availableFocusTarget(element));
    if (matches.length === 1) return matches[0];
  }
  // Saving the last unanswered question can remove its nonzero count button.
  // Return to the same summary row's label, rather than another category.
  const row = phaseInputDestination(root, rowAnchor);
  const label = row?.querySelector(".input-summary-label");
  return label && availableFocusTarget(label) ? label : null;
}

// Call only from an explicit summary activation. Polling and ordinary reader
// updates have no reason to call this helper or replay its scroll/focus work.
// A changing scope should be supplied as a getter, for example () => scopeRef.current.
export function navigatePhaseInput({ root, origin, anchor, scope, currentScope = () => scope, onUnavailable, onNavigated }) {
  root ||= origin?.closest('[data-reader-ready="true"]');
  const inScope = () => (typeof currentScope === "function" ? currentScope() : currentScope) === scope;
  const target = inScope() && phaseInputDestination(root, anchor);
  if (!target || !origin || !root.contains(origin)) { onUnavailable?.(unavailable); return null; }

  const position = captureReadingPosition(root);
  const originKey = origin.getAttribute("data-phase-input-origin");
  const originRow = origin.closest(".input-summary-row")?.getAttribute("data-reading-anchor");
  let state = "pending"; let frame; let emphasisTimer; let cancelRestore;
  const clearEmphasis = () => {
    clearTimeout(emphasisTimer);
    session.target.removeAttribute("data-phase-input-highlight");
  };
  const dispose = () => {
    state = "disposed"; cancelAnimationFrame(frame); cancelRestore?.(); clearEmphasis();
  };
  const session = {
    target, focusTarget: null,
    back() {
      if (state === "disposed" || state === "returning") return false;
      if (!inScope()) { dispose(); onUnavailable?.(unavailable); return false; }
      state = "returning"; cancelAnimationFrame(frame); clearEmphasis();
      cancelRestore = restoreReadingPosition(root, position, false, () => {
        if (state !== "returning" || !inScope()) return;
        const control = originControl(root, origin, originKey, originRow);
        state = "disposed";
        if (control) control.focus({ preventScroll: true });
        else onUnavailable?.("The original summary control is no longer available. Your prior reading position was restored.");
      });
      return true;
    },
    dispose,
  };

  openDestination(root, target);
  frame = requestAnimationFrame(() => {
    if (state !== "pending") return;
    const current = inScope() && phaseInputDestination(root, anchor);
    if (!current) { dispose(); onUnavailable?.(unavailable); return; }
    openDestination(root, current);
    if (!isVisibleElement(current)) { dispose(); onUnavailable?.(unavailable); return; }
    session.target = current;
    const focusTarget = destinationFocus(current);
    session.focusTarget = focusTarget;
    if (focusTarget.tagName !== "SUMMARY" && !focusTarget.hasAttribute("tabindex")) focusTarget.setAttribute("tabindex", "-1");
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: Math.max(0, window.scrollY + focusTarget.getBoundingClientRect().top - phaseInputStickyOffset(root)), behavior: reduced ? "instant" : "smooth" });
    focusTarget.focus({ preventScroll: true });
    current.setAttribute("data-phase-input-highlight", "true");
    emphasisTimer = setTimeout(clearEmphasis, 1600);
    state = "navigated";
    onNavigated?.(session);
  });
  return session;
}
