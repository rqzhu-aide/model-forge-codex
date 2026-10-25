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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-report-anchor-opacity-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ResearchDocument} from '${src}/components/Shared.jsx'; export const render=text=>renderToStaticMarkup(React.createElement(ResearchDocument,{text,renderAnchor:name=>React.createElement('span',{id:'target-'+name}),renderImage:(source,caption)=>React.createElement('img',{src:'/retained/'+source,alt:caption})}));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("code and math examples do not create an earlier target for a report citation", () => {
  const text = '`<a id="references"></a>`\n\n``An inner ` plus <a id="references"></a>``\n\n'
    + '$\\text{<a id="references"></a>}$\n\n<a id="references"></a>\n## References';
  const html = ui.render(text);
  assert.equal((html.match(/id="target-references"/g) || []).length, 1);
  assert.match(html, /<code>&lt;a id=&quot;references&quot;&gt;&lt;\/a&gt;<\/code>/);
  assert.match(html, /class="katex"/);
  assert.doesNotMatch(html, /katex-error/);
  assert.ok(html.indexOf('id="target-references"') > html.lastIndexOf("class=\"katex\""));
});

test("image examples in code and math do not request retained image bytes", () => {
  const html = ui.render('`![Example](missing.svg)`\n\n$\\text{![Example](missing.svg)}$\n\n![Actual figure](actual.svg)');
  assert.equal((html.match(/<img /g) || []).length, 1);
  assert.match(html, /src="\/retained\/actual.svg"/);
  assert.doesNotMatch(html, /src="\/retained\/missing.svg"/);
});
