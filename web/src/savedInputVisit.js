import { availableFocusTarget } from "./dialogFocus.js";
import { captureReadingPosition, readerScope, restoreReadingPosition } from "./readingPosition.js";
import { phaseInputDestination, phaseInputStickyOffset } from "./phaseInputNavigation.js";

// Only selections which change the displayed questions belong to the visit.
// P1/P2 still remember the method branch to restore the researcher's full view.
export function savedInputViewKey(projectId, context) {
  return JSON.stringify([projectId, context.phase || "P1", context.branch || "trunk",
    context.phase === "P2" ? context.p2ProposalKey || null : null]);
}

export function captureSavedInputVisit({ projectId, context, reading, root, origin, destination }) {
  if (!root || !origin || !root.contains(origin)) return null;
  const anchors = [];
  for (let element = origin; element && element !== root; element = element.parentElement) {
    const anchor = element.getAttribute("data-reading-anchor");
    if (anchor && !anchors.includes(anchor)) anchors.push(anchor);
  }
  if (!anchors.includes("phase-decisions")) anchors.push("phase-decisions");
  return {
    projectId,
    context: { phase: context.phase || "P1", branch: context.branch || "trunk",
      p2ProposalKey: context.p2ProposalKey, p2SharedPreparation: context.p2SharedPreparation },
    reading: structuredClone(reading || {}),
    position: captureReadingPosition(root),
    originKey: origin.getAttribute("data-phase-input-origin"),
    anchors,
    destinationKey: savedInputViewKey(projectId, { ...context, ...destination }),
  };
}

export function savedInputReturnContext(visit, context) {
  const scope = readerScope(visit.context.phase, visit.context.branch);
  return { ...visit.context, readers: { ...context.readers,
    [scope]: { ...visit.reading, position: visit.position } } };
}

// This replaces the ordinary reader restoration for the return. Focus never
// scrolls again, and polling cannot replay the visit after its completion.
export function restoreSavedInputVisit(root, visit, onRestored, onUnavailable) {
  let cancelled = false; let frame; let cancelRestore;
  const events = ["wheel", "touchstart", "pointerdown", "keydown"];
  const dispose = () => {
    cancelled = true; observer.disconnect(); cancelAnimationFrame(frame); cancelRestore?.();
    for (const event of events) window.removeEventListener(event, dispose, true);
  };
  const prepare = () => {
    if (cancelled || frame || root.querySelector('[data-reading-pending="true"]')) return;
    frame = requestAnimationFrame(() => {
      frame = null;
      if (cancelled || root.querySelector('[data-reading-pending="true"]')) return;
      observer.disconnect();
      cancelRestore = restoreAvailableInput(root, visit, (restored) => { dispose(); onRestored?.(restored); }, onUnavailable);
    });
  };
  const observer = new MutationObserver(prepare);
  observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-reading-pending"] });
  for (const event of events) window.addEventListener(event, dispose, { capture: true, passive: true });
  prepare();
  return dispose;
}

function restoreAvailableInput(root, visit, onRestored, onUnavailable) {
  const matches = visit.originKey ? [...root.querySelectorAll("[data-phase-input-origin]")]
    .filter(element => element.getAttribute("data-phase-input-origin") === visit.originKey) : [];
  const origin = matches.length === 1 ? matches[0] : null;
  const fallback = !origin && visit.anchors.map(anchor => phaseInputDestination(root, anchor)).find(Boolean);
  const target = origin || fallback;
  for (let element = target; element && element !== root; element = element.parentElement) {
    if (element.tagName === "DETAILS") element.open = true;
  }
  const position = fallback ? { ...visit.position,
    anchor: { kind: "data-reading-anchor", value: fallback.getAttribute("data-reading-anchor") },
    offset: phaseInputStickyOffset(root) } : visit.position;
  return restoreReadingPosition(root, position, false, () => {
    // Opening only native ancestor disclosures also recovers a surviving badge
    // when its previously selected saved item disappeared during the visit.
    const focus = target?.tagName === "DETAILS" ? target.querySelector(":scope > summary") : target;
    if (focus && availableFocusTarget(focus)) {
      if (!focus.hasAttribute("tabindex") && !focus.matches("button,a,input,textarea,select,summary")) focus.setAttribute("tabindex", "-1");
      focus.focus({ preventScroll: true });
    }
    if (!origin) onUnavailable?.("That saved item is no longer available here. Your saved input is open at the closest available group.");
    onRestored?.(root);
  });
}

// A successful request is not enough when an endpoint returned only part of its
// contract. Keep known content visible, but do not announce an empty decision set.
export function decisionDataState({ data, error, loading, needsMethod, phase, branch }) {
  if (!data || needsMethod) return "unavailable";
  const pending = data.pending;
  const complete = ["attention", "researcher_answers", "runs_awaiting_direction", "runs_needing_correction"]
    .every(key => Array.isArray(pending?.[key]))
    && Array.isArray(data.artifacts?.issues) && Array.isArray(data.artifacts?.load_errors)
    && !data.artifacts.load_errors.some(issue => (!issue.phase || issue.phase === phase) && (!issue.branch || issue.branch === branch));
  if (!complete) return "partial";
  return error ? "refresh-failed" : loading ? "refreshing" : "ready";
}
