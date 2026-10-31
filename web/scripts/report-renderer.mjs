import { researchBlocks } from "../src/researchMarkdown.js";
import { inlineTokens, inlineStrongParts, mathBody, parseMath, validateMathText } from "../src/researchMath.js";
import { REPORT_SECTION_KEYS, reportReferenceBoundary } from "../src/reportSections.js";

export function renderReport(katex, css, input) {
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const findings = validateMathText(katex, input.markdown, false, input.validate_materials === true);
if (findings.length) throw new Error(`The report ${input.primary_path || "primary source"}: ${findings[0].message}`);
const supplements = new Map();
const reservedPrimaryAnchors = new Set([...REPORT_SECTION_KEYS, "references"].map((key) => input.section_anchors?.[key]).filter(Boolean));
const primaryPaths = new Set(input.primary_paths || []);
let needsPrimaryAnchor = false;
let current = { path: input.primary_path || "", prefix: "" };
const fragmentId = fragment => {
  try { return decodeURIComponent(fragment); } catch { return fragment; }
};
const scopedId = id => `${current.prefix}${id}`;
function registerDocument(document, path) {
  let entry = supplements.get(document.identity);
  if (!entry) {
    entry = { ...document, path: document.path || path, prefix: `report-support-${supplements.size + 1}-` };
    supplements.set(document.identity, entry);
  }
  return entry;
}
function relativePath(source) {
  if (!current.path || /^(?:[a-z]+:|\/)/i.test(source)) return source;
  const parts = current.path.split("/").slice(0, -1);
  for (const part of source.split("/")) {
    if (part === "..") parts.pop();
    else if (part !== "." && part) parts.push(part);
  }
  return parts.join("/");
}
function retainedKey(source) {
  const relative = relativePath(source);
  // Prefer the document-relative exact path, then a declared legacy alias.
  return Object.hasOwn(input.asset_files || {}, relative) || primaryPaths.has(relative) ? relative : source;
}
function linkTarget(source) {
  if (source.startsWith("#")) return `#${scopedId(fragmentId(source.slice(1)))}`;
  if (/^(?:https?:\/\/|data:)/.test(source)) return source;
  const [file, ...fragments] = source.split("#");
  const fragment = fragments.join("#");
  const key = retainedKey(file);
  if (primaryPaths.has(key)) {
    if (!fragment) needsPrimaryAnchor = true;
    return fragment ? `#${fragmentId(fragment)}` : "#report-main";
  }
  const document = input.documents?.[key];
  if (document) {
    const entry = registerDocument(document, key);
    return `#${entry.prefix}${fragment ? fragmentId(fragment) : "document"}`;
  }
  return (input.assets[key] || file) + (fragment ? `#${fragment}` : "");
}
const opaque = /(!\[[^\]]*\]\([^\s)]+\)|<a id="[A-Za-z0-9_.:-]+"><\/a>)/g;
const renderedTokens = new RegExp(`(${opaque.source.slice(1, -1)}|${inlineTokens.source.slice(1, -1)})`, "g");
function inline(text, nested = false) {
  const emphasis = inlineStrongParts(text);
  if (emphasis.some((part) => part.strong)) return emphasis.map((part) =>
    part.strong ? `<strong>${inline(part.text, nested)}</strong>` : inline(part.text, nested)).join("");
  const source = String(text); const parts = []; let at = 0;
  for (const code of source.matchAll(/(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)/g)) {
    parts.push(inlineContent(source.slice(at, code.index), nested), `<code>${escape(code[2])}</code>`);
    at = code.index + code[0].length;
  }
  parts.push(inlineContent(source.slice(at), nested));
  return parts.join("");
}
function inlineContent(text, nested) {
  return text.split(renderedTokens).map((token, position) => {
      if (!(position % 2)) return escape(token);
      if (token.startsWith("<a ")) {
        const id = token.match(/id="([^"]+)"/)[1];
        return nested && !current.prefix && reservedPrimaryAnchors.has(id) ? "" : `<a id="${escape(scopedId(id))}"></a>`;
      }
      if (token.startsWith("![")) {
      const match = token.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
      const source = input.assets[retainedKey(match[2])];
      if (!source?.startsWith("data:")) throw new Error(`The report image ${match[2]} has no retained offline bytes`);
      return `<img src="${escape(source)}" alt="${escape(match[1])}">`;
      }
      const math = mathBody(token);
      if (math) {
        const rendered = parseMath(katex, math.latex, math.display);
        return math.display ? `<span class="report-equation" tabindex="0" role="region" aria-label="Mathematical equation">${rendered}</span>` : rendered;
      }
      if (token.startsWith("`")) return `<code>${escape(token.slice(1, -1))}</code>`;
      if (token.startsWith("**")) return `<strong>${escape(token.slice(2, -2))}</strong>`;
      const match = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const url = linkTarget(match[2]);
      if (!/^(?:https?:\/\/|data:|#)/.test(url)) throw new Error(`The report link ${url} has no portable target (from ${current.path || "primary report"})`);
      const file = input.asset_files?.[retainedKey(match[2].split("#")[0])];
      if (file && /^data:text\/html(?:;|,)/i.test(url)) {
        // Hosted views use a verified attachment endpoint. Standalone files
        // retain the original bytes without introducing a network dependency.
        const filename = (file.authored_path || file.path).split(/[\\/]/).at(-1);
        const label = /^proof$/i.test(match[1].trim()) ? "proof appendix" : match[1];
        const fragment = url.includes("#") ? url.slice(url.indexOf("#")) : "";
        const download = file.download_url ? file.download_url + fragment : url;
        return `<a href="${escape(download)}" download="${escape(filename)}">Download ${escape(label)} (HTML)</a>`;
      }
      return `<a href="${escape(url)}">${escape(match[1])}</a>`;
  }).join("");
}
function blocks(items, depth = 0) {
  return items.map((block) => {
    if (block.kind === "heading") return `<h${block.level}>${inline(block.text, depth > 0)}</h${block.level}>`;
    if (block.kind === "code") return `<pre><code>${escape(block.text)}</code></pre>`;
    if (block.kind === "quote") return `<blockquote>${blocks(block.blocks, depth + 1)}</blockquote>`;
    if (block.kind === "list") {
      const tag = block.ordered ? "ol" : "ul";
      return `<${tag}>${block.items.map((item) => `<li${item.value === undefined ? "" : ` value="${item.value}"`}>${blocks(item.blocks, depth + 1)}</li>`).join("")}</${tag}>`;
    }
    if (block.kind === "table") return `<div class="report-table" tabindex="0" role="region" aria-label="Report table"><table><thead><tr>${block.headers.map((cell) => `<th>${inline(cell, true)}</th>`).join("")}</tr></thead><tbody>${block.rows.map((row) => `<tr>${row.map((cell) => `<td>${inline(cell, true)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    return `<p>${inline(block.text, depth > 0)}</p>`;
  }).join("\n");
}
const parsed = researchBlocks(input.markdown);
const boundary = reportReferenceBoundary(input.markdown, input.section_anchors, parsed);
let html = boundary
  ? `<section class="report-body" aria-label="Scientific report">${blocks(parsed.slice(0, boundary.startIndex))}</section>\n<section class="report-references" aria-label="References">${blocks(parsed.slice(boundary.startIndex))}</section>`
  : blocks(parsed);
if (typeof input.notation_markdown === "string" && input.notation_markdown.trim()) {
  const notationErrors = validateMathText(katex, input.notation_markdown, false, input.validate_materials === true);
  if (notationErrors.length) throw new Error(`The report notation: ${notationErrors[0].message}`);
  html += `<section class="report-notation" id="report-notation" aria-label="Notation for this report">${blocks(researchBlocks(input.notation_markdown))}</section>`;
}
if (input.print_document) registerDocument(input.print_document, input.print_document.path);
if (input.validate_materials === true) {
  for (const [key, file] of Object.entries(input.asset_files || {})) {
    if (primaryPaths.has(key) || file?.media_type !== "text/markdown") continue;
    const document = input.documents?.[key];
    if (document) registerDocument(document, key);
  }
}
const supportHtml = [];
// Map iteration includes newly discovered documents. File identities prevent
// cycles and duplicate aliases from copying the same scientific account twice.
for (const entry of supplements.values()) {
  const errors = validateMathText(katex, entry.markdown, false, input.validate_materials === true);
  if (errors.length) throw new Error(`The report support ${entry.path}: ${errors[0].message}`);
  current = entry;
  supportHtml.push(`<section class="report-supplement" id="${entry.prefix}document"${entry.artifact_id ? ` data-report-material="${escape(entry.artifact_id)}"` : ""}><h2 class="report-support-title">Supporting document: ${escape(entry.path)}</h2>${blocks(researchBlocks(entry.markdown))}</section>`);
}
if (supplements.size || needsPrimaryAnchor) html = '<a id="report-main"></a>' + html;
const scopes = [{ id: "report-print-main", label: boundary ? "Report with references" : "Report", material_id: null }];
for (const entry of supplements.values()) {
  if (entry.artifact_id && entry.media_type === "text/markdown") scopes.push({ id: `${entry.prefix}print`, label: `Supporting document: ${entry.path}`, material_id: entry.artifact_id, region_id: `${entry.prefix}document` });
}
if (input.print_material_id && !scopes.some((scope) => scope.material_id === input.print_material_id)) throw new Error("The selected print material has no exact retained document scope");
let print_css = "";
if (boundary || supplements.size) {
  const controls = scopes.map((scope) => `<input class="report-print-choice" type="radio" name="report-print-scope" id="${scope.id}"${(input.print_material_id ? scope.material_id === input.print_material_id : scope.material_id === null) ? " checked" : ""}><label class="report-print-label" for="${scope.id}">${escape(scope.label)}</label>`).join("\n");
  html = `<div class="report-print-edition"><p class="report-print-caption">Print selection</p>${controls}<div class="report-primary">${html}</div>\n${supportHtml.join("\n")}</div>`;
  print_css = ".report-print-caption{font:600 14px/1.5 sans-serif;margin:1.5rem 0 .4rem}.report-print-choice{accent-color:#2c5c87;margin:.35rem .4rem .35rem 0}.report-print-label{font:14px/1.5 sans-serif;margin-right:1.2rem}.report-print-choice:focus-visible{outline:2px solid #2c5c87;outline-offset:3px}.report-primary{margin-top:1.5rem}.report-supplement{margin-top:3rem;padding-top:1rem;border-top:1px solid #ccd0d6}.report-support-title{font:600 16px/1.5 sans-serif;overflow-wrap:anywhere}"
    + "@page{size:letter;margin:1in}@media print{body{padding:0;font-size:11pt;line-height:1.4}.report-print-caption,.report-print-choice,.report-print-label,aside details,.report-provenance{display:none!important}.report-primary{margin:0}.report-supplement{display:none!important}.report-references{break-before:page;page-break-before:always}"
    + scopes.filter((scope) => scope.material_id).map((scope) => `#${scope.id}:checked~.report-primary{display:none!important}#${scope.id}:checked~#${scope.region_id}{display:block!important;margin:0;padding:0;border:0}`).join("")
    + "}";
}
return { html, css, print_css, print_scopes: Object.freeze(scopes.map((scope) => Object.freeze(scope))) };
}
