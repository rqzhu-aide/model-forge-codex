import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
const result = await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import EmpiricalDocument,{EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx'; import {ScientificDocuments} from '${src}/components/PhaseReading.jsx'; export {scientificDocumentLink} from '${src}/components/PhaseReading.jsx'; export {empiricalSource} from '${src}/components/EmpiricalDocument.jsx'; export const render=(sources,text)=>renderToStaticMarkup(<EmpiricalSourceProvider value={sources}><EmpiricalDocument text={text}/></EmpiricalSourceProvider>); export const account=doc=>renderToStaticMarkup(<ScientificDocuments documents={[doc]} onSource={()=>{}}/>);`, resolveDir: src, loader: "jsx" }, write: false, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const module = { exports: {} };
new Function("require", "module", "exports", result.outputFiles[0].text)(require, module, module.exports);
const { empiricalSource, render, account, scientificDocumentLink } = module.exports;
const reference = { branch: "method.a", phase: "P4", family: "analyst_synthesis", generation_id: "generation.a", sha256: "a".repeat(64), run_id: "run.a", package_id: "package.a" };
const links = ["tables/return_safety.json", "tables/paired_reward.json", "analysis/summary.json", "metrics_long.jsonl"].map((uri, index) => ({ uri, branch: "method.a", source_verified: true, producing_run_id: "run.a", sha256: "b".repeat(64), artifact_url: `/api/v1/projects/project.a/runs/run.a/outputs/p4.analyst/artifact?path=retained-${index}.json&sha256=${"b".repeat(64)}` }));

test("direct P4 findings open their exact published exhibit from the authored relative table link", () => {
  const exhibit = { ...reference, family: "exhibits", generation_id: "generation.saved-tables", sha256: "c".repeat(64), entry_pointer: "/2" };
  const binding = { ...links[0], exhibit_ref: exhibit };
  const document = { phase: "P4", generation_ref: reference, inline_sources: [binding] };
  const before = structuredClone(document), opened = [];
  const link = scientificDocumentLink(document, value => opened.push(value))(binding.uri, "Accounting");
  assert.deepEqual(link.props.reference, exhibit);
  assert.equal(link.props.label, "Accounting");
  link.type(link.props).props.onClick();
  assert.deepEqual(opened, [exhibit]);
  assert.deepEqual(document, before);
  const fragment = scientificDocumentLink(document)(`${binding.uri}#/rows/0`, "Exact cell");
  assert.equal(fragment.type, "a");
  assert.equal(fragment.props.href, `${binding.artifact_url}#/rows/0`);
  for (const change of [{ branch: "method.other" }, { run_id: "run.later" }, { package_id: "package.later" }, { family: "analyst_synthesis" }, { entry_pointer: "/-1" }]) {
    const other = { ...document, inline_sources: [{ ...binding, exhibit_ref: { ...exhibit, ...change }, artifact_url: undefined }] };
    assert.equal(scientificDocumentLink(other)(binding.uri, "Accounting").type, "span");
  }
  for (const change of [{ source_verified: false }, { source_error: "The saved bytes changed." }]) {
    const unavailable = { ...document, inline_sources: [{ ...binding, ...change }] };
    assert.equal(scientificDocumentLink(unavailable)(binding.uri, "Accounting").type, "span");
  }
});

test("P4 relative citations use only exact verified aliases in exhibits and full Analyst accounts", () => {
  const sources = { branch: "method.a", files: links };
  const text = links.map((link, i) => `[Saved result ${i}](${link.uri})`).join(" ");
  const html = render(sources, text);
  for (const [index, link] of links.entries()) {
    assert.deepEqual(empiricalSource(link.uri, sources), { artifact_url: link.artifact_url });
    assert.match(html, new RegExp(`Saved result ${index}</a>`));
  }
  const document = { kind: "analyst_synthesis", phase: "P4", generation_ref: reference, inline_sources: links, body_md: "Summary fallback only.", structured: { title: "Fresh account", summary_markdown: text, experimental_setting_markdown: "Sixty independent learning datasets with $n=3000$ episodes.", question_results: [{ title: "Count effect", answer_markdown: "The method returned on 60 datasets.", limitations_markdown: "Calibration remains unestablished." }] } };
  const full = account(document);
  assert.match(full, /Experimental setting/);
  assert.match(full, /Sixty independent learning datasets/);
  assert.match(full, /The method returned on 60 datasets\./);
  assert.match(full, /Calibration remains unestablished\./);
  assert.doesNotMatch(full, /Summary fallback only|source unavailable|katex-error|\]\(tables\//);
  for (const [index] of links.entries()) assert.match(full, new RegExp(`Saved result ${index}</a>`));
});

test("relative aliases cannot guess a path, use a foreign binding or make traversal clickable", () => {
  const first = links[0], sources = { branch: "method.a", files: [first] };
  for (const uri of ["return_safety.json", "../tables/return_safety.json", "tables\\return_safety.json", "unknown.json"]) assert.equal(empiricalSource(uri, sources), null);
  for (const changed of [{ source_verified: false }, { branch: "method.other" }, { sha256: undefined }, { producing_run_id: undefined }, { artifact_url: "file:///private" }]) assert.equal(empiricalSource(first.uri, { ...sources, files: [{ ...first, ...changed }] }), null);
  assert.equal(empiricalSource(first.uri, { ...sources, files: [first, { ...first, artifact_url: "/api/other" }] }), null);
  assert.match(render({ branch: "method.a", files: [] }, "[Missing](analysis/summary.json)"), /Missing \(source unavailable\)/);
});
