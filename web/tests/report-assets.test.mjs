import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { reportAssetInput } from "../scripts/report-assets.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const descriptor = (name, bytes, media_type) => ({ path: path.resolve(name), sha256: digest(bytes), media_type });

test("rendered references read exact bytes once per file/media while unreferenced large logs stay unread", () => {
  const code = Buffer.from([0, 255, 65, 10]);
  const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Exact figure</text></svg>');
  const source = descriptor("retained-source.bin", code, "application/octet-stream");
  const image = descriptor("retained-figure.svg", svg, "image/svg+xml");
  // No giant fixture is needed: reading this sentinel fails regardless of its
  // represented size, proving that aliases do not trigger eager file reads.
  const huge = { path: path.resolve("unreferenced-95MB-per-fit-log.json"), media_type: "application/json", sha256: "a".repeat(64) };
  const reads = [];
  const input = {
    markdown: "Inline $x^2$.\n\n[Source](source.bin) [Alias](artifact://source)\n\n![Figure](figure.svg)\n\n"
      + "[Local logs](http://127.0.0.1:8766/api/log?sha256=exact&path=deep) [Web](https://example.org/evidence?q=1&v=2)\n\n"
      + "`[Not a rendered link](deep.json)`\n\n```text\n[Example link](deep.json)\n![Example image](deep.json)\n```",
    asset_files: { "source.bin": source, "artifact://source": source, "figure.svg": image,
      "deep.json": huge, "artifact://deep": huge, "artifact.deep": huge },
  };
  const original = JSON.stringify(input);
  const prepared = reportAssetInput(input, filename => {
    reads.push(filename);
    if (filename === source.path) return code;
    if (filename === image.path) return svg;
    throw new Error("An unreferenced large source was read");
  });
  const html = renderReport(katex, "", prepared).html;
  assert.deepEqual(reads, [source.path, image.path]);
  assert.equal((html.match(/data:application\/octet-stream;base64,AP9BCg==/g) || []).length, 2);
  assert.ok(html.includes(`data:image/svg+xml;base64,${svg.toString("base64")}`));
  assert.match(html, /class="katex"/);
  assert.match(html, /href="http:\/\/127\.0\.0\.1:8766\/api\/log\?sha256=exact&amp;path=deep"/);
  assert.match(html, /href="https:\/\/example\.org\/evidence\?q=1&amp;v=2"/);
  assert.match(html, /<code>\[Not a rendered link\]\(deep\.json\)<\/code>/);
  assert.match(html, /<pre><code>\[Example link\]\(deep\.json\)/);
  assert.equal(JSON.stringify(input), original);
  assert.equal(prepared.assets.toString, undefined);
});

test("lazy file reads recheck the exact digest and reject conflicting alias metadata", () => {
  const bytes = Buffer.from("retained result\n");
  const source = descriptor("result.txt", bytes, "text/plain");
  const changed = reportAssetInput({ asset_files: { source } }, () => Buffer.from("changed result\n"));
  assert.throws(() => changed.assets.source, /changed after source verification/);

  let reads = 0;
  const prepared = reportAssetInput({ asset_files: { source, conflict: { ...source, sha256: "b".repeat(64) } } }, () => {
    reads += 1;
    return bytes;
  });
  assert.equal(prepared.assets.source, `data:text/plain;base64,${bytes.toString("base64")}`);
  assert.throws(() => prepared.assets.conflict, /conflicting retained digests/);
  assert.equal(reads, 1);
});

test("referenced missing files fail and retained file descriptors require absolute paths", () => {
  const source = descriptor("missing-result.json", Buffer.from("{}"), "application/json");
  const missing = reportAssetInput({ asset_files: { source } }, () => { throw new Error("ENOENT: missing retained source"); });
  assert.throws(() => missing.assets.source, /ENOENT/);
  const relative = reportAssetInput({ asset_files: { source: { ...source, path: "relative.json" } } }, () => {
    throw new Error("An invalid path was read");
  });
  assert.throws(() => relative.assets.source, /invalid retained file metadata/);
});

test("a cached file keeps distinct declared media types and supports existing inline assets", () => {
  const bytes = Buffer.from("same bytes");
  const source = descriptor("source.dat", bytes, "text/plain");
  let reads = 0;
  const prepared = reportAssetInput({ asset_files: { text: source, binary: { ...source, media_type: "application/octet-stream" } },
    assets: { legacy: "data:text/plain;base64,YQ==" } }, () => { reads += 1; return bytes; });
  assert.match(prepared.assets.text, /^data:text\/plain;base64,/);
  assert.match(prepared.assets.binary, /^data:application\/octet-stream;base64,/);
  assert.equal(prepared.assets.legacy, "data:text/plain;base64,YQ==");
  assert.equal(reads, 2);
});

test("Markdown support renders math and exact fragment links offline, including nested files and cycles", () => {
  const support = Buffer.from('<a id="model"></a>\n## Model\n\n$S(t)=\\exp(-t)$. [Back](../report.md#problem) [Theory](theory.md#model) [Again](#model)\n\n![Evidence](figure.svg)');
  const theory = Buffer.from('<a id="model"></a>\n## Theory\n\n[Return](support.md#model)');
  const figure = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Exact</text></svg>');
  const descriptors = {
    'details/support.md': descriptor('support.md', support, 'text/markdown'),
    'details/theory.md': descriptor('theory.md', theory, 'text/markdown'),
    'details/figure.svg': descriptor('figure.svg', figure, 'image/svg+xml'),
  };
  const bytes = new Map([[descriptors['details/support.md'].path, support], [descriptors['details/theory.md'].path, theory], [descriptors['details/figure.svg'].path, figure]]);
  const reads = [];
  const input = reportAssetInput({
    markdown: '<a id="problem"></a>\n# Main\n\n[Definition](details/support.md#model)',
    primary_paths: ['report.md'], asset_files: descriptors,
  }, filename => { reads.push(filename); return bytes.get(filename); });
  const html = renderReport(katex, '', input).html;
  assert.match(html, /href="#report-support-1-model"/);
  assert.match(html, /id="report-support-1-model"/);
  assert.match(html, /href="#report-support-2-model"/);
  assert.match(html, /id="report-support-2-model"/);
  assert.match(html, /href="#problem"/);
  assert.match(html, /class="katex"/);
  assert.match(html, /data:image\/svg\+xml;base64,/);
  assert.equal((html.match(/class="report-supplement"/g) || []).length, 2);
  assert.equal(reads.length, 3);
  assert.doesNotMatch(html, /data:text\/markdown/);
});

test("support math is validated and a missing fragment-bearing file is not invented", () => {
  const bytes = Buffer.from('Invalid $\\notARealCommand{x}$.');
  const source = descriptor('support.md', bytes, 'text/markdown');
  const prepared = reportAssetInput({ markdown: '[Support](support.md#model)', asset_files: { 'support.md': source } }, () => bytes);
  assert.throws(() => renderReport(katex, '', prepared), /report support support.md/);
  assert.throws(() => renderReport(katex, '', { markdown: '[Missing](missing.md#model)', assets: {} }), /no portable target/);
});

test("exact Markdown print scopes exclude other support while all linked documents remain readable offline", () => {
  const appendix = Buffer.from('<a id="proof"></a>\n# Proof appendix\n\n$X=1$. [Main](../report.md#problem) [Other](other.md#notes)');
  const other = Buffer.from('<a id="notes"></a>\n# Supporting notes\n\nRetained notes.');
  const selected = { ...descriptor("appendix.md", appendix, "text/markdown"), artifact_id: "artifact.appendix" };
  const notes = { ...descriptor("other.md", other, "text/markdown"), artifact_id: "artifact.notes" };
  const input = { markdown: '<a id="problem"></a>\n# Main report\n\n[Proof](details/appendix.md#proof)',
    primary_paths: ["report.md"], print_material_id: "artifact.appendix",
    asset_files: { "details/appendix.md": selected, "artifact.appendix": selected, "details/other.md": notes } };
  const original = JSON.stringify(input); const reads = [];
  const rendered = renderReport(katex, "", reportAssetInput(input, filename => {
    reads.push(filename); return filename === selected.path ? appendix : other;
  }));
  assert.equal(reads.length, 2);
  assert.match(rendered.html, /id="report-support-1-print" checked/);
  assert.match(rendered.html, /id="report-print-main"><label/);
  assert.match(rendered.html, /href="#report-support-1-proof"/);
  assert.match(rendered.html, /href="#report-support-2-notes"/);
  assert.match(rendered.html, /href="#problem"/);
  assert.match(rendered.html, /id="report-support-1-document" data-report-material="artifact.appendix"/);
  assert.equal((rendered.html.match(/class="report-supplement"/g) || []).length, 2);
  assert.match(rendered.html, /class="katex"/);
  assert.match(rendered.print_css, /\.report-supplement\{display:none!important\}/);
  assert.match(rendered.print_css, /#report-support-1-print:checked~\.report-primary\{display:none!important\}/);
  assert.match(rendered.print_css, /#report-support-1-print:checked~#report-support-1-document\{display:block!important/);
  assert.equal(rendered.print_scopes.find(scope => scope.material_id === "artifact.appendix").region_id, "report-support-1-document");
  assert.equal(JSON.stringify(input), original);
});

test("a selected declared appendix renders even when the primary report has no appendix link", () => {
  const bytes = Buffer.from("# Submitted appendix\n\nExact retained proof.");
  const file = { ...descriptor("appendix.md", bytes, "text/markdown"), artifact_id: "artifact.appendix" };
  const rendered = renderReport(katex, "", reportAssetInput({ markdown: "# Main report", print_material_id: "artifact.appendix", asset_files: { "appendix.md": file } }, () => bytes));
  assert.match(rendered.html, /Submitted appendix/);
  assert.match(rendered.html, /id="report-support-1-print" checked/);
});

test("print material selection requires one exact submitted Markdown artifact identity", () => {
  const bytes = Buffer.from("# Appendix");
  const file = { ...descriptor("appendix.md", bytes, "text/markdown"), artifact_id: "artifact.appendix" };
  const prepare = (changes) => reportAssetInput({ print_material_id: "artifact.appendix", asset_files: { "appendix.md": file }, ...changes }, () => bytes);
  assert.throws(() => prepare({ print_material_id: "appendix.md" }), /not a declared report artifact/);
  assert.throws(() => prepare({ print_material_id: "" }), /exact submitted Markdown artifact/);
  assert.throws(() => prepare({ primary_paths: ["appendix.md"] }), /rather than the primary report/);
  assert.throws(() => prepare({ asset_files: { one: file, two: { ...file, path: path.resolve("other.md") } } }), /ambiguous retained source/);
  assert.throws(() => prepare({ asset_files: { "source.csv": { ...descriptor("source.csv", bytes, "text/csv"), artifact_id: "artifact.appendix" } } }), /not a retained Markdown/);
});

test("artifact-ID appendix links retain the canonical authored base for nested relative assets", () => {
  const appendix = Buffer.from('# Proof\n\n![Nested retained figure](figure.svg) [Notes](notes.md#entry)');
  const notes = Buffer.from('<a id="entry"></a>\n# Notes\n\n[Return](appendix.md)');
  const image = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Nested exact image</text></svg>');
  const doc = { ...descriptor("physical-appendix.md", appendix, "text/markdown"), artifact_id: "artifact.appendix", authored_path: "details/proofs/appendix.md" };
  const next = { ...descriptor("physical-notes.md", notes, "text/markdown"), artifact_id: "artifact.notes", authored_path: "details/proofs/notes.md" };
  const figure = descriptor("physical-figure.svg", image, "image/svg+xml");
  const files = { "artifact.appendix": doc, "details/proofs/appendix.md": doc, "details/proofs/notes.md": next, "details/proofs/figure.svg": figure };
  const bytes = new Map([[doc.path, appendix], [next.path, notes], [figure.path, image]]);
  const rendered = renderReport(katex, "", reportAssetInput({ markdown: '[Proof](artifact.appendix)', asset_files: files,
    print_material_id: "artifact.appendix" }, filename => bytes.get(filename)));
  assert.match(rendered.html, /data:image\/svg\+xml;base64,/);
  assert.match(rendered.html, /href="#report-support-2-entry"/);
  assert.match(rendered.html, /href="#report-support-1-document"/);
  assert.match(rendered.html, /Supporting document: details\/proofs\/appendix.md/);
});

test("a historical plain-text Markdown path stays readable without advertising an ineligible print scope", () => {
  const bytes = Buffer.from("# Historical support\n\nRetained readable content.");
  const file = { ...descriptor("support.md", bytes, "text/plain"), artifact_id: "artifact.support" };
  const input = { markdown: "[Support](support.md)", asset_files: { "support.md": file } };
  const rendered = renderReport(katex, "", reportAssetInput(input, () => bytes));
  assert.match(rendered.html, /Historical support/);
  assert.ok(!rendered.print_scopes.some(scope => scope.material_id === "artifact.support"));
  assert.throws(() => reportAssetInput({ ...input, print_material_id: "artifact.support" }, () => bytes), /not a retained Markdown/);
});
