import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { requestSourceReferences } from "../src/contextualRequests.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
const bundle = await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import EmpiricalDocument,{EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx'; export {empiricalSource,empiricalQuestionDestination} from '${src}/components/EmpiricalDocument.jsx'; export {questionSupport,questionSupportSnapshot,QuestionSupportDocument} from '${src}/components/QuestionSupport.jsx'; export const render=(sources,text)=>renderToStaticMarkup(<EmpiricalSourceProvider value={sources}><EmpiricalDocument text={text}/></EmpiricalSourceProvider>); export const renderComponent=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));`, resolveDir: src, loader: "jsx" }, write: false, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const module = { exports: {} };
new Function("require", "module", "exports", bundle.outputFiles[0].text)(require, module, module.exports);
const { empiricalSource, empiricalQuestionDestination, render } = module.exports;
const { questionSupport, questionSupportSnapshot, QuestionSupportDocument, renderComponent } = module.exports;
const source = { branch: "method.a", phase: "P4", family: "attention_items", generation_id: "generation.original", sha256: "a".repeat(64), run_id: "run.original", package_id: "package.original" };
const target = { attention_id: "priority", question: "Which safety question should come next?", reference: { ...source, entry_pointer: "/0" } };
const question = { attention_id: "priority", kind: "researcher_decision", generation_ref: target.reference };
const binding = { uri: "artifact://p4.attention_items", branch: source.branch, producing_run_id: source.run_id, sha256: source.sha256, source_verified: true, generation_ref: source, question_targets: [target] };
const context = { branch: source.branch, files: [binding], decisionQuestions: [question], onDecision() {}, onSource() {} };

test("a priority mention is a keyboard button to the exact unique current question", () => {
  assert.equal(empiricalQuestionDestination(binding.uri, context), question);
  assert.deepEqual(empiricalSource(binding.uri, context), { reference: source });
  const html = render(context, `[Priority inquiry](${binding.uri}).`);
  assert.match(html, /<button[^>]*type="button"[^>]*>[\s\S]*Priority inquiry<\/button>/);
  assert.doesNotMatch(html, /source unavailable/);
});

test("missing, multiple and historical questions keep the exact saved record reader", () => {
  for (const change of [
    { decisionQuestions: [] },
    { decisionQuestions: [{ ...question, generation_ref: { ...source, entry_pointer: "/1" } }] },
    { decisionQuestions: [{ ...question, generation_ref: { ...target.reference, generation_id: "generation.later" } }] },
    { files: [{ ...binding, question_targets: [] }] },
    { files: [{ ...binding, question_targets: [target, { ...target, attention_id: "other" }] }] },
  ]) {
    const sources = { ...context, ...change };
    assert.equal(empiricalQuestionDestination(binding.uri, sources), null);
    assert.deepEqual(empiricalSource(binding.uri, sources), { reference: source });
    assert.match(render(sources, `[Priority inquiry](${binding.uri})`), /data-action="source"/);
  }
});

test("artifact aliases require verified exact bytes and never resolve an arbitrary guessed file", () => {
  for (const change of [{ branch: "method.other" }, { sha256: "f".repeat(64) }, { source_verified: false }, { producing_run_id: "run.other" }]) {
    assert.equal(empiricalSource(binding.uri, { ...context, files: [{ ...binding, ...change }] }), null);
  }
  assert.equal(empiricalSource(binding.uri, { ...context, files: [binding, { ...binding, sha256: "f".repeat(64) }] }), null);
  assert.equal(empiricalSource("artifact://p4.guessed", context), null);
  assert.match(render({ ...context, files: [] }, `[Priority inquiry](${binding.uri})`), /Priority inquiry \(source unavailable\)/);
});

test("decision evidence precedes and distinguishes the original request without changing exact refs", () => {
  const analyst = { ...source, family: "analyst_synthesis", generation_id: "generation.analyst", entry_pointer: "/question_results/1" };
  const theory = { ...source, family: "theory_audit", generation_id: "generation.theory", entry_pointer: "/findings/4" };
  const item = { ...question, scientific_source_refs: [{ label: "Safety calibration", reference: analyst }, { label: "Theory finding", reference: theory }], related_source_refs: [theory] };
  const before = structuredClone(item);
  assert.deepEqual(requestSourceReferences(item), [
    { label: "Safety calibration", reference: analyst }, { label: "Theory finding", reference: theory },
    { label: "Original request", reference: question.generation_ref },
  ]);
  assert.deepEqual(item, before);
});

test("P4 source-only reading counts evidence, the exact original request and citations separately", () => {
  const scientific_source_refs = Array.from({ length: 4 }, (_, index) => ({ label: `Evidence ${index + 1}`,
    reference: { ...source, family: "analyst_synthesis", entry_pointer: `/question_results/${index}` } }));
  const item = { ...question, phase: "P4", scientific_source_refs };
  assert.equal(questionSupport(item, target.question).sizeLabel, "4 scientific sources · original request");
  assert.equal(questionSupport(item, target.question).title, "View scientific sources");
  const citations = ["[Paper A](#cite:paper.a)", "[Paper A again](#cite:paper.a)", "[Paper B](https://example.org/paper-b)"];
  assert.equal(questionSupport(item, target.question, citations).sizeLabel, "4 scientific sources · original request · 2 citations");
  const withoutOriginal = questionSupport({ ...item, generation_ref: undefined }, target.question);
  assert.equal(withoutOriginal.sizeLabel, "4 scientific sources");
});

test("P4 original-only and citation-only readers do not imply scientific evidence is available", () => {
  const item = { ...question, phase: "P4" };
  const support = questionSupport(item, target.question);
  assert.equal(support.sizeLabel, "Original request");
  assert.equal(support.title, "View original request");
  assert.equal(questionSupportSnapshot({ projectId: "project.a", phase: "P4" }, item, target.question, [], () => {}).title, "Original request");
  const html = renderComponent(QuestionSupportDocument, { issue: item, support, onSource() {} });
  assert.match(html, /Original request/);
  assert.doesNotMatch(html, /Read the scientific context|scientific sources/);
  const citationOnly = questionSupport({ ...item, generation_ref: undefined }, target.question, ["[Paper](#cite:paper)"]);
  assert.equal(citationOnly.sizeLabel, "1 citation");
  assert.equal(citationOnly.title, "View citations");
  assert.equal(questionSupport({ ...item, generation_ref: undefined }, target.question).available, false);
  for (const phase of ["P1", "P2", "P3", "P5"]) {
    const unchanged = questionSupport({ ...item, phase }, target.question);
    assert.equal(unchanged.sizeLabel, "1 scientific source");
    assert.equal(unchanged.title, "View scientific sources");
  }
});
