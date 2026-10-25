import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { REPORT_SECTION_KEYS, reportSectionHeadings } from "../src/reportSections.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-report-sections-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Reading,{TechnicalReportDocument} from '${src}/components/TechnicalReportReading.jsx'; import {ResearchDocument} from '${src}/components/Shared.jsx'; const draw=C=>props=>renderToStaticMarkup(React.createElement(C,props)); export const document=draw(TechnicalReportDocument),reading=draw(Reading),research=draw(ResearchDocument); export const documentTree=TechnicalReportDocument,researchDocument=ResearchDocument;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.section", phase: "P5", family: "technical_report", generation_id: "report.current", sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report" };
const anchors = Object.fromEntries(REPORT_SECTION_KEYS.map((key) => [key, key.replaceAll("_", "-")]));
const markdown = "# Retained report\n\n## Investigation summary\n\nThe conditional evidence remains limited.\n\n" + REPORT_SECTION_KEYS.map((key) => `<a id="${anchors[key]}"></a>\n## Exact ${key.replaceAll("_", " ")}\n\nAuthored ${key} evidence with $x=1$.`).join("\n\n");
const document = { kind: "technical_report", title: "Retained report", generation_ref: ref, body_md: markdown, section_anchors: anchors, completion: { status: "complete" }, method_identity: { stable_id: "method.section", version: 3 }, portable_artifact_url: "/api/v1/portable" };
const walk = (node) => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];

test("seven authored report sections each expose one compact researcher action with an exact section target", () => {
  const opened = []; const before = structuredClone(document);
  const html = ui.reading({ documents: [document], onDiscussSection: (target) => opened.push(target) });
  assert.equal((html.match(/class="report-section-heading"/g) || []).length, 7);
  assert.equal((html.match(/aria-label="Discuss or comment on /g) || []).length, 7);
  assert.equal((html.match(/report-section-discuss/g) || []).length, 7);
  assert.equal((html.match(/>Retained report<\//g) || []).length, 1);
  assert.match(html, /data-ui-role="research"[^>]*>[\s\S]*?data-icon="ask"/);
  const tree = ui.documentTree({ document, onDiscussSection: (target) => opened.push(target) });
  const renderer = walk(tree).find((node) => node.type === ui.researchDocument && node.props.renderHeading)?.props.renderHeading;
  for (const [headingPath, section] of reportSectionHeadings(markdown, anchors)) {
    const heading = renderer({ level: 4, path: headingPath, children: section.label });
    walk(heading).find((node) => node.props?.className === "report-section-discuss").props.onClick();
  }
  assert.deepEqual(opened, REPORT_SECTION_KEYS.map((object_id) => ({ ...ref, kind: "report_section", object_id, label: `Exact ${object_id.replaceAll("_", " ")}`, assessmentPurpose: "model_dialogue", responsible_role: "research_lead" })));
  assert.deepEqual(document, before);
});

test("only explicit, unambiguous section anchors create actions, including inline and post-heading anchors", () => {
  const source = '```md\n<a id="problem"></a>\n## Fenced heading\n```\n\n<a id="problem"></a>\n## Actual question\n\nAnswer.\n\n## Model <a id="model"></a>\n\nFormulation.\n\n## Justification\n<a id="justification"></a>\n\nArgument.\n\n## Limitations without an anchor';
  const sections = [...reportSectionHeadings(source, anchors).values()];
  assert.deepEqual(sections.map(({ key, label }) => [key, label]), [["problem", "Actual question"], ["model", "Model"], ["justification", "Justification"]]);
  const duplicated = `${source}\n\n<a id="problem"></a>\n## Competing question`;
  assert.ok(![...reportSectionHeadings(duplicated, anchors).values()].some((section) => section.key === "problem"));
  assert.equal(reportSectionHeadings(source, { problem: "problem", model: "problem" }).size, 0);
  assert.equal(reportSectionHeadings({ body: source }, anchors).size, 0);
  assert.equal(reportSectionHeadings(source, null).size, 0);
  const opaque = '$$\n<a id="problem"></a>\n## Equation text\n$$\n\n`<a id="problem"></a>`\n\n<a id="problem"></a>\n## Retained problem\n\n1. Quoted syntax\n   <a id="model"></a>\n   ## Nested heading\n\n> <a id="justification"></a>\n> ## Quoted heading';
  assert.deepEqual([...reportSectionHeadings(opaque, anchors).values()].map(({ key, label }) => [key, label]), [["problem", "Retained problem"]]);
});

test("section affordances preserve one complete Markdown document, display math, nested lists, tables, exhibits and exact links", () => {
  const body = `${markdown}\n\n$$\n\\begin{aligned}\nf(x)&=x^2\\\\\ng(x)&=2x\n\\end{aligned}\n$$\n\n1. First retained step\n   - Nested retained condition $n=90$\n\n| Quantity | Exact value |\n| --- | --- |\n| Estimate | -0.0006028432811984 |\n\n![Retained figure](figure.svg)\n\n[Values](values.csv), [Model](#model), [Paper](https://example.org/paper).`;
  const report_materials = [{ path: "values.csv", artifact_url: "/api/v1/exact-values", source_verified: true, media_type: "text/csv" }, { authored_path: "figure.svg", artifact_url: "/api/v1/exact-figure", source_verified: true, media_type: "image/svg+xml" }];
  const value = { ...document, body_md: body, report_materials }; const before = structuredClone(value);
  const tree = ui.documentTree({ document: value, onDiscussSection: () => {} });
  const authored = walk(tree).filter((node) => node.type === ui.researchDocument && node.props.renderHeading);
  assert.equal(authored.length, 1); assert.equal(authored[0].props.text, body);
  const html = ui.document({ document: value, onDiscussSection: () => {} });
  assert.equal((html.match(/class="katex-display"/g) || []).length, 1);
  assert.match(html, /<ol start="1"><li value="1">[\s\S]*<ul><li><p>Nested retained condition/);
  assert.equal((html.match(/<table>/g) || []).length, 1);
  assert.match(html, /<td>-0\.0006028432811984<\/td>/);
  assert.match(html, /src="\/api\/v1\/exact-figure" alt="Retained figure"/);
  assert.match(html, /href="\/api\/v1\/exact-values"[^>]*>Values<\/a>/);
  assert.match(html, /href="#report-report.current-model">Model<\/a>/);
  assert.match(html, /id="report-report.current-model"/);
  assert.match(html, /href="https:\/\/example.org\/paper"[^>]*>Paper<\/a>/);
  assert.doesNotMatch(html, /katex-error/);
  assert.deepEqual(value, before);
});

test("report tools and source identities collapse while the report and its exact review status remain visible", () => {
  const html = ui.document({ document: { ...document, reviewed_report_ref: { ...ref, sha256: "b".repeat(64) }, review_status: "independently_reviewed" } });
  assert.match(html, /Review concerns an earlier version; this version has not been independently reviewed/);
  assert.match(html, /<details class="research-details report-tools"[^>]*><summary>Report tools<\/summary>[\s\S]*Download offline HTML/);
  assert.match(html, /<details class="research-details report-source-details"[^>]*><summary>Source details<\/summary>[\s\S]*Model version/);
  assert.ok(html.indexOf("</details>", html.indexOf("report-tools")) < html.indexOf("Investigation summary"));
  assert.doesNotMatch(html, /<details[^>]* open/);
  assert.doesNotMatch(html, /report-section-discuss/);
});

test("unknown report versions, historical candidates and document errors do not advertise section discussion", () => {
  const cases = [{ ...document, generation_ref: { ...ref, sha256: null } }, { ...document, generation_ref: { ...ref, family: "manuscript" } }, { ...document, kind: "technical_report_candidate" }, { ...document, document_error: "Retained bytes changed." }];
  for (const value of cases) assert.doesNotMatch(ui.document({ document: value, onDiscussSection: () => {} }), /report-section-discuss/);
  const structured = { ...document, section_anchors: undefined, structured: { section_anchors: anchors } };
  assert.equal((ui.document({ document: structured, onDiscussSection: () => {} }).match(/report-section-discuss/g) || []).length, 7);
});

test("nested examples cannot shadow reserved section or References citation targets", () => {
  const examples = '> <a id="references"></a>\n> A quoted example.\n\n- <a id="problem"></a> A listed example.\n\n';
  const body_md = examples + markdown + '\n\n<a id="references"></a>\n## References\n\n1. <a id="entry-in-list"></a> An ordinary bibliography entry.';
  const html = ui.document({ document: { ...document, body_md, section_anchors: { ...anchors, references: "references" } }, onDiscussSection: () => {} });
  assert.equal((html.match(/id="report-report.current-references"/g) || []).length, 1);
  assert.equal((html.match(/id="report-report.current-problem"/g) || []).length, 1);
  assert.equal((html.match(/report-section-discuss/g) || []).length, 7);
  assert.match(html, /id="report-report.current-entry-in-list"/);
});

test("references have their own visual boundary and exact appendix HTML adds no eighth discussion", () => {
  const value = { ...document, body_md: markdown + '\n\n<a id="references"></a>\n## References\n\nA retained reference.',
    section_anchors: { ...anchors, references: "references" }, report_artifact: { artifact_id: "primary" },
    report_materials: [{ artifact_id: "primary", path: "report.md", source_verified: true, media_type: "text/markdown", artifact_url: "/api/main" },
      { artifact_id: "proofs exact", path: "appendix.md", source_verified: true, media_type: "text/markdown", artifact_url: "/api/proof" }] };
  const html = ui.document({ document: value, onDiscussSection() {} });
  assert.equal((html.match(/report-section-discuss/g) || []).length, 7);
  assert.match(html, /class="report-reference-heading"/);
  assert.match(html, /href="\/api\/v1\/portable\?material_id=proofs%20exact"/);
  assert.doesNotMatch(html, /material_id=primary/);
  assert.match(html, /The proof appendix stays separate from the main account/);
  const malformed = ui.document({ document: { ...value, section_anchors: { ...anchors, references: "absent" } } });
  assert.match(malformed, /References boundary could not be verified/);
  assert.match(malformed, /A retained reference/);
});
