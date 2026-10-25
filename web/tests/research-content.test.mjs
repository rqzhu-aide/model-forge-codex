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

test("typed scope metadata stays out of readable sections while authored scope remains", () => {
  for (const scope of [{ kind: "project" }, { kind: "model", model_ref: { stable_id: "method.fixture", version: 2 } }]) {
    const issue = { scope, context_markdown: "The joint endpoint law is supplied.", question: "What reference regret is identified?", likely_consequence: "The interpretation depends on the measurement law." };
    const before = structuredClone(issue);
    assert.deepEqual(readableSections(issue).map(section => section.key), ["context_markdown", "question", "likely_consequence"]);
    assert.deepEqual(issue, before);
  }
  for (const scope of ["Finite supplied-model scope.", { text: "Conditional on the joint endpoint law." }]) {
    assert.deepEqual(readableSections({ scope }), [{ key: "scope", label: "Scope", body: scope }]);
  }
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

test("declared Analyst JSON presents the whole account without joining informal keys to question IDs", () => {
  const account = { title: "Complete Analyst account", conclusion: "Conditional conclusion.", scope: "Finite law.", conditions: "Synthetic only.", design: "Paired cases.",
    questions: [{ key: "unrelated.informal.key", title: "A complete question", outcome: "mixed", answer_markdown: "$x=1$.", comparison_markdown: "Full comparison.", reliability_markdown: "Reliability.", uncertainty_markdown: "Uncertainty.", limitations_markdown: "Limits.", decision_implication_markdown: "Implication.", next_steps_markdown: "Next check." }],
    implementation_summary: Object.fromEntries(["rule", "correspondence", "environment", "verification", "limitations", "configuration", "choices", "departures"].map(key => [key, `Recorded ${key}.`])) };
  const compact = { question_results: [{ question_id: "exact.structured.question", answer_markdown: "Full Q4." }] };
  const document = { kind: "analyst_synthesis", structured: compact, primary_content: account, primary_source_verified: true, primary_artifact_kind: "json" };
  const before = structuredClone(document);
  const content = researchDocumentContent(document);
  const text = JSON.stringify(content);
  for (const value of [account.conclusion, account.scope, account.conditions, account.design, ...Object.values(account.questions[0]).filter(value => value !== "unrelated.informal.key"), ...Object.values(account.implementation_summary)]) assert.ok(text.includes(value), value);
  assert.doesNotMatch(text, /exact\.structured\.question|unrelated\.informal\.key|Full Q4/);
  assert.deepEqual(document, before);
  assert.equal(researchDocumentContent({ ...document, primary_source_verified: false }), compact);
  assert.equal(researchDocumentContent({ kind: "analyst_synthesis", body_md: "Original Markdown account.", structured: compact }), "Original Markdown account.");
});

test("declared Analyst JSON also presents summary_markdown and question_results accounts", () => {
  const account = { title: "Bounded design account", summary_markdown: "No informative comparison qualified; held-out work remains unassessed.",
    question_results: Array.from({ length: 10 }, (_, index) => ({ question_id: `test.exact.${index}`, title: `Question ${index + 1}`,
      category: "performance", outcome: "not_evaluated", answer_markdown: `Authored answer ${index + 1}: $J(\\pi)$ is conditional.`,
      relevance_markdown: "Why this question matters.", design_markdown: "The declared design.", conditions_markdown: "Synthetic conditions.",
      comparison_markdown: "Separate control comparison.", reliability_markdown: "Recorded reliability.", uncertainty_markdown: "No held-out interval.",
      limitations_markdown: "No human inference.", decision_implication_markdown: "Retain the bounded result.",
      next_steps_markdown: "See [retained source](artifact://artifact.exact).", observed_counts: { planned: 1, completed: 0, failed: 0, not_run: 1 } })) };
  const compact = { question_results: [{ answer_markdown: "Compact answer." }] };
  const document = { kind: "analyst_synthesis", structured: compact, primary_content: account, primary_source_verified: true, primary_artifact_kind: "json" };
  const before = structuredClone(document);
  const content = researchDocumentContent(document);
  assert.equal(content.title, account.title);
  assert.ok(content.body.some(section => section.body === account.summary_markdown));
  const questions = content.body.find(section => section.title === "Empirical questions").body;
  assert.equal(questions.length, 10);
  for (const [index, question] of account.question_results.entries()) {
    assert.equal(questions[index].title, question.title);
    assert.equal(questions[index].state, question.outcome);
    for (const [field, value] of Object.entries(question).filter(([field]) => field.endsWith("_markdown"))) {
      assert.ok(questions[index].body.some(section => section.body === value), field);
    }
  }
  assert.doesNotMatch(JSON.stringify(content), /test\.exact|Compact answer/);
  assert.deepEqual(document, before);
  assert.equal(researchDocumentContent({ ...document, primary_source_verified: false }), compact);
  const dual = { ...document, primary_content: { ...account, questions: [{ title: "Original questions shape", answer_markdown: "Preserve existing precedence." }] } };
  assert.deepEqual(researchDocumentContent(dual).body.find(section => section.title === "Empirical questions").body.map(question => question.title), ["Original questions shape"]);
});
