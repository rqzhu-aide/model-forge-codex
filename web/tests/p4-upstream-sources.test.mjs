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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-upstream-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import EmpiricalDocument,{EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx'; export {empiricalSource} from '${src}/components/EmpiricalDocument.jsx'; export const render = (sources,text) => renderToStaticMarkup(React.createElement(EmpiricalSourceProvider,{value:{...sources,onSource:()=>{}}},React.createElement(EmpiricalDocument,{text})));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const { empiricalSource, render } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

const reference = { branch: "trunk", phase: "P2", family: "lead_proposal", generation_id: "generation.frozen", sha256: "a".repeat(64), run_id: "run.p2.origin", package_id: "package.origin", stage_id: "p2.independent_proposals" };
const uri = `run://${reference.run_id}/p2.lead_proposal`;
const binding = { uri, branch: "method.a", sha256: reference.sha256, producing_run_id: reference.run_id, source_verified: true, generation_ref: reference };

test("P4 uses the exact frozen upstream generation and fragment, including shared P2 provenance", () => {
  const sources = { branch: "method.a", files: [binding] };
  const fragment = "/method/mathematical_definition/canonical_definition";
  assert.deepEqual(empiricalSource(`${uri}#${fragment}`, sources), { reference: { ...reference, entry_pointer: fragment } });
  const html = render(sources, `[Frozen v2 definition](${uri}#${fragment})`);
  assert.match(html, /Frozen v2 definition/);
  assert.doesNotMatch(html, /source unavailable/);
  const theory = { ...reference, branch: "method.a", phase: "P3", family: "complete_theory", run_id: "run.p3.origin" };
  const theoryUri = `run://${theory.run_id}/p3.lead/complete_theory.json`;
  assert.deepEqual(empiricalSource(theoryUri, { branch: "method.a", files: [{ ...binding, uri: theoryUri, generation_ref: theory }] }), { reference: theory });
});

test("P4 rejects unverified, changed, foreign, ambiguous or unbound upstream targets", () => {
  for (const changed of [
    { source_verified: false }, { source_error: "Changed snapshot" }, { branch: "method.other" },
    { generation_ref: { ...reference, run_id: "run.other" } },
    { generation_ref: { ...reference, sha256: "b".repeat(64) } },
    { uri: `run://${reference.run_id}/p2.other` },
  ]) assert.equal(empiricalSource(uri, { branch: "method.a", files: [{ ...binding, ...changed }] }), null);
  assert.equal(empiricalSource(uri, { branch: "method.other", files: [binding] }), null);
  assert.equal(empiricalSource(uri, { branch: "method.a", files: [binding, { ...binding, generation_ref: { ...reference, generation_id: "generation.other" } }] }), null);
  const html = render({ branch: "method.a", files: [] }, `[Missing upstream](${uri})`);
  assert.match(html, /Missing upstream \(source unavailable\)/);
});
