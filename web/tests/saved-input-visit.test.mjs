import test from "node:test";
import assert from "node:assert/strict";
import { captureSavedInputVisit, decisionDataState, restoreSavedInputVisit, savedInputReturnContext, savedInputViewKey } from "../src/savedInputVisit.js";
import { navigationDom } from "./fixtures/saved-input-navigation-dom.mjs";

test("saved-input visits restore exact view, disclosures and invoking control after their reader is ready", () => {
  const dom = navigationDom();
  try {
    const original = dom.saved();
    const context = { phase: "P2", branch: "method.b", p2ProposalKey: "run.b:proposal.b", p2SharedPreparation: true };
    const reading = { tab: "review", modelDisclosures: { "run.b:proposal.b": { computation: true } } };
    const visit = captureSavedInputVisit({ projectId: "project", context, reading, root: dom.root, origin: original.origin, destination: { phase: "P1" } });
    assert.equal(visit.destinationKey, savedInputViewKey("project", { ...context, phase: "P1" }));
    const current = { readers: { P1: { tab: "setting" }, P2: { tab: "method" } } };
    assert.deepEqual(savedInputReturnContext(visit, current), { ...context, readers: { P1: current.readers.P1, P2: { ...reading, position: visit.position } } });
    reading.modelDisclosures["run.b:proposal.b"].computation = false;
    assert.equal(visit.reading.modelDisclosures["run.b:proposal.b"].computation, true);
    const returned = dom.saved(); returned.badge.open = false; returned.item.open = false;
    const pending = dom.root.append(new dom.Element("div", { "data-reading-pending": "true" }));
    window.scrollY = 100; let restored = 0;
    restoreSavedInputVisit(dom.root, visit, () => restored++); dom.flush();
    assert.equal(dom.scrolls.length, 0); assert.equal(dom.focused.length, 0);
    pending.removeAttribute("data-reading-pending"); dom.changed(); dom.flush();
    assert.ok(returned.badge.open && returned.item.open);
    assert.deepEqual(dom.scrolls, [{ top: 800, behavior: "instant" }]);
    assert.deepEqual(dom.focused, [{ element: returned.origin, options: { preventScroll: true } }]);
    dom.changed(); dom.flush(); assert.equal(restored, 1); assert.equal(dom.scrolls.length, 1);
  } finally { dom.cleanup(); }
});

test("a removed saved item returns to its phase badge with one scroll and an honest notice", () => {
  const dom = navigationDom();
  try {
    const original = dom.saved();
    const visit = captureSavedInputVisit({ projectId: "project", context: { phase: "P4", branch: "method.b" }, root: dom.root, origin: original.origin, destination: { phase: "P1" } });
    const returned = dom.saved(); returned.badge.children = [returned.badgeSummary]; returned.badge.open = false;
    const notices = []; restoreSavedInputVisit(dom.root, visit, undefined, message => notices.push(message)); dom.flush();
    assert.deepEqual(dom.focused, [{ element: returned.badgeSummary, options: { preventScroll: true } }]);
    assert.deepEqual(dom.scrolls, [{ top: 804, behavior: "instant" }]);
    assert.equal(notices.length, 1); assert.match(notices[0], /no longer available/);
  } finally { dom.cleanup(); }
});

test("a late-mounted item is resolved after its reader settles before choosing a fallback", () => {
  const dom = navigationDom();
  try {
    const original = dom.saved();
    const visit = captureSavedInputVisit({ projectId: "project", context: { phase: "P2", branch: "method.b" }, root: dom.root, origin: original.origin, destination: { phase: "P1" } });
    dom.root.children = [];
    dom.root.append(new dom.Element("div", { "data-reading-pending": "true" }));
    const notices = []; restoreSavedInputVisit(dom.root, visit, undefined, message => notices.push(message)); dom.flush();
    assert.equal(dom.focused.length, 0);
    const returned = dom.saved(); dom.changed(); dom.flush();
    assert.equal(dom.focused.at(-1).element, returned.origin);
    assert.equal(dom.scrolls.length, 1); assert.deepEqual(notices, []);
  } finally { dom.cleanup(); }
});

test("decision emptiness requires complete scoped data and distinguishes retained refresh content", () => {
  const data = { pending: { attention: [], researcher_answers: [], runs_awaiting_direction: [], runs_needing_correction: [] }, artifacts: { issues: [], load_errors: [] } };
  const input = { data, phase: "P4", branch: "method.b" };
  assert.equal(decisionDataState(input), "ready");
  assert.equal(decisionDataState({ ...input, error: "Refresh failed" }), "refresh-failed");
  assert.equal(decisionDataState({ ...input, loading: true }), "refreshing");
  assert.equal(decisionDataState({ ...input, needsMethod: true }), "unavailable");
  assert.equal(decisionDataState({ ...input, data: null }), "unavailable");
  for (const key of Object.keys(data.pending)) {
    const partial = structuredClone(data); delete partial.pending[key];
    assert.equal(decisionDataState({ ...input, data: partial, error: "Refresh failed" }), "partial");
  }
  for (const key of ["issues", "load_errors"]) {
    const partial = structuredClone(data); delete partial.artifacts[key];
    assert.equal(decisionDataState({ ...input, data: partial }), "partial");
  }
  data.artifacts.load_errors = [{ branch: "method.b", phase: "P4", message: "Source unavailable" }];
  assert.equal(decisionDataState(input), "partial");
  data.artifacts.load_errors[0].branch = "method.a";
  assert.equal(decisionDataState(input), "ready");
});
