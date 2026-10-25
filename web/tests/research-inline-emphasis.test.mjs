import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";

const require = createRequire(import.meta.url);
const katex = require(sharedPackage("katex"));
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-inline-emphasis-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ResearchDocument} from '${src}/components/Shared.jsx'; export const document = text => renderToStaticMarkup(<ResearchDocument text={text}/>);`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle).document;
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const portable = markdown => renderReport(katex, "", { markdown, assets: {} }).html;

for (const [name, draw] of [["UI", ui], ["portable", portable]]) {
  test(`${name} retains bold proof labels around inline statement code`, () => {
    const source = "**Logged likelihood, `statement.fixture.likelihood` (conditional, full).** The main reduction is unchanged.";
    const html = draw(source);
    assert.match(html, /<strong>Logged likelihood, <code>statement\.fixture\.likelihood<\/code> \(conditional, full\)\.<\/strong> The main reduction is unchanged\./);
    assert.doesNotMatch(html, /\*\*/);
  });

  test(`${name} preserves exact math and opaque asterisks inside bold`, () => {
    const html = draw("**Known law $x * y$ and `a ** b`.** Outside.");
    assert.match(html, /<strong>Known law <span class="(?:math-inline|katex)"/);
    assert.match(html, /<annotation encoding="application\/x-tex">x \* y<\/annotation>/);
    assert.match(html, /<code>a \*\* b<\/code>\.<\/strong> Outside\./);
    assert.equal((html.match(/<strong>/g) || []).length, 1);
    assert.doesNotMatch(html, /katex-error/);
  });

  test(`${name} keeps nested links usable and literal code escaped`, () => {
    const html = draw('**[Retained source](https://example.test/paper) and `<script>literal</script>`.**');
    assert.match(html, /<strong><a href="https:\/\/example\.test\/paper"[^>]*>Retained source<\/a> and <code>&lt;script&gt;literal&lt;\/script&gt;<\/code>\.<\/strong>/);
    assert.doesNotMatch(html, /<script>/);
  });

  test(`${name} does not let a code dollar hide the surrounding bold boundary`, () => {
    const html = draw("**Code `$unfinished` and $x$.** After.");
    assert.match(html, /<strong>Code <code>\$unfinished<\/code> and /);
    assert.match(html, /<annotation encoding="application\/x-tex">x<\/annotation>/);
    assert.match(html, /\.<\/strong> After\./);
    assert.doesNotMatch(html, /\*\*|katex-error/);
  });

  test(`${name} does not reinterpret bold markers inside standalone code or mathematics`, () => {
    const html = draw('`**literal**` and $\\text{**literal**}$; **unfinished.');
    assert.match(html, /<code>\*\*literal\*\*<\/code>/);
    assert.match(html, /<annotation encoding="application\/x-tex">\\text\{\*\*literal\*\*\}<\/annotation>/);
    assert.match(html, /; \*\*unfinished\./);
    assert.doesNotMatch(html, /<strong>|katex-error/);
  });
}
