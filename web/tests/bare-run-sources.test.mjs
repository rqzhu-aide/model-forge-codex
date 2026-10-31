import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { bareRunSourceParts } from "../src/researchSourceLinks.js";

const uri = "run://run.original/p4.exhibits/table_safety.csv";
const second = "run://run.original/p4.audit/theory.md";

test("bare run locators preserve sentence punctuation, balanced paths, fragments and repetitions", () => {
  for (const [text, expected] of [
    [`Sources: ${uri}, ${second}.`, [uri, second]],
    [`(${uri}); ${second}#/findings/2!`, [uri, `${second}#/findings/2`]],
    [`${uri} ${uri}`, [uri, uri]],
    ["run://run.original/path(a).md.", ["run://run.original/path(a).md"]],
  ]) {
    const parts = bareRunSourceParts(text);
    assert.equal(parts.map((part) => part.text).join(""), text);
    assert.deepEqual(parts.filter((part) => part.source).map((part) => part.source), expected);
  }
});

test("embedded URLs, local paths, escaped locators and other schemes remain literal", () => {
  for (const text of [
    `https://example.test/?target=${uri}`, `file:///example/${uri}`,
    `C:\\${uri}`, `\\${uri}`, `<${uri}>`, `prefix${uri}`,
    "javascript:alert(1) C:/private/file.md artifact://record RUN://run.original/path.md",
  ]) {
    assert.deepEqual(bareRunSourceParts(text), [{ text }]);
  }
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-bare-run-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server';
    import {ResearchDocument} from '${src}/components/Shared.jsx';
    import EmpiricalDocument,{EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx';
    export {empiricalSource,empiricalSourceLabel} from '${src}/components/EmpiricalDocument.jsx';
    export const renderProse = (text,enabled=true) => { const calls=[]; const renderSourceLink=enabled?(uri,label,path,options)=>{calls.push({uri,label,options});return React.createElement('button',{'data-source':uri},label);}:undefined; return {html:renderToStaticMarkup(React.createElement(ResearchDocument,{text,renderSourceLink})),calls}; };
    export const render = (sources,text) => {let opens=0;return {html:renderToStaticMarkup(React.createElement(EmpiricalSourceProvider,{value:{...sources,onSource:()=>opens++}},React.createElement(EmpiricalDocument,{text}))),opens};};`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const { renderProse, render, empiricalSource } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("only prose reaches the resolver; code, math and existing Markdown keep their paths", () => {
  const text = `Visible ${uri}.\n\n\`${uri}\` and $\\text{${second}}$.\n\n> \`\`\`md\n> ${uri}\n> \`\`\`\`\n\n- > ~~~md\n  > ${uri}\n  > ~~~~\n\n[Authored label](${second})`;
  const result = renderProse(text);
  assert.deepEqual(result.calls.map((call) => [call.uri, call.options?.bare || false]), [[uri, true], [second, false]]);
  assert.match(result.html, /<code>run:\/\/run.original\/p4.exhibits\/table_safety.csv<\/code>/);
  assert.doesNotMatch(result.html, /katex-error/);
  assert.match(result.html, />Authored label<\/button>/);
  assert.equal(renderProse(text, false).calls.length, 0);
});

test("unclosed code and Markdown label/destination examples do not gain bare citations", () => {
  for (const text of [
    `> \`\`\`md\n> ${uri}`, `- \`\`\`md\n  ${uri}`,
    `[${uri}](https://example.test/exact)`, `![example](${uri})`,
  ]) assert.equal(renderProse(text).calls.filter((call) => call.options?.bare).length, 0);
});

const ref = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "generation.original", sha256: "a".repeat(64), run_id: "run.original", package_id: "package.original", stage_id: "p4.analyst" };
const file = { uri, sha256: "b".repeat(64), branch: ref.branch, producing_run_id: ref.run_id, source_verified: true, artifact_url: `/api/retained/original?sha256=${"b".repeat(64)}`, title: "Recorded patient safety" };

test("bare verified files use their exact title/URL without automatic navigation", () => {
  const sources = { branch: ref.branch, files: [file] };
  const { html, opens } = render(sources, `Sources: ${uri}, ${uri}.`);
  assert.equal(opens, 0);
  assert.equal((html.match(/>Recorded patient safety<\/a>/g) || []).length, 2);
  assert.equal((html.match(/href="\/api\/retained\/original\?sha256=/g) || []).length, 2);
  assert.match(html, /<\/a>, /); assert.match(html, /<\/a>\.<\/p>/);
  assert.match(html, /title="run:\/\/run.original\/p4.exhibits\/table_safety.csv"/);
  assert.match(render(sources, `[Preserve authored label](${uri})`).html, />Preserve authored label<\/a>/);
});

test("exact generations keep the existing source button and fragment", () => {
  const generationFile = { ...file, sha256: ref.sha256, generation_ref: ref, artifact_url: undefined };
  const sources = { branch: ref.branch, files: [generationFile] };
  const source = `${uri}#/claim`;
  assert.deepEqual(empiricalSource(source, sources), { reference: { ...ref, entry_pointer: "/claim" } });
  const result = render(sources, source);
  assert.equal(result.opens, 0);
  assert.match(result.html, /<button[^>]+>.*Recorded patient safety<\/button>/);
  assert.doesNotMatch(result.html, /source unavailable|href=/);
});

test("absent, ambiguous or unverified bindings stay readable and never inherit a current filename match", () => {
  for (const files of [
    [], [{ ...file, source_verified: false }], [{ ...file, source_error: "Changed bytes" }],
    [file, { ...file, sha256: "c".repeat(64) }],
    [{ ...file, uri: uri.replace("run.original", "run.newer") }],
  ]) {
    const result = render({ branch: ref.branch, files }, uri);
    assert.equal(result.opens, 0);
    assert.match(result.html, />table_safety.csv \(source unavailable\)<\/span>/);
    assert.match(result.html, /title="run:\/\/run.original\/p4.exhibits\/table_safety.csv"/);
    assert.doesNotMatch(result.html, /<a |<button/);
  }
});
