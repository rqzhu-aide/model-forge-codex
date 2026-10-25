import { isVisibleElement } from "./dialogFocus.js";

const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const text = (value) => typeof value === "string" ? value : "";
const number = (value) => Number.isFinite(value) ? value : 0;
const tabs = { P1: ["setting", "frameworks", "papers", "coverage"], P2: ["method", "assumptions", "computation", "review"], P3: ["claims", "assumptions", "arguments", "review"], P4: ["setup", "comparisons", "computation", "tuning", "sensitivity"], P5: ["manuscript", "evidence", "reviews", "changes"] };

export function readerScope(phase, branch = "trunk") {
  return ["P1", "P2"].includes(phase) ? phase : `${phase}:${branch}`;
}
export function normalizeReader(value, phase) {
  if (!object(value)) return {};
  const result = {};
  if (typeof phase === "string" && Object.hasOwn(tabs, phase) && tabs[phase].includes(value.tab)) result.tab = value.tab;
  for (const key of ["query", "topicId", "paperId", "frameworkId", "search", "selectedNode"]) if (typeof value[key] === "string" || key === "selectedNode" && value[key] === null) result[key] = value[key];
  if (typeof value.related === "boolean") result.related = value.related;
  if (phase === "P4" && ["all", "synthetic", "researcher_observed", "external_data", "computational_check", "other"].includes(value.dataView)) result.dataView = value.dataView;
  if (phase === "P2" && object(value.modelDisclosures)) result.modelDisclosures = Object.fromEntries(Object.entries(value.modelDisclosures)
    .filter(([key, sections]) => key && object(sections))
    .map(([key, sections]) => [key, Object.fromEntries(["assumptions", "computation", "review"].filter((name) => typeof sections[name] === "boolean").map((name) => [name, sections[name]]))]));
  if (object(value.origin) && text(value.origin.id)) {
    result.origin = { id: value.origin.id, title: text(value.origin.title) };
    if (value.origin.kind === "citation") result.origin.kind = "citation";
    if (text(value.origin.anchor)) result.origin.anchor = value.origin.anchor;
    if (object(value.origin.notation) && text(value.origin.notation.basisId)) result.origin.notation = { basisId: value.origin.notation.basisId, scrollTop: Math.max(0, number(value.origin.notation.scrollTop)) };
    if (object(value.origin.position)) result.origin.position = normalizeReader({ position: value.origin.position }, phase).position;
  }
  if (object(value.entrySelection) && text(value.entrySelection.sourceId) && object(value.entrySelection.reference)) {
    result.entrySelection = { sourceId: value.entrySelection.sourceId, reference: Object.fromEntries(["role", "family", "run_id", "entry_id", "entry_sha256"].filter((key) => typeof value.entrySelection.reference[key] === "string").map((key) => [key, value.entrySelection.reference[key]])) };
    if (typeof value.entrySelection.memberKey === "string") result.entrySelection.memberKey = value.entrySelection.memberKey;
    if (text(value.entrySelection.citationBasisId)) result.entrySelection.citationBasisId = value.entrySelection.citationBasisId;
  }
  if (object(value.position)) {
    const position = value.position;
    result.position = { y: Math.max(0, number(position.y)), offset: number(position.offset), disclosures: Array.isArray(position.disclosures) ? position.disclosures.filter((item) => object(item) && Number.isInteger(item.index) && item.index >= 0 && typeof item.summary === "string").map(({ index, summary, anchor }) => ({ index, summary, ...(text(anchor) ? { anchor } : {}) })) : [] };
    if (object(position.anchor) && ["data-card-role", "data-question-id", "data-reading-anchor"].includes(position.anchor.kind) && text(position.anchor.value)) result.position.anchor = { kind: position.anchor.kind, value: position.anchor.value, ...(Number.isInteger(position.anchor.index) && position.anchor.index >= 0 ? { index: position.anchor.index } : {}) };
  }
  return result;
}
export function normalizeNavigation(value) {
  const result = { projectId: object(value) && text(value.projectId) || null, contexts: {} };
  if (!object(value?.contexts)) return result;
  for (const [id, saved] of Object.entries(value.contexts)) {
    if (!object(saved)) continue;
    const phase = typeof saved.phase === "string" && Object.hasOwn(tabs, saved.phase) ? saved.phase : "P1"; const branch = text(saved.branch) || "trunk";
    const readers = {};
    if (object(saved.readers)) for (const [scope, reader] of Object.entries(saved.readers)) if (Object.hasOwn(tabs, scope.split(":")[0])) readers[scope] = normalizeReader(reader, scope.split(":")[0]);
    // Older navigation stored the graph selection at project scope.
    if (typeof saved.selectedNode === "string" && !readers[readerScope("P3", branch)]) readers[readerScope("P3", branch)] = { selectedNode: saved.selectedNode };
    result.contexts[id] = { phase, branch, readers, ...(text(saved.p2ProposalKey) ? { p2ProposalKey: saved.p2ProposalKey } : {}), ...(typeof saved.p2SharedPreparation === "boolean" ? { p2SharedPreparation: saved.p2SharedPreparation } : {}) };
  }
  return result;
}

const anchors = '[data-reading-anchor],[data-question-id],[data-card-role]:not([data-card-role="history"])';
export function captureReadingPosition(root) {
  if (!root) return null;
  const candidates = [...root.querySelectorAll(anchors)].filter((element) => !element.closest(".project-toolbar") && isVisibleElement(element) && element.getBoundingClientRect().bottom > 0 && element.getBoundingClientRect().top < window.innerHeight);
  const target = candidates.sort((a, b) => Math.abs(a.getBoundingClientRect().top) - Math.abs(b.getBoundingClientRect().top))[0];
  const kind = target && ["data-reading-anchor", "data-question-id", "data-card-role"].find((attribute) => target.hasAttribute(attribute));
  const matching = target && [...root.querySelectorAll(`[${kind}]`)].filter((element) => element.getAttribute(kind) === target.getAttribute(kind) && isVisibleElement(element));
  const allDetails = [...root.querySelectorAll("details")]; const disclosures = [];
  for (const [index, detail] of allDetails.entries()) {
    if (!detail.open || detail.closest(".project-toolbar") || !isVisibleElement(detail)) continue;
    disclosures.push({ index, summary: detail.querySelector(":scope > summary")?.textContent || "", ...(detail.getAttribute("data-reading-anchor") ? { anchor: detail.getAttribute("data-reading-anchor") } : {}) });
  }
  return { y: window.scrollY, offset: target?.getBoundingClientRect().top || 0, ...(target ? { anchor: { kind, value: target.getAttribute(kind), ...(matching.length > 1 ? { index: matching.indexOf(target) } : {}) } } : {}), disclosures };
}

// Capture when a response is ready to commit, after any reading during fetch.
// Keep the current screen position through the commit and its delayed tables.
// Any reader action ends this short preservation window. A remounted disclosure
// can retain its focused summary, but removed editor controls never gain a substitute.
export function preserveReadingUpdate(root) {
  if (!root) return null;
  const active = document.activeElement;
  const visible = (element) => isVisibleElement(element) && element.getBoundingClientRect().bottom > 0 && element.getBoundingClientRect().top < window.innerHeight;
  let focused = root.contains(active) && !active.closest(".project-toolbar") && visible(active) ? active : null;
  const disclosure = focused?.tagName === "SUMMARY" && focused.parentElement?.tagName === "DETAILS" ? focused.parentElement : null;
  const matchingSummaries = (anchor, label) => [...root.querySelectorAll("details[data-reading-anchor]")]
    .filter((element) => element.getAttribute("data-reading-anchor") === anchor)
    .map((element) => element.querySelector(":scope > summary"))
    .filter((element) => element?.textContent === label && isVisibleElement(element));
  const summary = disclosure?.getAttribute("data-reading-anchor") && disclosure.querySelector(":scope > summary") === focused
    && matchingSummaries(disclosure.getAttribute("data-reading-anchor"), focused.textContent).length === 1
    ? { anchor: disclosure.getAttribute("data-reading-anchor"), text: focused.textContent } : null;
  const position = focused ? null : captureReadingPosition(root);
  if (!focused && !position?.anchor) return null;
  const offset = focused ? focused.getBoundingClientRect().top : position.offset;
  let disposed = false; let observer; let timer;
  const events = ["wheel", "touchstart", "pointerdown", "keydown", "focusin"];
  const dispose = () => {
    disposed = true; observer?.disconnect(); clearTimeout(timer);
    for (const event of events) window.removeEventListener(event, dispose, true);
  };
  for (const event of events) window.addEventListener(event, dispose, { capture: true, passive: true });
  timer = setTimeout(dispose, 2500);
  const restore = () => {
    if (disposed) return;
    if (!root.isConnected) { dispose(); return; }
    if (focused && !focused.isConnected) {
      if (!summary || document.activeElement !== document.body) { dispose(); return; }
      const matches = matchingSummaries(summary.anchor, summary.text);
      if (matches.length !== 1) { dispose(); return; }
      // A keyed preparation form can change scope at publication while this
      // logical disclosure survives. Its own focusin is not a reader action.
      focused = matches[0];
      window.removeEventListener("focusin", dispose, true);
      focused.focus({ preventScroll: true });
      window.addEventListener("focusin", dispose, { capture: true, passive: true });
    }
    const target = focused || [...root.querySelectorAll(`[${position.anchor.kind}]`)].filter((element) => element.getAttribute(position.anchor.kind) === position.anchor.value && isVisibleElement(element))[position.anchor.index || 0];
    if (!target?.isConnected || !root.contains(target) || focused && document.activeElement !== focused) { dispose(); return; }
    const delta = target.getBoundingClientRect().top - offset;
    if (Math.abs(delta) > 0.5) window.scrollTo({ top: Math.max(0, window.scrollY + delta), behavior: "instant" });
  };
  return {
    restore() {
      if (disposed) return;
      restore();
      if (disposed) return;
      if (!observer && typeof ResizeObserver !== "undefined") { observer = new ResizeObserver(restore); observer.observe(root); }
    },
    dispose,
  };
}

// One restoration per real navigation, after the selected reader and any saved
// table page are ready. Polling and preference updates never call this function.
export function restoreOpenDisclosures(root, disclosures = []) {
  const details = [...root.querySelectorAll("details")];
  const summary = (element) => element?.querySelector(":scope > summary")?.textContent;
  for (const saved of disclosures) {
    const matches = details.filter((element) => saved.anchor ? element.getAttribute("data-reading-anchor") === saved.anchor : summary(element) === saved.summary);
    const target = matches.length === 1 ? matches[0] : null;
    if (target) target.open = true;
  }
}

export function restoreReadingPosition(root, position, focus = false, onRestored) {
  let cancelled = false; let frame;
  restoreOpenDisclosures(root, position?.disclosures);
  const restore = () => {
    if (root.querySelector('[data-reading-pending="true"]')) return;
    observer.disconnect();
    frame = requestAnimationFrame(() => {
      if (cancelled) return;
      const target = position?.anchor && [...root.querySelectorAll(`[${position.anchor.kind}]`)].filter((element) => element.getAttribute(position.anchor.kind) === position.anchor.value && isVisibleElement(element))[position.anchor.index || 0];
      window.scrollTo({ top: target ? window.scrollY + target.getBoundingClientRect().top - position.offset : position?.y || 0, behavior: "instant" });
      if (focus && target) target.focus({ preventScroll: true });
      onRestored?.(root);
    });
  };
  const observer = new MutationObserver(restore);
  observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-reading-pending"] });
  restore();
  return () => { cancelled = true; observer.disconnect(); cancelAnimationFrame(frame); };
}
