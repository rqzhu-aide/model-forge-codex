import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-compact-evidence-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {DecisionBrief} from '${src}/components/DecisionResponse.jsx'; export {EmpiricalDecisionSummary as Summary} from '${src}/components/EmpiricalQuestion.jsx'; export {CitedRequestDocument,CitedResearchDocument} from '${src}/components/LiteratureCitation.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; export {default as EmpiricalDocument} from '${src}/components/EmpiricalDocument.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree?.props ? text(tree.props.children) : typeof tree === "string" || typeof tree === "number" ? String(tree) : "";
const outsideDetails = html => { let depth = 0; return html.split(/(<\/?details\b[^>]*>)/g).filter(part => { if (/^<details\b/.test(part)) { depth++; return false; } if (/^<\/details/.test(part)) { depth--; return false; } return depth === 0; }).join(""); };

test("decision reading anchors distinguish legacy issues and source revisions", () => {
  const item = { issue_id: "issue.legacy", phase: "P3", branch: "method.a", question: "Which target?", context_markdown: "Preserve the target.", likely_consequence: "The target determines the comparison.", generation_ref: { generation_id: "generation.old" } };
  const anchors = value => nodes(ui.DecisionBrief({ item: value })).filter(node => node.type === "section").map(node => node.props["data-reading-anchor"]);
  assert.deepEqual(anchors({ ...item }), anchors(item));
  assert.ok(anchors(item).length > 0);
  assert.notDeepEqual(anchors({ ...item, issue_id: "issue.other" }), anchors(item));
  assert.notDeepEqual(anchors({ ...item, generation_ref: { generation_id: "generation.new" } }), anchors(item));
});
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "generation.compact", sha256: "a".repeat(64), package_id: "package.compact", run_id: "run.compact" };
const paperRef = { ...ref, phase: "P1", family: "paper_cards", generation_id: "generation.paper", sha256: "b".repeat(64) };
const citation = { source_id: "paper.saved", status: "available", entry_ref: { entry_sha256: "c".repeat(64) }, card: { generation_ref: paperRef, entry_pointer: "/cards/paper.saved" } };
const longAccount = label => `${label}: ${Array.from({ length: 4 }, () => "The retained analysis distinguishes the scientific target from the available evidence and states the conditions under which the comparison can be interpreted.").join(" ")}\n\n$$\n\\begin{aligned}\nJ(\\theta)&=E[L(\\theta)],\\\\\nL(\\theta)&=Q(\\theta)+\\lambda\\|\\theta\\|^2.\n\\end{aligned}\n$$\n\n[Exact paper](#cite:paper.saved). The final caveat for ${label} remains complete.`;

test("complete formulation, consequences and advice remain visible with exact math and citations", () => {
  const item = { attention_id: "question.compact", attention_version_id: "question.compact.v2", response_kind: "choice", context_markdown: longAccount("Affected study"), likely_consequence: longAccount("Consequence"), recommendation: longAccount("Recommendation"), options: [{ id: "keep", label: "Keep the target", consequence: "Retain the saved scientific target." }], citations: [citation], generation_ref: ref };
  const before = structuredClone(item), opened = [], tree = ui.DecisionBrief({ item, onSource: source => opened.push(source) });
  assert.equal(nodes(tree).filter(node => node.type === "details").length, 0);
  const sections = nodes(tree).filter(node => node.type === "section");
  assert.deepEqual(sections.map(node => text(nodes(node).find(child => child.type === "h4"))), ["What this choice changes", "Why your answer matters", "Team recommendation"]);
  assert.equal(new Set(sections.map(node => node.props["data-reading-anchor"])).size, 3);
  const expected = [[item.context_markdown, "context"], [item.likely_consequence, "consequence"], [item.recommendation, "recommendation"]];
  for (const [index, section] of sections.entries()) {
    const doc = nodes(section).find(node => node.type === ui.CitedRequestDocument);
    assert.equal(doc.props.text, expected[index][0]); assert.equal(doc.props.section, expected[index][1]);
    const cited = ui.CitedRequestDocument(doc.props), previous = ui.dispatcher.current;
    let research;
    try { ui.dispatcher.current = { useContext: context => context._currentValue }; research = ui.CitedResearchDocument(cited.props); } finally { ui.dispatcher.current = previous; }
    const link = research.props.renderInternalLink("#cite:paper.saved", "Exact paper", 0);
    assert.ok(link.props.anchor.includes(`request:question.compact.v2:${expected[index][1]}:0`));
    link.props.onOpen(citation, { anchor: link.props.anchor });
  }
  assert.deepEqual(opened, expected.map(() => ({ ...paperRef, entry_pointer: "/cards/paper.saved" })));
  const html = ui.render(ui.DecisionBrief, { item, onSource() {} });
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 3);
  assert.equal((html.match(/class="katex-display"/g) || []).length, 3);
  for (const marker of ["Affected study", "Consequence", "Recommendation"]) assert.ok(html.includes(`The final caveat for ${marker} remains complete.`));
  for (const marker of ["Affected study", "Consequence", "Recommendation"]) assert.ok(outsideDetails(html).includes(`The final caveat for ${marker} remains complete.`));
  assert.doesNotMatch(html, /katex-error|reference unavailable/); assert.deepEqual(item, before);
});

test("concise decision fields and full legacy directions stay visible", () => {
  const item = { attention_id: "question.concise", response_kind: "choice", context_markdown: "The target population is the enrolled cohort.", likely_consequence: "Only the enrolled cohort supports this comparison.", recommendation: "Retain that target.", options: [{ id: "retain", label: "Retain the target", consequence: "Keep the saved scope." }] };
  const html = ui.render(ui.DecisionBrief, { item });
  assert.doesNotMatch(html, /<details/);
  for (const value of [item.context_markdown, item.likely_consequence, item.recommendation]) assert.ok(outsideDetails(html).includes(value));
  const options = longAccount("Legacy directions"), legacy = { attention_id: "question.legacy", options, citations: [citation] };
  const tree = ui.DecisionBrief({ item: legacy, onSource() {} }), section = nodes(tree).find(node => node.type === "section");
  assert.equal(nodes(tree).filter(node => node.type === "details").length, 0);
  assert.equal(text(nodes(section).find(node => node.type === "h4")), "Possible directions");
  assert.equal(nodes(section).find(node => node.type === ui.CitedRequestDocument).props.text, options);
  const rendered = ui.render(ui.DecisionBrief, { item: legacy, onSource() {} });
  assert.match(rendered, /katex-display/); assert.match(rendered, /class="inline-citation"/); assert.match(rendered, /final caveat for Legacy directions remains complete/);
});

test("Summary consolidates each exact authored pointer once without clipping visible findings or full formulation", () => {
  const formulation = "The saved objective uses $J(\\theta)$.\n\n$$J(\\theta)=E[L(\\theta)]+\\lambda\\|\\theta\\|^2.$$\n\nThe complete method qualification remains. [Derivation](https://example.test/derivation).";
  const record = { generation_ref: ref, scientific_outcome: { conclusion: "The recorded contrast is $\\Delta=0$.", scope: "Only the supplied cohort was evaluated." }, decision_summary: { method_formulation_markdown: formulation, implementation_markdown: "The saved solver evaluated the cohort. [Protocol](https://example.test/protocol)." } };
  const before = structuredClone(record), opened = [], tree = ui.Summary({ record, onSource: source => opened.push(source) });
  const sources = nodes(tree).filter(node => node.type === ui.SourceRef);
  const disclosure = nodes(tree).find(node => node.type === "details" && node.props.className === "research-details empirical-summary-sources");
  assert.equal(disclosure.props.open, undefined); assert.equal(text(nodes(disclosure).find(node => node.type === "summary")), "Summary sources");
  assert.deepEqual(sources.map(node => node.props.label), ["Current finding", "Evaluation scope", "Implemented method", "Developed and tested"]);
  assert.deepEqual(nodes(disclosure).filter(node => node.type === ui.SourceRef), sources);
  const pointers = ["/scientific_outcome/conclusion", "/scientific_outcome/scope", "/decision_summary/method_formulation_markdown", "/decision_summary/implementation_markdown"];
  assert.deepEqual(sources.map(node => node.props.reference), pointers.map(entry_pointer => ({ ...ref, entry_pointer })));
  for (const source of sources) ui.SourceRef(source.props).props.onClick();
  assert.deepEqual(opened, pointers.map(entry_pointer => ({ ...ref, entry_pointer })));
  assert.ok(nodes(tree).some(node => node.type === ui.EmpiricalDocument && node.props.text === formulation));
  const html = ui.render(ui.Summary, { record, onSource() {} }), visible = outsideDetails(html);
  for (const value of ["recorded contrast", "Only the supplied cohort", "saved solver"]) assert.ok(visible.includes(value), value);
  assert.doesNotMatch(visible, /complete method qualification|Summary sources|source-link/);
  assert.match(html, /katex-display/); assert.doesNotMatch(html, /katex-error/);
  assert.match(html, /href="https:\/\/example.test\/derivation"/); assert.match(html, /href="https:\/\/example.test\/protocol"/);
  assert.deepEqual(record, before);
});

test("legacy frozen methods retain one precise source even with an objective and no summary paragraph", () => {
  const frozen = { ...ref, phase: "P2", family: "method", generation_id: "generation.frozen", sha256: "d".repeat(64), entry_pointer: "/method/objective_markdown" };
  for (const summary of ["A frozen recap.", undefined]) {
    const record = { decision_summary: {}, evaluated_method: { summary, objective_markdown: "The frozen criterion is $$Q(\\beta)=\\ell(\\beta)+\\lambda\\|\\beta\\|^2.$$. [Full account](https://example.test/frozen).", target_markdown: "The full frozen target remains.", source_ref: frozen } };
    const opened = [], tree = ui.Summary({ record, onSource: source => opened.push(source) }), sources = nodes(tree).filter(node => node.type === ui.SourceRef);
    assert.equal(sources.length, 1); assert.equal(sources[0].props.label, "Evaluated method");
    ui.SourceRef(sources[0].props).props.onClick(); assert.deepEqual(opened, [frozen]);
    const html = ui.render(ui.Summary, { record, onSource() {} });
    for (const value of ["Model formulation and fitting criterion", "katex-display", "full frozen target"]) assert.ok(html.includes(value), value);
    assert.match(html, /href="https:\/\/example.test\/frozen"/); assert.doesNotMatch(html, /No mathematical formulation|katex-error/);
  }
  const missing = ui.render(ui.Summary, { record: { generation_ref: ref, decision_summary: {} } });
  assert.doesNotMatch(missing, /Summary sources/);
});
