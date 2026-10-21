import test from "node:test";
import assert from "node:assert/strict";
import { captureReadingPosition, normalizeNavigation, normalizeReader, readerScope, restoreOpenDisclosures, restoreReadingPosition } from "../src/readingPosition.js";
import { tablePageIdentity, tablePageUrl, tableResumeOffset } from "../src/tableReading.js";

test("malformed navigation cannot replace the usable project context", () => {
  for (const value of [null, [], true, "text", 8, { contexts: [] }, { contexts: { a: null, b: [] } }]) assert.deepEqual(normalizeNavigation(value), { projectId: null, contexts: {} });
  const saved = normalizeNavigation({ projectId: 5, contexts: { a: { phase: "wrong", branch: [], readers: { P1: null, P2: [], "P3:method.a": { tab: "arguments", search: 12 } } } } });
  assert.equal(saved.projectId, null); assert.equal(saved.contexts.a.phase, "P1"); assert.equal(saved.contexts.a.branch, "trunk");
  assert.deepEqual(saved.contexts.a.readers["P3:method.a"], { tab: "arguments" });
  assert.equal(normalizeNavigation({ contexts: { a: { phase: "constructor" } } }).contexts.a.phase, "P1");
  assert.equal(normalizeNavigation({ contexts: { a: { phase: ["P3"] } } }).contexts.a.phase, "P1");
  assert.deepEqual(normalizeReader({ tab: "setting" }, "__proto__"), {});
});
test("reader scope separates method branches while P1 and P2 remain shared", () => {
  assert.equal(readerScope("P1", "method.a"), "P1"); assert.equal(readerScope("P2", "method.b"), "P2");
  assert.notEqual(readerScope("P3", "method.a"), readerScope("P3", "method.b"));
  const saved = normalizeNavigation({ contexts: { a: { branch: "method.a", phase: "P4", selectedNode: "claim.1" } } });
  assert.equal(saved.contexts.a.readers["P3:method.a"].selectedNode, "claim.1");
  assert.equal(saved.contexts.a.readers["P3:method.b"], undefined);
});

test("P2 disclosure state retains exact selected records and normalizes only native disclosure booleans", () => {
  const value = { modelDisclosures: { "run.a:proposal.a": { assumptions: true, computation: false, review: true, unknown: true }, "catalog:method.b:2:exact-hash": { assumptions: false, computation: true, review: "yes" }, malformed: [], missing: null }, tab: "review" };
  const before = structuredClone(value);
  assert.deepEqual(normalizeReader(value, "P2"), { tab: "review", modelDisclosures: { "run.a:proposal.a": { assumptions: true, computation: false, review: true }, "catalog:method.b:2:exact-hash": { assumptions: false, computation: true } } });
  assert.deepEqual(normalizeReader(value, "P1"), {});
  assert.deepEqual(value, before);
  const saved = normalizeNavigation({ contexts: { project: { phase: "P2", p2ProposalKey: "run.a:proposal.a", readers: { P2: value } } } });
  assert.equal(saved.contexts.project.p2ProposalKey, "run.a:proposal.a");
  assert.equal(saved.contexts.project.readers.P2.modelDisclosures["run.a:proposal.a"].assumptions, true);
});
test("exact assessment identity and a bounded disclosure path survive normalization", () => {
  const reference = { role: "theorist", family: "theory_literature", run_id: "run.1", entry_id: "entry.1", entry_sha256: "a".repeat(64), arbitrary: "discard" };
  const reader = normalizeReader({ tab: "papers", query: "mean", entrySelection: { sourceId: "paper.1", reference }, position: { y: 240, offset: -32, anchor: { kind: "data-question-id", value: "question.1" }, disclosures: [{ index: 1, summary: "Saved values" }, null, { index: -1, summary: "invalid" }] } }, "P1");
  assert.equal(reader.entrySelection.reference.entry_sha256, reference.entry_sha256); assert.equal(reader.entrySelection.reference.arbitrary, undefined);
  assert.deepEqual(reader.position.disclosures, [{ index: 1, summary: "Saved values" }]);
  assert.equal(normalizeReader({ tab: "claims", focusQuestion: "transient", query: null }, "P4").tab, undefined);
  assert.equal(normalizeReader({ entrySelection: { sourceId: "legacy.paper", reference: {}, memberKey: "legacy.member" } }, "P1").entrySelection.memberKey, "legacy.member");
  assert.equal(normalizeReader({ position: { anchor: { kind: "data-card-role", value: "research", index: 1 } } }, "P1").position.anchor.index, 1);
});
const table = { page_size: 100, total_rows: 401, next_page_url: `/api/v1/projects/project.a/runs/run.a/outputs/results/table?path=values.csv&sha256=${"a".repeat(64)}&exhibit_id=table.a&offset=100` };
test("a visible sticky Activity anchor cannot replace the scientific reading location", () => {
  const previousWindow = globalThis.window; const previousStyle = globalThis.getComputedStyle;
  globalThis.window = { innerHeight: 700, scrollY: 900 };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  const element = (value, top, toolbar) => ({ isConnected: true, parentElement: null, tagName: "SECTION", getClientRects: () => [{}], closest: (selector) => selector === ".project-toolbar" && toolbar ? {} : null,
    getBoundingClientRect: () => ({ top, bottom: top + 400 }), hasAttribute: (name) => name === "data-reading-anchor", getAttribute: () => value });
  const activity = element("work-activity", 0, true); const scientific = element("main-findings", -20, false);
  const root = { querySelectorAll: (selector) => selector === "details" ? [] : [activity, scientific] };
  try {
    const position = captureReadingPosition(root);
    assert.equal(position.anchor.value, "main-findings"); assert.equal(position.offset, -20); assert.equal(position.y, 900);
  } finally { globalThis.window = previousWindow; globalThis.getComputedStyle = previousStyle; }
});
test("open reading disclosures survive a first Activity panel and a changed status label", () => {
  const detail = (heading, anchor) => ({ open: false, querySelector: () => ({ textContent: heading }), getAttribute: () => anchor });
  const activity = detail("Running Activity", "work-activity"), history = detail("Research history", "research-history"), protocol = detail("Recorded protocol");
  const root = { querySelectorAll: () => [activity, history, protocol] };
  const saved = normalizeReader({ position: { disclosures: [{ index: 0, summary: "Research history", anchor: "research-history" }, { index: 1, summary: "Recorded protocol" }, { index: 0, summary: "Complete Activity", anchor: "work-activity" }] } }, "P4");
  restoreOpenDisclosures(root, saved.position.disclosures);
  assert.ok(history.open); assert.ok(protocol.open); assert.ok(activity.open);
  const duplicate = detail("Recorded protocol"); protocol.open = false;
  restoreOpenDisclosures({ querySelectorAll: () => [activity, protocol, duplicate] }, [{ index: 1, summary: "Recorded protocol" }]);
  assert.equal(protocol.open, false); assert.equal(duplicate.open, false);
});

test("returning to a selected paper restores open sibling and nested disclosures before its reading offset", () => {
  const names = ["window", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  let root; const scrolls = [];
  const element = (anchor, top, parent = null, toolbar = false) => ({
    isConnected: true, parentElement: parent, tagName: "ARTICLE", getClientRects: () => [{}],
    closest: selector => selector === ".project-toolbar" && toolbar ? {} : null,
    getBoundingClientRect: () => ({ top: 1104.5 + top - window.scrollY, bottom: 1504.5 + top - window.scrollY }),
    hasAttribute: name => name === "data-reading-anchor", getAttribute: () => anchor,
  });
  const detail = (anchor, title, top, parent, toolbar = false) => ({ ...element(anchor, top, parent, toolbar), tagName: "DETAILS", open: true,
    querySelector: () => ({ textContent: title, contains: () => false }) });
  const paper = element("paper:mean", -20);
  const activity = detail("work-activity", "Complete Activity", 0, null, true);
  const earlier = detail("legacy-assessment:exact-digest", "Read the earlier member assessment", 80, paper);
  const nested = detail("assessment-evidence:exact-digest", "Evidence locations", 200, earlier);
  const mathematics = detail("paper-math:exact-digest", "Full mathematics and reading basis", 500, paper);
  const closed = detail("closed-history", "Other history", 600, paper); closed.open = false;
  const concealed = detail("concealed-record", "An unavailable reading", 620, closed);
  const details = [activity, earlier, nested, mathematics, closed, concealed];
  root = { querySelector: () => null, querySelectorAll: selector => selector === "details" ? details : [paper, ...details] };
  paper.parentElement = root; activity.parentElement = root;
  globalThis.window = { innerHeight: 700, scrollY: 1104.5, scrollTo: ({ top }) => {
    assert.ok(earlier.open && mathematics.open && nested.open, "Expanded research content must exist before scrolling.");
    scrolls.push(top); window.scrollY = top;
  } };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = callback => { callback(); return 1; };
  globalThis.cancelAnimationFrame = () => {};
  try {
    const saved = normalizeReader({ position: captureReadingPosition(root) }, "P1");
    assert.equal(saved.position.anchor.value, "paper:mean");
    assert.deepEqual(saved.position.disclosures.map(item => item.anchor), [earlier, nested, mathematics].map(item => item.getAttribute("data-reading-anchor")));
    for (const item of details) item.open = false;
    details.unshift(detail("inserted-history", "Other retained history", -100, root));
    window.scrollY = 460.5;
    const cancel = restoreReadingPosition(root, saved.position);
    assert.deepEqual(scrolls, [1104.5]); assert.equal(paper.getBoundingClientRect().top, -20);
    assert.equal(activity.open, false); assert.equal(concealed.open, false); assert.equal(closed.open, false);
    cancel();
  } finally { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } }
});

test("same-day earlier evaluations restore by exact run identity after disclosure insertion", () => {
  const detail = (anchor) => ({ open: false, querySelector: () => ({ textContent: "Earlier evaluation · 2026-10-11" }), getAttribute: () => anchor });
  const earlier = detail("earlier-evaluation:run.a"), selected = detail("earlier-evaluation:run.b"), inserted = detail("work-activity");
  restoreOpenDisclosures({ querySelectorAll: () => [inserted, earlier, selected] }, [{ index: 1, summary: "Earlier evaluation · 2026-10-11", anchor: "earlier-evaluation:run.b" }]);
  assert.equal(selected.open, true); assert.equal(earlier.open, false); assert.equal(inserted.open, false);
});

test("table resume uses the exact current artifact identity and available page size", () => {
  const identity = tablePageIdentity(table);
  assert.ok(identity); assert.equal(new URL(tablePageUrl(identity, 200), "http://local").searchParams.get("offset"), "200");
  assert.equal(tablePageIdentity({ previous_page_url: table.next_page_url.replace("offset=100", "offset=0") }), identity);
  assert.notEqual(tablePageIdentity({ ...table, next_page_url: table.next_page_url.replace("a".repeat(64), "b".repeat(64)) }), identity);
  assert.equal(tablePageIdentity({ next_page_url: "/api/legacy-table?offset=200" }), null);
  assert.equal(tableResumeOffset(table, 300), 300); for (const offset of [-1, 50, 500, null, "200"]) assert.equal(tableResumeOffset(table, offset), 0);
});
