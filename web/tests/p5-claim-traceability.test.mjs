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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p5-claims-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Claims from '${src}/components/ClaimTraceability.jsx'; import Report, {ReportSupportingDocuments} from '${src}/components/TechnicalReportReading.jsx'; import {ReadingDocumentButton} from '${src}/components/MethodReadingWindow.jsx'; import {ScientificDocuments} from '${src}/components/PhaseReading.jsx'; import {SourceRef} from '${src}/components/Shared.jsx'; export const render=props=>renderToStaticMarkup(React.createElement(Claims,props)); export const report=props=>renderToStaticMarkup(React.createElement(Report,props)); export const tree=Claims; export const sourceRef=SourceRef; export const supporting=ReportSupportingDocuments; export const readingButton=ReadingDocumentButton; export const scientificDocuments=ScientificDocuments; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const reportRef = { branch: "method.srpes", phase: "P5", family: "technical_report", generation_id: "generation.report.final", sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report" };
const traceRef = { ...reportRef, family: "claim_traceability", generation_id: "generation.trace.final" };
const theoryRef = { ...reportRef, phase: "P3", family: "theory_record", generation_id: "generation.theory.frozen", sha256: "b".repeat(64), run_id: "run.theory", package_id: "package.theory" };
const claim = { claim_id: "claim.p5.srpes.identification", statement_id: "claim.p5.srpes.identification", text: "Randomization, if documented, can justify the assignment condition.", anchor: "problem", support_route: "qualified", qualification: "Outcome-regression approximation is additionally needed for SRPES recovery; clinical conditions are unchecked.", evidence_links: [{ relationship: "support", identifier: "/statements/0", label: "/statements/0", generation_ref: theoryRef }] };
const record = { generation_ref: traceRef, report_generation_ref: reportRef, claims: [claim] };
const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];

test("current report claims show authored qualification without an invented finding or internal support-route row", () => {
  const value = structuredClone(record), before = structuredClone(value);
  const html = ui.render({ records: [value], onSource() {} });
  for (const text of ["Report claim 1", claim.text, "Qualification", claim.qualification, "Report source for these claims", "Theoretical account", "Inspect exact source", "Recorded reference", "/statements/0", claim.claim_id]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Manuscript claim|Not assessed|Finding:|no readable research account|Recorded source|Declared support route/);
  assert.deepEqual(value, before);
  const integrated = ui.report({ documents: [{ kind: "technical_report", generation_ref: reportRef }], traceability: [value], initialTab: "evidence", onSource() {} });
  assert.match(integrated, /Report claim 1/);
  assert.ok(integrated.includes(claim.qualification));
  assert.doesNotMatch(integrated, /Not assessed|no readable research account/);
  for (const route of ["model_description", "numerical", "new_formal_result", "established_result", "qualified", "open"]) {
    const classified = ui.render({ records: [{ ...record, claims: [{ ...claim, support_route: route }] }] });
    assert.doesNotMatch(classified, /Not assessed|Finding:|Declared support route|Model description|New formal result|Established result|>Numerical<|>Qualified<|>Open</);
  }
});

test("report, upstream evidence and complete traceability controls open their exact original identities", () => {
  const opened = [], before = structuredClone(record);
  const tree = ui.tree({ records: [record], onSource: source => opened.push(source) });
  for (const node of walk(tree).filter(node => node.type === ui.sourceRef)) ui.sourceRef(node.props).props.onClick();
  assert.deepEqual(opened, [reportRef, theoryRef, traceRef]);
  assert.deepEqual(record, before);
});

test("all current report source families have readable labels without replacing explicit authored descriptions or pointer disclosure", () => {
  const families = { method_catalog: "Model proposals", theory_record: "Theoretical account", analyst_audit: "Analyst assessment", theory_audit: "Theorist assessment", empirical_evidence_index: "Experimental evidence", empirical_synthesis: "Experimental conclusions", implementation_record: "Implementation and checks", evidence: "Experimental observations", diagnostics: "Experimental diagnostics", protocol: "Evaluation protocol", research_basis: "Research setting" };
  const links = Object.keys(families).map((family, index) => ({ relationship: "support", identifier: `/entries/${index}`, label: `/entries/${index}`, generation_ref: { ...theoryRef, family } }));
  links.push({ relationship: "support", identifier: "claim.scoped", label: "Exact authored boundary result", generation_ref: theoryRef });
  links.push({ relationship: "support", identifier: "generation.protocol", label: "protocol", generation_ref: { ...theoryRef, family: "protocol" } });
  const html = ui.render({ records: [{ ...record, claims: [{ ...claim, evidence_links: links }] }] });
  for (const label of [...Object.values(families), "Exact authored boundary result", ...links.map(link => link.identifier)]) assert.ok(html.includes(label), label);
  assert.doesNotMatch(html, />Recorded source</);
});

test("unavailable evidence stays explicit and retains its pointer without a guessed source control", () => {
  const link = { relationship: "support", identifier: "/statements/9", label: "/statements/9", family: "theory_record", source_error: "This exact source is unavailable in the report's retained basis." };
  const html = ui.render({ records: [{ ...record, claims: [{ ...claim, evidence_links: [link] }] }], onSource() {} });
  assert.match(html, /Theoretical account/); assert.match(html, /exact source is unavailable/); assert.match(html, /\/statements\/9/);
  assert.doesNotMatch(html, /Inspect exact source/);
});

test("unresolved claim sources remain visible while source identity stays collapsed", () => {
  const evidenceError = "This exact theory source is unavailable in the retained basis.";
  const locationError = "The declared appendix digest could not be verified.";
  const assessed = { ...claim, evidence_links: [{ relationship: "support", identifier: "/statements/9", label: "/statements/9", family: "theory_record", source_error: evidenceError }], source_links: [{ locator: "appendix/private-location", source_error: locationError }] };
  const html = ui.render({ records: [{ ...record, claims: [assessed] }] });
  const visibleClaim = html.slice(html.indexOf('<article class="traceability-claim'), html.indexOf('<details class="research-details traceability-source-details"'));
  for (const message of [evidenceError, locationError]) {
    assert.ok(visibleClaim.includes(message), message);
    assert.equal(html.split(message).length - 1, 1, "Availability messages appear once.");
  }
  assert.doesNotMatch(visibleClaim, /\/statements\/9|appendix\/private-location|Inspect exact source/);
  assert.match(html, /\/statements\/9/);
  const empty = ui.render({ records: [{ ...record, claims: [{ ...claim, evidence_links: [] }] }] });
  assert.ok(empty.indexOf("No cited source links were recorded") < empty.indexOf('class="research-details traceability-source-details"'));
});

test("authored legacy outcomes and manuscript terminology remain intact, including an explicitly authored not-assessed result", () => {
  const manuscriptRef = { ...reportRef, family: "manuscript" };
  for (const [state, label] of [["partially_supported", "Partly supported"], ["not_assessed", "Not assessed"]]) {
    const legacy = { generation_ref: traceRef, manuscript_generation_ref: manuscriptRef, claims: [{ statement_id: "claim.legacy", text: "A retained manuscript claim.", scientific_outcome: { state, conclusion: "An actual recorded assessment.", scope: "Synthetic data only." } }] };
    const html = ui.render({ records: [legacy], onSource() {} });
    for (const text of ["Manuscript claim 1", "Manuscript for these claims", "A retained manuscript claim", label, "An actual recorded assessment", "Synthetic data only"]) assert.ok(html.includes(text), text);
    assert.doesNotMatch(html, /Report claim|Report source for these claims/);
  }
});

test("compact report claims keep decisive conditions and counterevidence visible while only source controls collapse", () => {
  const assessed = { ...claim, scope: "Adults in the retained trial.", scientific_outcome: {
    state: "partially_supported", conclusion: "Recovery is conditional on the observation process.",
    scope: "No claim about missing outcomes.", assumptions: ["Visits are conditionally independent."],
    strongest_counterevidence_ids: ["evidence.missing-outcomes"], material_disagreement: ["The analyst disputes the missingness assumption."],
  } };
  const html = ui.render({ records: [{ ...record, claims: [assessed] }] });
  const visibleClaim = html.slice(html.indexOf('<article class="traceability-claim'), html.indexOf('<details class="research-details traceability-source-details"'));
  for (const text of [claim.text, claim.qualification, assessed.scope, "Partly supported", assessed.scientific_outcome.conclusion,
    assessed.scientific_outcome.scope, assessed.scientific_outcome.assumptions[0], "Strongest recorded counterevidence", "evidence.missing-outcomes", assessed.scientific_outcome.material_disagreement[0]]) assert.ok(visibleClaim.includes(text), text);
  assert.doesNotMatch(visibleClaim, /<details|Inspect exact source|Recorded reference/);
  assert.match(html, /<h5>Cited source<\/h5>/); assert.doesNotMatch(html, /<h5>Supporting evidence<\/h5>/);
  assert.match(html, /<details class="research-details traceability-source-details"><summary>Sources and claim identity<\/summary>/);
  const fallback = ui.render({ records: [{ ...record, claims: [{ statement_id: "empty" }] }] });
  assert.match(fallback, /A readable statement was not recorded for this claim/);
  assert.match(fallback, /No cited source links were recorded/);
});

test("manuscript relationship labels and any explicit counterevidence roles retain their recorded meanings", () => {
  const links = ["support", "counterevidence", "assumption", "strongest_support", "strongest_counterevidence"].map(relationship => ({ relationship, identifier: relationship, generation_ref: theoryRef }));
  const manuscript = { ...record, report_generation_ref: undefined, manuscript_generation_ref: { ...reportRef, family: "manuscript" }, claims: [{ ...claim, evidence_links: links }] };
  const legacy = ui.render({ records: [manuscript] });
  for (const label of ["Supporting evidence", "Counterevidence", "Assumption", "Strongest supporting evidence", "Strongest counterevidence"]) assert.ok(legacy.includes(`<h5>${label}</h5>`), label);
  const technical = ui.render({ records: [{ ...record, claims: [{ ...claim, evidence_links: links }] }] });
  assert.match(technical, /<h5>Cited source<\/h5>/); assert.match(technical, /<h5>Counterevidence<\/h5>/);
});

test("supporting documents stay complete and open frozen exact-source readers with honest body sizes", () => {
  const documents = [
    { kind: "theory_record", title: "Theoretical account", generation_ref: theoryRef, body_md: "A retained argument.\n\n$$x=1$$" },
    { kind: "empirical_synthesis", title: "Experimental conclusion", generation_ref: { ...theoryRef, phase: "P4", family: "empirical_synthesis", sha256: "c".repeat(64) }, body_md: "A numerical answer." },
    { kind: "protocol", title: "Protocol source", generation_ref: { ...theoryRef, family: "protocol" } },
    { kind: "attachment", title: "Retained PDF", primary_artifact_kind: "pdf", primary_artifact_url: "/api/v1/exact.pdf", generation_ref: theoryRef },
  ];
  const opened = [], scope = { projectId: "project.a", phase: "P5", branch: "method.srpes" };
  const previous = ui.dispatcher.current;
  try {
    ui.dispatcher.current = { useContext: () => ({ scope, open: (snapshot, trigger) => opened.push({ snapshot, trigger }) }) };
    const before = structuredClone(documents);
    const tree = ui.supporting({ documents, onSource() {} });
    const buttons = walk(tree).filter(node => node.type === ui.readingButton);
    assert.deepEqual(buttons.map(node => node.props.title), documents.map(doc => doc.title));
    assert.deepEqual(buttons[0].props.size, { words: 5, equations: 1 });
    assert.equal(buttons[2].props.size, undefined); assert.equal(buttons[3].props.size, undefined);
    const trigger = { id: "theory-source" };
    buttons[0].props.onClick({ currentTarget: trigger });
    assert.equal(opened[0].trigger, trigger); assert.equal(opened[0].snapshot.body.type, ui.scientificDocuments);
    assert.deepEqual(opened[0].snapshot.body.props.documents, [documents[0]]);
    assert.match(opened[0].snapshot.key, /project.a/); assert.match(opened[0].snapshot.key, /P5/); assert.ok(opened[0].snapshot.key.includes(theoryRef.sha256));
    assert.deepEqual(documents, before);
    documents[0].body_md = "A newly published argument.";
    assert.equal(opened[0].snapshot.body.props.documents[0].body_md, before[0].body_md);
    const reopenedList = walk(ui.supporting({ documents })).filter(node => node.type === ui.readingButton);
    assert.equal(reopenedList.length, 4, "Reading a cited source cannot remove it from the complete document list.");
  } finally { ui.dispatcher.current = previous; }
});

test("the document list deduplicates exact source identities while retaining revisions, renditions and claim-cited sources", () => {
  const original = { kind: "theory_record", title: "Claim-cited theoretical account", generation_ref: theoryRef, body_md: "The retained argument." };
  const revised = { ...original, title: "Revised theoretical account", generation_ref: { ...theoryRef, generation_id: "generation.theory.revised", sha256: "c".repeat(64) } };
  const pdf = { ...original, title: "PDF rendition", primary_artifact_kind: "pdf", primary_artifact_url: "/api/v1/exact.pdf", primary_artifact_sha256: "d".repeat(64) };
  const unresolved = { kind: "protocol", title: "Unidentified retained source" };
  const pointed = ["/statements/0", "/statements/1"].map(entry_pointer => ({ ...original, generation_ref: { ...theoryRef, entry_pointer } }));
  const documents = [original, structuredClone(original), revised, pdf, unresolved, structuredClone(unresolved), ...pointed];
  const before = structuredClone(documents);
  const previous = ui.dispatcher.current;
  try {
    ui.dispatcher.current = { useContext: () => ({ scope: { projectId: "p", phase: "P5", branch: theoryRef.branch }, open() {} }) };
    const controls = walk(ui.supporting({ documents })).filter(node => node.type === ui.readingButton);
    assert.equal(controls.length, 7);
    assert.equal(controls.filter(node => node.props.title === original.title).length, 3, "The complete cited document and two distinct exact entries remain available.");
    assert.ok(controls.some(node => node.props.title === revised.title));
    assert.ok(controls.some(node => node.props.title === pdf.title));
    assert.equal(controls.filter(node => node.props.title === unresolved.title).length, 2, "An identical title cannot establish an exact shared source.");
  } finally { ui.dispatcher.current = previous; }
  assert.deepEqual(documents, before);
  const integrated = ui.report({ documents: [{ kind: "technical_report", generation_ref: reportRef }, original, structuredClone(original)], traceability: [record], initialTab: "evidence" });
  assert.equal((integrated.match(/Claim-cited theoretical account/g) || []).length, 1, "A claim citation does not remove its document from the list.");
});
