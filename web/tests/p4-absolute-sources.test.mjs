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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-absolute-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import EmpiricalDocument,{EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx'; export {empiricalSource} from '${src}/components/EmpiricalDocument.jsx'; export const render = (sources,text) => renderToStaticMarkup(React.createElement(EmpiricalSourceProvider,{value:{...sources,onSource:()=>{}}},React.createElement(EmpiricalDocument,{text})));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const { empiricalSource, render } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

const uri = "C:/Users/researcher/research/projects/project.a/runs/run.a/outputs/p4.analyst/exhibit-artifacts/retained-safety.json";
const file = { uri, branch: "method.a", sha256: "a".repeat(64), producing_run_id: "run.a", source_verified: true, artifact_url: "/api/v1/projects/project.a/runs/run.a/outputs/p4.analyst/artifact?path=exhibit-artifacts%2Fretained-safety.json&sha256=" + "a".repeat(64) };

test("absolute markdown locators use only exact backend-verified bindings and preserve labels and math", () => {
  const sources = { branch: "method.a", files: [file] };
  const text = `Unsafe returns were 0/60. [Policy return and safety table](<${uri}#counts>) with $\\delta=0.05$.`;
  const before = JSON.stringify(sources);
  const html = render(sources, text);
  assert.deepEqual(empiricalSource(`${uri}#counts`, sources), { artifact_url: file.artifact_url + "#counts" });
  assert.match(html, /href="\/api\/v1\/projects\/project.a\/runs\/run.a\/outputs\/p4.analyst\/artifact\?/);
  assert.match(html, /Policy return and safety table<\/a>/);
  assert.match(html, /Unsafe returns were 0\/60\./);
  assert.match(html, /class="katex"/);
  assert.doesNotMatch(html, /C:\/Users|source unavailable|katex-error/);
  assert.equal(JSON.stringify(sources), before);
});

test("unverified, foreign, changed, ambiguous and same-basename paths cannot become links", () => {
  for (const change of [{ source_verified: false }, { source_error: "Changed bytes" }, { branch: "method.other" },
    { sha256: undefined }, { producing_run_id: undefined }, { uri: uri.replace("run.a/", "run.other/") },
    { artifact_url: "file:///private" }]) {
    assert.equal(empiricalSource(uri, { branch: "method.a", files: [{ ...file, ...change }] }), null);
  }
  assert.equal(empiricalSource(uri, { branch: "method.a", artifacts: [file] }), null);
  assert.equal(empiricalSource(uri, { branch: "method.a", files: [file, { ...file, sha256: "b".repeat(64) }] }), null);
  const html = render({ branch: "method.a", files: [] }, `[Policy table](<${uri}>)`);
  assert.match(html, /Policy table \(source unavailable\)/);
  assert.doesNotMatch(html, /C:\/Users|href=/);
});

test("absolute frozen record preserves its exact source reference and pointer while API links stay usable", () => {
  const reference = { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "generation.frozen", sha256: file.sha256, run_id: "run.p2.origin", package_id: "package.origin" };
  const frozen = { ...file, uri: uri.replace("outputs/p4.analyst/exhibit-artifacts/retained-safety.json", "inputs/trunk/p2/method_catalog/generation.frozen.json"), producing_run_id: reference.run_id, artifact_url: undefined, generation_ref: reference };
  const sources = { branch: "method.a", files: [frozen] };
  assert.deepEqual(empiricalSource(`${frozen.uri}#/methods/0`, sources), { reference: { ...reference, entry_pointer: "/methods/0" } });
  assert.equal(empiricalSource(frozen.uri, { ...sources, files: [{ ...frozen, generation_ref: { ...reference, sha256: "b".repeat(64) } }] }), null);
  const html = render(sources, `[Frozen method](<${frozen.uri}#/methods/0>) and [Download](/api/v1/download).`);
  assert.match(html, /<button[^>]*class="source-link[^>]*>[\s\S]*?Frozen method<\/button>/);
  assert.match(html, /href="\/api\/v1\/download"/);
  assert.doesNotMatch(html, /source unavailable|C:\/Users/);
});
