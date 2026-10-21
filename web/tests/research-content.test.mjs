import test from "node:test";
import assert from "node:assert/strict";
import { citationLinks, filterLiterature, readableSections, researchDocumentContent, researchDocumentTitle, retainedReviewNote, selectResearchDocuments, sourceEntry } from "../src/researchContent.js";

test("literature search finds retained sources by author and assessed contribution", () => {
  const sources = [
    { title: "An older source", authors: ["Ada Example"], cards: [{ innovation: "Establishes a fixed point" }] },
    { title: "A recent source", authors: ["Other Author"] },
  ];
  assert.deepEqual(filterLiterature(sources, " ada fixed "), [sources[0]]);
  assert.deepEqual(filterLiterature(sources, "unknown"), []);
  assert.equal(filterLiterature(sources, "").length, 2);
});

test("literature search covers direct mathematical entries and source drilldown keeps exact paper identity", () => {
  const paper = { formulation_markdown: "The discounted Bellman operator", explanation_markdown: "A stationary occupancy measure", topics: ["constrained control"] };
  const source = { title: "Exact paper", cards: [paper] };
  assert.deepEqual(filterLiterature([source], "Bellman occupancy"), [source]);
  assert.deepEqual(filterLiterature([source], "constrained"), [source]);
  const record = { papers: [paper, { explanation_markdown: "Different paper" }] };
  assert.equal(sourceEntry(record, "/papers/0"), paper);
  assert.equal(sourceEntry(record, "/papers/9"), null);
  assert.equal(sourceEntry(record, "/__proto__"), null);
  assert.equal(sourceEntry(record), record);
  const legacy = [{ card_id: "card.one", definition: "Exact first definition" }, { card_id: "card.two", definition: "Second definition" }];
  assert.equal(sourceEntry(legacy, undefined, "card.one"), legacy[0]);
  assert.equal(sourceEntry(legacy, undefined, "card.missing"), null);
});

test("citation links retain trusted identifiers and exclude executable schemes", () => {
  const links = citationLinks({ identifiers: [{ kind: "doi", value: "https://doi.org/10.12345/test" }, { kind: "arxiv", value: "arXiv:2401.01234" }, { kind: "url", value: "javascript:alert(1)" }, { kind: "doi", value: "invalid" }] });
  assert.deepEqual(links, [{ label: "DOI", href: "https://doi.org/10.12345/test" }, { label: "arXiv", href: "https://arxiv.org/abs/2401.01234" }]);
});

test("readable sections select authored findings without reinterpreting internal metadata", () => {
  const sections = readableSections({ record_id: "record.internal", content_sha256: "digest", source_run_id: "run.internal", overall_assessment: "Evidence is incomplete.", prioritized_issues: [{ issue: "The target marginal is unproved.", requested_resolution: "Prove invariance." }], worker_manual: "Run a shell command" });
  assert.deepEqual(sections.map((section) => section.key), ["overall_assessment", "prioritized_issues"]);
});

test("bare math recovery is confined to symbolic definitions in named mathematical fields", () => {
  const formula = { symbol: "\\theta", definition: "\\theta = E[Y]", domain: "Observed outcomes." };
  const source = { target_or_estimand: formula };
  assert.deepEqual(readableSections(source)[0].body, { ...formula, definition: { latex: formula.definition } });
  assert.equal(source.target_or_estimand, formula);
  assert.equal(typeof formula.definition, "string");
  for (const definition of ["Expected outcome.", "The target equals \\theta = E[Y].", "x = 1 is required.", "$$x = 1$$", "\\[x = 1\\]", "`x = 1`", "https://example.test/?x=1"]) {
    const object = { symbol: "x", definition };
    assert.equal(readableSections({ constraints_and_normalization: [object] })[0].body[0], object, definition);
  }
  // Other narrative definitions, even formula-shaped ones, are untouched.
  assert.equal(readableSections({ definition: formula.definition })[0].body, formula.definition);
});

test("exact landscape and correction sources retain authored conditions, changed science and evidence", () => {
  const correction = { correction_id: "internal.id", target: { entry_sha256: "internal.digest" }, reason_markdown: "The source uses expected overrun.", changes: { formulation_markdown: "$E[(C-b)_+]$", assumptions_markdown: "The cost is integrable." }, evidence_locations: ["Equation (3)."] };
  const sections = readableSections(correction);
  assert.deepEqual(sections.map((item) => item.key), ["reason_markdown", "changes", "evidence_locations"]);
  assert.equal(sections.find((item) => item.key === "changes").body, correction.changes);
  assert.deepEqual(readableSections(correction.changes).map((item) => item.key), ["formulation_markdown", "assumptions_markdown"]);
  const comparison = { assumptions_markdown: "Same policy class.", changes_markdown: "Fix the threshold.", consequences_markdown: "The constraint changes.", computational_requirements_markdown: "Requires full trajectories." };
  assert.deepEqual(readableSections(comparison).map((item) => item.body), Object.values(comparison));
});

test("retained review findings are distinct from a new manuscript review verdict", () => {
  const ledger = { branch: "method.a", phase: "P5", kind: "review_issue_ledger", title: "Review issue ledger" };
  const documents = [ledger, { branch: "method.a", phase: "P5", kind: "review_issues" }, { branch: "method.b", phase: "P5", kind: "review_issues" }, { branch: "method.a", phase: "P5", kind: "outside_review" }, { branch: "method.a", phase: "P5", kind: "manuscript" }];
  const selected = selectResearchDocuments(documents);
  assert.equal(selected[0].kind, "manuscript");
  assert.equal(selected.filter((doc) => doc.kind === "review_issues").length, 1);
  assert.ok(selected.includes(ledger));
  assert.ok(selected.some((doc) => doc.kind === "outside_review"));
  assert.equal(researchDocumentTitle(ledger), "Review findings and resolution status");
  assert.match(retainedReviewNote, /earlier manuscript version/);
  assert.match(retainedReviewNote, /does not by itself resolve or reassess/);
  const structured = { issues: [{ issue: "Assumption missing", severity: "major", disposition: "needs_theory", status: "open" }] };
  assert.equal(researchDocumentContent({ ...ledger, body_md: "Partial plain-text projection", structured }), structured);
  assert.equal(researchDocumentContent({ kind: "manuscript", body_md: "Authored manuscript", structured }), "Authored manuscript");
});
