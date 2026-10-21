import test from "node:test";
import assert from "node:assert/strict";
import { beginRunReturn, captureRunOrigin } from "../src/runReturnFocus.js";
import { groupRunFindings } from "../src/runFindings.js";

function fixture() {
  const listeners = new Set(); const focused = [];
  const oldDocument = globalThis.document, oldStyle = globalThis.getComputedStyle;
  globalThis.document = { body: {}, documentElement: {}, addEventListener: (_, cb) => listeners.add(cb), removeEventListener: (_, cb) => listeners.delete(cb) };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  const element = (key, parent = null) => ({ isConnected: true, tagName: "BUTTON", parentElement: parent, getClientRects: () => [{}], closest: () => null,
    getAttribute: (name) => name === "data-run-origin" ? key : null, matches() { return Boolean(this.disabled); }, setAttribute(name, value) { this[name] = value; }, focus: (options) => focused.push({ key, options }) });
  const detail = { tagName: "DETAILS", open: true, parentElement: null, getAttribute: () => "work-activity", querySelector: () => ({ textContent: "Activity", contains: () => false }) };
  const button = element("activity:run.1", detail), heading = element("heading");
  const root = { querySelectorAll: (selector) => selector === "details" ? [detail] : selector === "[data-run-origin]" ? [button] : [heading] };
  detail.parentElement = root;
  return { root, button, detail, heading, focused, listeners, move: (target) => [...listeners].forEach((cb) => cb({ target })), cleanup: () => { globalThis.document = oldDocument; globalThis.getComputedStyle = oldStyle; } };
}

test("Activity return restores its disclosure, exact control and focus only once without scrolling", () => {
  const f = fixture();
  try {
    const origin = captureRunOrigin(f.root, f.button, "project:P1:trunk"); f.detail.open = false;
    const returning = beginRunReturn(origin); returning.prepare(f.root, "project:P1:trunk"); assert.equal(f.detail.open, true);
    returning.finish(f.root, "project:P1:trunk"); returning.finish(f.root, "project:P1:trunk");
    assert.deepEqual(f.focused, [{ key: "activity:run.1", options: { preventScroll: true } }]); assert.equal(f.listeners.size, 0);
  } finally { f.cleanup(); }
});

test("focus moved during research loading is preserved even after that control disappears", () => {
  const f = fixture();
  try { const returning = beginRunReturn(captureRunOrigin(f.root, f.button, "p")); const temporary = {}; f.move(temporary); returning.finish(f.root, "p"); assert.deepEqual(f.focused, []); }
  finally { f.cleanup(); }
});

test("a hidden origin or changed context returns to a visible focusable heading", () => {
  for (const hidden of [true, false]) {
    const f = fixture();
    try { const returning = beginRunReturn(captureRunOrigin(f.root, f.button, "p")); if (hidden) f.detail.open = false;
      returning.finish(f.root, hidden ? "p" : "different"); assert.equal(f.heading.tabindex, "-1"); assert.equal(f.focused[0].key, "heading"); }
    finally { f.cleanup(); }
  }
});

test("cancelled navigation cannot focus the old origin", () => {
  const f = fixture(); try { const returning = beginRunReturn(null); returning.cancel(); returning.finish(f.root, "p"); assert.deepEqual(f.focused, []); } finally { f.cleanup(); }
});

test("disabled origin uses the heading and cancelled or changed-scope preparation stays closed", () => {
  const f = fixture();
  try { const returning = beginRunReturn(captureRunOrigin(f.root, f.button, "p")); f.detail.open = false;
    returning.prepare(f.root, "different"); assert.equal(f.detail.open, false); f.button.disabled = true;
    returning.prepare(f.root, "p"); returning.finish(f.root, "p"); assert.equal(f.focused[0].key, "heading");
    f.detail.open = false; returning.prepare(f.root, "p"); assert.equal(f.detail.open, false);
  } finally { f.cleanup(); }
});

test("citation groups retain every owner finding and exact differing source values", () => {
  const detail = { kind: "citation_conflict", group_id: "doi.1", paper_title: "Paper", differing_fields: ["authors"], entries: [{ family: "p1.lead_literature", json_pointer: "/papers/0/source", source_sha256: "a", source: { authors: ["A."] } }] };
  const first = { code: "literature.metadata_reconciliation_pending", object_id: "p1.lead_literature", details: detail };
  const second = { ...first, object_id: "p1.theory_literature", details: { ...detail, entries: [...detail.entries, { family: "p1.theory_literature", json_pointer: "/papers/1/source", source_sha256: "b", source: { authors: ["A", "Trial group"] } }] } };
  const groups = groupRunFindings([first, second, { code: "runtime.failure", message: "Unavailable" }]);
  assert.equal(groups.length, 2); assert.deepEqual(groups[0].findings, [first, second]); assert.deepEqual(groups[0].entries[1].source.authors, ["A", "Trial group"]);
});
