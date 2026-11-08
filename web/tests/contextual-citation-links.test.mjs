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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-contextual-links-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {default as Framework,LandscapeRecord} from '${src}/components/FrameworkLandscape.jsx'; export {CitedResearchDocument,LiteratureCitation} from '${src}/components/LiteratureCitation.jsx'; export {default as Claims} from '${src}/components/ClaimTraceability.jsx'; export {default as ReportReading,TechnicalReportDocument,ReportFragmentTarget,ReportInternalLink} from '${src}/components/TechnicalReportReading.jsx'; export {ResearchDocument} from '${src}/components/Shared.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);
function hooks(Component, props) {
  const previous = ui.dispatcher.current;
  try {
    ui.dispatcher.current = { useContext: context => context._currentValue, useId: () => "fixture-id", useState: initial => [initial, () => {}] };
    return Component(props);
  } finally { ui.dispatcher.current = previous; }
}

const basisRef = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "basis.retained", sha256: "a".repeat(64) };
const exactEntry = { role: "theorist", family: "theory_literature", run_id: "run.original", entry_id: "entry.original", entry_sha256: "b".repeat(64) };
const originalCard = { ...exactEntry, explanation_markdown: "The original assessment remains conditional.", generation_ref: { ...basisRef, family: "theory_literature" }, entry_pointer: "/papers/0" };
const citation = { source_id: "source.original", canonical_source_id: "source.canonical", status: "available", entry_ref: exactEntry, card: originalCard, bibliography: { title: "Original cited paper" } };
const record = { framework_id: "framework.conditional", title: "Conditional formulation", formulation_markdown: "The formulation uses $x>0$ [Author](#cite:source.original).", assumptions_markdown: "Positive overlap is assumed [Author](#cite:source.original).", changes_markdown: "Only the threshold changes [Author](#cite:source.original).", explanation_markdown: "The target remains conditional [Author](#cite:source.original).", consequences_markdown: "The boundary remains unresolved [Author](#cite:source.original).", limitations: ["No boundary result was established [Author](#cite:source.original)."], relevance_markdown: "Overlap is required in this setting [Author](#cite:source.original).", computational_requirements_markdown: "The original inputs are required [Author](#cite:source.original)." };
const basis = { generation_ref: basisRef, citations: [citation], landscape: { frameworks: [record] } };
const selection = { kind: "framework", id: record.framework_id, record };

test("all framework accounts render authored citations with the producing basis instead of raw Markdown", () => {
  const before = structuredClone(basis);
  const html = ui.render(ui.Framework, { basis, selectedId: record.framework_id, onOpenCitation() {} });
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 8);
  assert.doesNotMatch(html, /\[Author\]|#cite:/);
  for (const text of ["The target remains conditional", "No boundary result was established", "The original inputs are required"]) assert.ok(html.includes(text));
  assert.match(html, /class="katex"/);
  const framework = hooks(ui.Framework, { basis, selectedId: record.framework_id, onOpenCitation() {} });
  const inspector = find(framework, node => node.type === ui.LandscapeRecord);
  assert.equal(inspector.props.basis, basis);
  assert.equal(typeof inspector.props.onOpenCitation, "function");
  assert.deepEqual(basis, before);
});

test("framework citations preserve their retained historical card and distinct keyboard return anchors", () => {
  const opened = [];
  const tree = ui.LandscapeRecord({ selection, landscape: basis.landscape, basis, onOpenCitation: (...args) => opened.push(args) });
  const accounts = nodes(tree).filter(node => node.type === ui.CitedResearchDocument);
  const anchors = [];
  for (const account of accounts) {
    const document = hooks(account.type, account.props);
    const link = document.props.renderInternalLink("#cite:source.original", "Author", "document.block0.inline1");
    assert.equal(link.type, ui.LiteratureCitation);
    assert.equal(link.props.citation.card, originalCard);
    anchors.push(link.props.anchor);
    const button = find(hooks(link.type, link.props), node => node.type === "button");
    const invoker = { id: account.props.section };
    button.props.onClick({ currentTarget: invoker });
    assert.equal(opened.at(-1)[0].entry_ref.entry_sha256, exactEntry.entry_sha256);
    assert.equal(opened.at(-1)[1].basis, basis);
    assert.equal(opened.at(-1)[1].element, invoker);
  }
  assert.equal(new Set(anchors).size, 8, "Returning to one cited field cannot select another field's citation.");
  assert.ok(anchors.every(anchor => anchor.startsWith("citation:basis.retained:framework:framework:framework.conditional:")));
});

test("a missing exact framework citation stays explicit even when the paper has a different assessment", () => {
  const newer = { ...originalCard, entry_sha256: "c".repeat(64), explanation_markdown: "Today's changed assessment." };
  const source = { source_id: "source.canonical", title: "Current paper", cards: [newer] };
  for (const citations of [[], [{ ...citation, status: "unavailable", card: undefined }]]) {
    const html = ui.render(ui.Framework, { basis: { ...basis, citations }, sources: [source], selectedId: record.framework_id, onOpenCitation() {} });
    assert.equal((html.match(/reference unavailable/g) || []).length, 8);
    assert.doesNotMatch(html, /inline-citation|Today's changed assessment|\[Author\]/);
  }
});

const reportRef = { branch: "method.original", phase: "P5", family: "technical_report", generation_id: "report.original", sha256: "d".repeat(64), run_id: "run.report.original", package_id: "package.report.original" };
const reportClaims = { generation_ref: { ...reportRef, family: "claim_traceability", generation_id: "trace.current" }, report_generation_ref: reportRef, claims: [{ statement_id: "claim.applicability", text: "No supplied observation process verifies the [model premises](#model).", qualification: "Read the [original conditions](#conditions%2Eoriginal)." }] };
const report = { kind: "technical_report", generation_ref: reportRef, body_md: '# Original report\n\n<a id="model"></a>\n## Model\n\nThe retained model remains conditional.' };

test("report claims open their exact historical report and authored fragment while the current report differs", () => {
  const current = { ...report, generation_ref: { ...reportRef, generation_id: "report.current", sha256: "e".repeat(64) }, body_md: report.body_md.replace("Original", "Current") };
  const opened = []; const before = structuredClone(reportClaims);
  const html = ui.render(ui.ReportReading, { documents: [current], traceability: [reportClaims], initialTab: "evidence", onSource: reference => opened.push(reference) });
  assert.match(html, /href="#report-report.original-model">model premises<\/a>/);
  assert.doesNotMatch(html, /\[model premises\]|href="#report-report.current-model"/);
  const tree = ui.Claims({ records: [reportClaims], onSource: reference => opened.push(reference) });
  const accounts = nodes(tree).filter(node => node.type === ui.ResearchDocument && node.props.renderInternalLink);
  const link = accounts[0].props.renderInternalLink("#model", "model premises");
  let prevented = false;
  link.props.onClick({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.deepEqual(opened[0], { ...reportRef, report_fragment: "model" });
  accounts[1].props.renderInternalLink("#conditions%2Eoriginal", "original conditions").props.onClick({ preventDefault() {} });
  assert.deepEqual(opened[1], { ...reportRef, report_fragment: "conditions.original" });
  assert.deepEqual(reportClaims, before);
});

test("unidentified report links do not guess the current report and candidates retain their own source family", () => {
  const missing = { ...reportClaims, report_generation_ref: { generation_id: reportRef.generation_id } };
  const html = ui.render(ui.Claims, { records: [missing], onSource() { throw new Error("No exact source is identified."); } });
  assert.match(html, /model premises \(report source unavailable\)/);
  assert.doesNotMatch(html, /\[model premises\]|href="#report-/);
  const noHandler = ui.render(ui.Claims, { records: [reportClaims] });
  assert.match(noHandler, /report source unavailable/); assert.doesNotMatch(noHandler, /href="#report-/);
  const candidateRef = { ...reportRef, family: "technical_report_candidate" };
  const candidate = { ...reportClaims, report_generation_ref: undefined, generation_ref: candidateRef };
  let opened;
  const account = find(ui.Claims({ records: [candidate], onSource: ref => { opened = ref; } }), node => node.type === ui.ResearchDocument && node.props.renderInternalLink);
  account.props.renderInternalLink("#model", "model premises").props.onClick({ preventDefault() {} });
  assert.deepEqual(opened, { ...candidateRef, report_fragment: "model" });
});

// Commit the target root before exercising the real effect, including rerenders.
function fragmentReader(initialProps, root) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const hooks = {
    useRef: initial => (slots[cursor++] ||= { value: { current: initial } }).value,
    useState(initial) { const at = cursor++; slots[at] ||= { value: initial }; return [slots[at].value, value => { if (slots[at].value !== value) { slots[at].value = value; dirty = true; } }]; },
    useEffect(run, dependencies) { const at = cursor++; if (!slots[at] || dependencies.some((value, offset) => value !== slots[at].dependencies[offset])) { slots[at] = { dependencies }; pending.push(run); } },
  };
  const draw = () => {
    for (let count = 0; dirty && count < 10; count++) {
      cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current;
      try { ui.dispatcher.current = hooks; tree = ui.ReportFragmentTarget(props); } finally { ui.dispatcher.current = previous; }
      tree.ref.current = root; for (const run of pending) run();
    }
    assert.equal(dirty, false); return tree;
  };
  return { draw, update(changes) { props = { ...props, ...changes }; dirty = true; return draw(); } };
}

test("the exact report target receives focus once and polling leaves its reading position alone", () => {
  const calls = [];
  const target = { id: "report-report.original-model", scrollIntoView: options => calls.push(["scroll", options]), focus: options => calls.push(["focus", options]) };
  const root = { querySelectorAll: selector => { assert.equal(selector, ".report-anchor"); return [target, { ...target, id: "report-report.current-model" }]; } };
  const view = fragmentReader({ fragment: "model", generationId: reportRef.generation_id }, root);
  view.draw();
  assert.deepEqual(calls, [["scroll", { block: "start" }], ["focus", { preventScroll: true }]]);
  view.update({ children: "A rerender of the exact same report." });
  assert.equal(calls.length, 2, "Polling and nested source readers cannot replay the explicit report jump.");
  const tree = ui.TechnicalReportDocument({ document: report, fragment: "model" });
  assert.equal(tree.type, ui.ReportFragmentTarget); assert.equal(tree.props.generationId, reportRef.generation_id);
  const html = ui.render(ui.TechnicalReportDocument, { document: report, fragment: "model" });
  assert.match(html, /id="report-report.original-model"[^>]*tabindex="-1"/);
  assert.match(html, /The retained model remains conditional/);
});

test("missing and ambiguous retained report anchors are explicit without focusing a different report", () => {
  const target = { id: "report-report.original-model", scrollIntoView() { throw new Error("No unique target."); }, focus() { throw new Error("No unique target."); } };
  for (const matches of [[], [target, { ...target }], [{ ...target, id: "report-report.current-model" }]]) {
    const view = fragmentReader({ fragment: "model", generationId: reportRef.generation_id }, { querySelectorAll: () => matches });
    const tree = view.draw();
    const status = find(tree, node => node.props.role === "status");
    assert.ok(status);
    assert.match(status.props.children[0], /The linked section is unavailable in this retained report/);
    assert.equal(find(status, node => node.type === "code").props.children, "model");
  }
  const unavailable = fragmentReader({ fragment: "model", generationId: reportRef.generation_id, unavailable: true }, { querySelectorAll() { throw new Error("The report text could not be loaded."); } });
  assert.equal(find(unavailable.draw(), node => node.props.role === "status"), undefined, "A report load error must not also claim its anchor is absent.");
});

function internalLinkReader(props) {
  let missing = false;
  const draw = () => {
    const previous = ui.dispatcher.current;
    try {
      ui.dispatcher.current = { useState: () => [missing, value => { missing = value; }] };
      return ui.ReportInternalLink(props);
    } finally { ui.dispatcher.current = previous; }
  };
  return { draw, update(changes) { props = { ...props, ...changes }; return draw(); }, click(event) { find(draw(), node => node.type === "a").props.onClick(event); return draw(); } };
}

test("internal links in two copies of the same report stay within the activated article", () => {
  const input = { ...report, body_md: `${report.body_md}\n\nRead the [model premises](#model).` };
  const body = find(ui.TechnicalReportDocument({ document: input }), node => node.type === ui.ResearchDocument && node.props.renderInternalLink);
  const link = body.props.renderInternalLink("#model", "model premises");
  assert.equal(link.type, ui.ReportInternalLink);
  const copies = [input, structuredClone(input)].map(document => ui.render(ui.TechnicalReportDocument, { document, showRecordSource: false })).join("");
  assert.equal((copies.match(/id="report-report.original-model"/g) || []).length, 2, "Public authored anchor names remain unchanged in both rendered copies.");
  assert.equal((copies.match(/href="#report-report.original-model"/g) || []).length, 2);
  const calls = [];
  const article = name => {
    const target = { id: link.props.targetId, scrollIntoView: options => calls.push([name, "scroll", options]), focus: options => calls.push([name, "focus", options]) };
    const root = { querySelectorAll: selector => { assert.equal(selector, ".report-anchor"); return [target]; } };
    return { target, invoker: { closest: selector => { assert.equal(selector, ".technical-report"); return root; } } };
  };
  const background = article("background"), dialog = article("dialog");
  const activate = invoker => {
    let prevented = false;
    internalLinkReader(link.props).click({ button: 0, currentTarget: invoker, preventDefault() { prevented = true; } });
    assert.equal(prevented, true);
  };
  activate(dialog.invoker);
  assert.deepEqual(calls, [["dialog", "scroll", { block: "start" }], ["dialog", "focus", { preventScroll: true }]]);
  activate(background.invoker);
  assert.deepEqual(calls.slice(2), [["background", "scroll", { block: "start" }], ["background", "focus", { preventScroll: true }]]);
});

test("report internal links preserve modified activation and expose missing or duplicate local targets", () => {
  const props = { fragment: "model", targetId: "report-report.original-model", label: "model premises" };
  for (const activation of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) {
    const view = internalLinkReader(props);
    let prevented = false;
    const tree = view.click({ button: 0, ...activation, currentTarget: { closest() { throw new Error("Modified activation retains its native link behavior."); } }, preventDefault() { prevented = true; } });
    assert.equal(prevented, false);
    assert.equal(find(tree, node => node.type === "a").props.href, `#${props.targetId}`);
    assert.equal(find(tree, node => node.props.role === "status"), undefined);
  }
  for (const targets of [[], [{ id: props.targetId }, { id: props.targetId }]]) {
    const view = internalLinkReader(props);
    const tree = view.click({ button: 0, currentTarget: { closest: () => ({ querySelectorAll: () => targets }) }, preventDefault() {} });
    const status = find(tree, node => node.props.role === "status");
    assert.ok(status);
    assert.match(status.props.children[0], /The linked section is unavailable in this retained report/);
    assert.equal(find(status, node => node.type === "code").props.children, "model");
    let focused = false;
    const recovered = view.click({ button: 0, currentTarget: { closest: () => ({ querySelectorAll: () => [{ id: props.targetId, scrollIntoView() {}, focus() { focused = true; } }] }) }, preventDefault() {} });
    assert.equal(focused, true);
    assert.equal(find(recovered, node => node.props.role === "status"), undefined);
  }
});

test("an unavailable report-link status stays with the exact target that was activated", () => {
  const view = internalLinkReader({ fragment: "model", targetId: "report-report.original-model", label: "model premises" });
  const missing = () => ({ button: 0, currentTarget: { closest: () => ({ querySelectorAll: () => [] }) }, preventDefault() {} });
  assert.ok(find(view.click(missing()), node => node.props.role === "status"));
  const next = view.update({ fragment: "justification", targetId: "report-report.revised-justification", label: "theoretical result" });
  assert.equal(find(next, node => node.props.role === "status"), undefined, "An old failed target cannot assert that a new report section is unavailable.");
  assert.equal(find(next, node => node.type === "a").props.href, "#report-report.revised-justification");
  const status = find(view.click(missing()), node => node.props.role === "status");
  assert.equal(find(status, node => node.type === "code").props.children, "justification");
});
