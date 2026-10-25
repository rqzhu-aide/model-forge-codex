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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-document-spacing-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ResearchDocument, MathText} from '${src}/components/Shared.jsx'; export const document = text => renderToStaticMarkup(<ResearchDocument text={text}/>); export const math = (latex, display = true) => renderToStaticMarkup(<MathText latex={latex} display={display}/>);`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const document = content => `<div class="research-document">${content}</div>`;

test("display equations replace their separator line breaks without extra prose line boxes", () => {
  for (const [open, close] of [["$$", "$$"], ["\\[", "\\]"], ["$", "$"]]) {
    const text = `Before.\n${open}\nx=1\n${close}\nAfter.`;
    const expected = document(`<p>Before.${render.math("\nx=1\n")}After.</p>`);
    assert.equal(render.document(text), expected);
    assert.equal(render.document(text.replaceAll("\n", "\r\n")), expected);
  }
});

test("ordinary prose breaks and paragraph boundaries survive beside display equations", () => {
  const equation = render.math("x=1");
  assert.equal(render.document("First line.\nSecond line.\n$$x=1$$\nThird line.\nFourth line."),
    document(`<p>First line.\nSecond line.${equation}Third line.\nFourth line.</p>`));
  assert.equal(render.document("Before.\n\n$$x=1$$\n\nAfter."),
    document(`<p>Before.</p><p>${equation}</p><p>After.</p>`));
});

test("display equations work between sentences and next to another display equation", () => {
  const first = render.math("x=1"), second = render.math("y=2");
  assert.equal(render.document("Before.$$x=1$$After."), document(`<p>Before.${first}After.</p>`));
  assert.equal(render.document("Before. $$x=1$$ After."), document(`<p>Before. ${first} After.</p>`));
  assert.equal(render.document("$$x=1$$\n$$y=2$$"), document(`<p>${first}${second}</p>`));
});

test("inline math, code and links keep their ordinary line breaks and content", () => {
  assert.equal(render.document("Before.\n$x$\nAfter."),
    document(`<p>Before.\n${render.math("x", false)}\nAfter.</p>`));
  assert.equal(render.document("First.\n`$$x$$`\n[Paper](https://example.test/paper)\nLast."),
    document('<p>First.\n<code>$$x$$</code>\n<a href="https://example.test/paper" target="_blank" rel="noreferrer">Paper</a>\nLast.</p>'));
  assert.equal(render.document("Before.\n$$$$\nAfter."), document("<p>Before.\n$$$$\nAfter.</p>"));
});

test("display-boundary handling also applies inside list items and quoted prose", () => {
  const equation = render.math("x=1");
  assert.equal(render.document("1. Before.\n   $$x=1$$\n   After."),
    document(`<ol start="1"><li value="1"><p>Before.${equation}After.</p></li></ol>`));
  assert.equal(render.document("> Before.\n> $$x=1$$\n> After."),
    document(`<blockquote><p>Before.${equation}After.</p></blockquote>`));
});
