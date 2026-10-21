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
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Claims from '${src}/components/ClaimTraceability.jsx'; import Report from '${src}/components/TechnicalReportReading.jsx'; import {SourceRef} from '${src}/components/Shared.jsx'; export const render=props=>renderToStaticMarkup(React.createElement(Claims,props)); export const report=props=>renderToStaticMarkup(React.createElement(Report,props)); export const tree=Claims; export const sourceRef=SourceRef;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
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

test("authored legacy outcomes and manuscript terminology remain intact, including an explicitly authored not-assessed result", () => {
  const manuscriptRef = { ...reportRef, family: "manuscript" };
  for (const [state, label] of [["partially_supported", "Partly supported"], ["not_assessed", "Not assessed"]]) {
    const legacy = { generation_ref: traceRef, manuscript_generation_ref: manuscriptRef, claims: [{ statement_id: "claim.legacy", text: "A retained manuscript claim.", scientific_outcome: { state, conclusion: "An actual recorded assessment.", scope: "Synthetic data only." } }] };
    const html = ui.render({ records: [legacy], onSource() {} });
    for (const text of ["Manuscript claim 1", "Manuscript for these claims", "A retained manuscript claim", label, "An actual recorded assessment", "Synthetic data only"]) assert.ok(html.includes(text), text);
    assert.doesNotMatch(html, /Report claim|Report source for these claims/);
  }
});
