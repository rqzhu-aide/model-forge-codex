import { researchBlocks } from "../src/researchMarkdown.js";
import { inlineTokens, inlineStrongParts, mathBody, parseMath, validateMathText } from "../src/researchMath.js";
import { REPORT_SECTION_KEYS, reportReferenceBoundary } from "../src/reportSections.js";
import { portableDocumentCss, retainedDownloadName, retainedTable, reproductionMaterial } from "./report-portable-materials.mjs";
import { createHash } from "node:crypto";
import { bundleStandaloneDownloads } from "./report-downloads.mjs";
import { reportTableCaption } from "../src/reportTableCaption.js";
import { reportReferenceEmphasis } from "../src/reportReferenceEmphasis.js";
import { numericColumn, readingTemplate, supportingDisclosure } from "./report-reading.mjs";

export function renderReport(katex, css, input) {
// HTML parsing normalizes style newlines. Use those same bytes when computing
// a standalone edition's hash and sharing its CSS with a saved main report.
css = css.replace(/\r\n?/g, "\n");
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
function standaloneTitle(document) {
  const headings = researchBlocks(document.markdown).filter(block => block.kind === "heading");
  const heading = headings.find(block => block.level === 1) || headings[0];
  return heading?.text?.trim() || document.title?.trim() || retainedDownloadName(null, document.path) || "Supporting document";
}
function standalone(document) {
  return renderReport(katex, css, { ...input, title: standaloneTitle(document), markdown: document.markdown, primary_path: document.path,
    primary_paths: document.aliases, section_anchors: {}, print_material_id: undefined, print_document: undefined,
    standalone_material_id: undefined, standalone_mode: true, validate_materials: false,
    notation_markdown: undefined, reproduction_download_url: undefined, reproduction_archive_base64: undefined });
}
if (input.standalone_material_id) {
  const selected = Object.entries(input.asset_files || {}).find(([, file]) => file.artifact_id === input.standalone_material_id);
  const document = selected && input.documentForHtml?.(selected[0]);
  if (!document) throw new Error("The standalone HTML material needs one declared Markdown companion");
  return standalone(document);
}
const findings = validateMathText(katex, input.markdown, false, input.validate_materials === true);
if (findings.length) throw new Error(`The report ${input.primary_path || "primary source"}: ${findings[0].message}`);
const supplements = new Map();
const evidence = new Map();
const standaloneDownloads = new Map();
const encodedMaterials = new Map();
function retainedDownload(file, key, url) {
  const download = input.downloadForAsset?.(key) || { url, filename: retainedDownloadName(file, key) };
  if (download.delivery && file.artifact_id) encodedMaterials.set(file.artifact_id, { artifact_id: file.artifact_id, delivery: download.delivery });
  return !download.delivery && !file.download_url ? { ...download, url } : download;
}
function downloadLink(download, label) {
  const hashes = download.delivery ? ` data-source-sha256="${escape(download.source_sha256)}" data-export-sha256="${escape(download.delivery.decoded_sha256)}" data-download-sha256="${escape(download.delivery.sha256)}" data-content-encoding="gzip"` : "";
  return `<a href="${escape(download.url)}" download="${escape(download.filename)}"${hashes}>${escape(label)}</a>`;
}
function gzipNote(download) {
  return download.delivery ? `<p>Gzip-compressed source. Extract it to recover ${escape(download.delivery.decoded_filename)}.</p>` : "";
}
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
  return Object.hasOwn(input.asset_files || {}, relative) || Object.hasOwn(input.withheld_materials || {}, relative)
    || primaryPaths.has(relative) ? relative : source;
}
function unavailableMaterial(source, kind) {
  const key = retainedKey(source.split("#")[0]);
  const withheld = !Object.hasOwn(input.asset_files || {}, key) && input.withheld_materials?.[key];
  const unsafe = /^(?:[a-z][a-z0-9+.-]*:|[\\/]|~[\\/])/i.test(source);
  // Python consumes this structured diagnostic before presenting the finding.
  // Withheld source bytes never enter assets or rendered output.
  const message = withheld ? "A retained report material was withheld for privacy."
    : kind === "image" ? "The report image has no retained offline bytes." : "The report link has no portable target.";
  throw new Error(message + " MF_REPORT_MATERIAL " + JSON.stringify({
    reason: withheld ? "privacy_withheld" : unsafe ? "unsupported_location" : "undeclared_dependency", kind,
    linked_target: source, from_document: current.path || input.primary_path || null,
    ...(withheld ? { withheld_material: withheld } : {}),
  }));
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
  if (input.shareable_export && input.standalone_mode) {
    const htmlDocument = input.documentForHtml?.(key);
    if (htmlDocument) {
      const entry = registerDocument(htmlDocument, key);
      return `#${entry.prefix}${fragment ? fragmentId(fragment) : "document"}`;
    }
  }
  return (input.assets[key] || file) + (fragment ? `#${fragment}` : "");
}
const opaque = /(!\[[^\]]*\]\([^\s)]+\)|<a id="[A-Za-z0-9_.:-]+"><\/a>)/g;
const renderedTokens = new RegExp(`(${opaque.source.slice(1, -1)}|${inlineTokens.source.slice(1, -1)})`, "g");
function inline(text, nested = false) {
  const emphasis = inlineStrongParts(text);
  if (emphasis.some((part) => part.strong)) return emphasis.map((part) =>
    part.strong ? `<strong>${inline(part.text, nested)}</strong>` : inline(part.text, nested)).join("");
  const italics = reportReferenceEmphasis(text);
  if (italics.some(part => part.emphasis)) return italics.map(part =>
    part.emphasis ? `<em>${inline(part.text, nested)}</em>` : inline(part.text, nested)).join("");
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
        return nested && !current.prefix && reservedPrimaryAnchors.has(id) ? "" : `<a id="${escape(scopedId(id))}" tabindex="-1"></a>`;
      }
      if (token.startsWith("![")) {
      const match = token.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
      if (input.shareable_export && /^data:/i.test(match[2])) throw new Error("Shareable report images must use declared retained assets");
      const source = input.assets[retainedKey(match[2])];
      if (!source?.startsWith("data:")) unavailableMaterial(match[2], "image");
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
      if (input.shareable_export && /^data:/i.test(match[2])) throw new Error("Shareable report links must use declared retained assets");
      if (input.shareable_export && /^https?:\/\//i.test(match[2])) {
        const hostname = new URL(match[2]).hostname.toLowerCase();
        if (hostname === "localhost" || hostname.endsWith(".localhost") || /^127\./.test(hostname) || hostname === "[::1]") {
          return `<span>${escape(match[1])} (local source, unavailable in a shared report)</span>`;
        }
      }
      const url = linkTarget(match[2]);
      if (!/^(?:https?:\/\/|data:|#)/.test(url)) unavailableMaterial(match[2], "link");
      const file = input.asset_files?.[retainedKey(match[2].split("#")[0])];
      if (file && /^data:text\/html(?:;|,)/i.test(url)) {
        // Hosted views use a verified attachment endpoint. Shareable offline
        // editions render their declared Markdown without a network dependency.
        const key = retainedKey(match[2].split("#")[0]);
        const filename = retainedDownloadName(file, key);
        const label = /^proof$/i.test(match[1].trim()) ? "proof appendix" : match[1];
        const fragment = url.includes("#") ? url.slice(url.indexOf("#")) : "";
        let download = file.download_url ? file.download_url + fragment : url;
        if (input.shareable_export) {
          const document = input.documentForHtml?.(key);
          if (!document) throw new Error(`The standalone HTML material ${key} needs one declared Markdown companion`);
          const title = standaloneTitle(document);
          const entry = registerDocument(document, key);
          if (!standaloneDownloads.has(document.identity)) {
            if (!file.download_url) {
              const rendered = standalone(document);
              const body = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + escape(title) + '</title><style>'
                + rendered.css + portableDocumentCss + rendered.print_css + '</style><body>'
                + rendered.html.replace('<!--report-publication-details-->', '<details class="report-publication"><summary>About this standalone edition</summary><p>Linked scientific sources are included for offline reading. Shared source extracts omit private notes and machine paths.</p></details>') + '</body></html>';
              download = body;
            } else download = file.download_url;
            standaloneDownloads.set(document.identity, { href: file.download_url || `#${entry.prefix}document`,
              ...(file.download_url ? {} : { body: download, download_index: [...standaloneDownloads.values()].filter(value => value.body).length }), filename, label: title,
              artifact_id: file.artifact_id, source_sha256: file.source_sha256 || file.sha256,
              source_markdown_sha256: document.source_sha256,
              export_sha256: file.download_url ? null : createHash("sha256").update(download).digest("hex") });
          }
          return `<a href="#${entry.prefix}${fragment ? fragmentId(fragment.slice(1)) : "document"}">${escape(match[1])}</a>`;
        }
        return `<a href="${escape(download)}" download="${escape(filename)}">Download ${escape(label)} (HTML)</a>`;
      }
      if (file && /^data:/i.test(url)) {
        const key = retainedKey(match[2].split("#")[0]);
        const download = retainedDownload(file, key, url);
        const table = retainedTable(url, file.media_type);
        if (table || download.delivery) {
          let entry = evidence.get(file.path);
          if (!entry) { entry = { id: `report-evidence-${evidence.size + 1}`, table, download, label: match[1], path: key }; evidence.set(file.path, entry); }
          return `<a href="#${entry.id}">${escape(match[1])}</a>`;
        }
        return downloadLink(download, `${match[1]} (download ${download.filename})`);
      }
      return `<a href="${escape(url)}">${escape(match[1])}</a>`;
  }).join("");
}
let headingSequence = 0, tableSequence = 0;
const contents = [];
function blocks(items, depth = 0, primary = false) {
  return items.map((block, index) => {
    const next = items[index + 1];
    // Preserve an authored caption once, as the table's semantic caption.
    if (reportTableCaption(block) && next?.kind === "table") return "";
    const anchorOnly = block.kind === "paragraph" && /^\s*(?:<a id="[A-Za-z0-9_.:-]+"><\/a>\s*)+$/.test(block.text);
    if (anchorOnly && next?.kind === "heading") return "";
    if (block.kind === "heading") {
      const previous = items[index - 1];
      const anchors = previous?.kind === "paragraph" && /^\s*(?:<a id="[A-Za-z0-9_.:-]+"><\/a>\s*)+$/.test(previous.text)
        ? [...previous.text.matchAll(/<a id="([^"]+)"><\/a>/g)].map(match => match[1])
          .filter(anchor => !(depth > 0 && !current.prefix && reservedPrimaryAnchors.has(anchor))) : [];
      const id = scopedId(anchors[0] || `report-heading-${++headingSequence}`);
      if (primary && depth === 0 && block.level > 1) contents.push({ id, label: block.text.replace(/<a id="[^"]+"><\/a>/g, "").replace(/[*`]/g, "").trim() });
      return anchors.slice(1).map(anchor => `<a id="${escape(scopedId(anchor))}" tabindex="-1"></a>`).join("")
        + `<h${block.level} id="${escape(id)}" tabindex="-1">${inline(block.text, depth > 0)}</h${block.level}>`;
    }
    if (block.kind === "code") return `<pre><code>${escape(block.text)}</code></pre>`;
    if (block.kind === "quote") return `<blockquote>${blocks(block.blocks, depth + 1)}</blockquote>`;
    if (block.kind === "list") {
      const tag = block.ordered ? "ol" : "ul";
      return `<${tag}>${block.items.map((item) => `<li${item.value === undefined ? "" : ` value="${item.value}"`}>${blocks(item.blocks, depth + 1)}</li>`).join("")}</${tag}>`;
    }
    if (block.kind === "table") {
      const caption = reportTableCaption(items[index - 1]);
      const id = scopedId(`report-table-${++tableSequence}-caption`);
      const numbers = block.headers.map((_, column) => numericColumn(block.rows.map(row => row[column])));
      return `<div class="report-table" tabindex="0" role="region" aria-labelledby="${escape(id)}"><table><caption id="${escape(id)}"${caption ? "" : ' class="report-table-caption-fallback"'}>${caption ? inline(caption, true) : block.headers.map(cell => inline(cell, true)).join("; ")}</caption><thead><tr>${block.headers.map((cell, column) => `<th scope="col"${numbers[column] ? ' class="report-number"' : ""}>${inline(cell, true)}</th>`).join("")}</tr></thead><tbody>${block.rows.map((row) => `<tr>${row.map((cell, column) => `<td${numbers[column] ? ' class="report-number"' : ""}>${inline(cell, true)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    }
    return `<p>${inline(block.text, depth > 0)}</p>`;
  }).join("\n");
}
const parsed = researchBlocks(input.markdown);
const boundary = reportReferenceBoundary(input.markdown, input.section_anchors, parsed);
// Leave the title and opening account ahead of secondary reading controls.
const firstSection = parsed.findIndex(block => block.kind === "heading" && block.level > 1);
let openingEnd = firstSection >= 0 ? firstSection : parsed.length;
if (openingEnd > 0 && parsed[openingEnd - 1]?.kind === "paragraph" && /^\s*<a id="[^"]+"><\/a>\s*$/.test(parsed[openingEnd - 1].text)) openingEnd--;
const renderPrimary = items => {
  if (!items.length) return "";
  const split = Math.min(openingEnd, items.length);
  return blocks(items.slice(0, split), 0, true) + "<!--report-reading-tools-->" + blocks(items.slice(split), 0, true);
};
let html = boundary
  ? `<section class="report-body" aria-label="Scientific report">${renderPrimary(parsed.slice(0, boundary.startIndex))}</section>\n<section class="report-references" aria-label="References">${blocks(parsed.slice(boundary.startIndex), 0, true)}</section>`
  : renderPrimary(parsed);
let notation = "";
if (!input.standalone_mode && typeof input.notation_markdown === "string" && input.notation_markdown.trim()) {
  const notationErrors = validateMathText(katex, input.notation_markdown, false, input.validate_materials === true);
  if (notationErrors.length) throw new Error(`The report notation: ${notationErrors[0].message}`);
  notation = `<details class="report-notation" id="report-notation"><summary>Notation glossary</summary><section class="report-notation-content" id="report-notation-content" tabindex="-1" aria-label="Notation for this report">${blocks(researchBlocks(input.notation_markdown))}</section></details>`;
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
const supportLinks = [];
// Map iteration includes newly discovered documents. File identities prevent
// cycles and duplicate aliases from copying the same scientific account twice.
// Table captions and cells may also link to retained supporting documents.
const renderedSupplements = new Set(), renderedEvidence = new Set();
while (renderedSupplements.size < supplements.size || renderedEvidence.size < evidence.size) {
for (const entry of supplements.values()) {
  if (renderedSupplements.has(entry.identity)) continue;
  renderedSupplements.add(entry.identity);
  const errors = validateMathText(katex, entry.markdown, false, input.validate_materials === true);
  if (errors.length) throw new Error(`The report support ${entry.path}: ${errors[0].message}`);
  current = entry;
  const body = blocks(researchBlocks(entry.markdown));
  const download = standaloneDownloads.get(entry.identity);
  const action = download ? `<p><a href="${escape(download.href)}"${download.body ? ` data-report-download="${download.download_index}"` : ` download="${escape(download.filename)}"`}>Download standalone ${escape(download.label)} (HTML)</a></p>` : "";
  const title = standaloneTitle(entry);
  supportLinks.push({ id: `${entry.prefix}document`, label: title });
  supportHtml.push(supportingDisclosure(title, `${entry.prefix}document`, action + body, escape,
    entry.artifact_id ? ` data-report-material="${escape(entry.artifact_id)}"` : ""));
}
for (const entry of evidence.values()) {
  if (renderedEvidence.has(entry.id)) continue;
  renderedEvidence.add(entry.id);
  current = { path: entry.path, prefix: `${entry.id}-` };
  const cell = value => typeof value === "string" && value !== "" ? inline(value) : escape(value === null || value === undefined || value === "" ? "Not recorded" : typeof value === "object" ? JSON.stringify(value) : value);
  const captionId = `${entry.id}-caption`;
  const numbers = entry.table?.columns.map(column => numericColumn(entry.table.rows.map(row => row[column.key])));
  const table = entry.table ? `<div class="report-table" tabindex="0" role="region" aria-labelledby="${captionId}"><table><caption id="${captionId}">${inline(entry.table.caption || entry.label)}</caption><thead><tr>${entry.table.columns.map((column, index) => `<th scope="col"${numbers[index] ? ' class="report-number"' : ""}>${inline(column.label || column.key)}${column.unit ? ` (${inline(column.unit)})` : ""}</th>`).join("")}</tr></thead><tbody>${entry.table.rows.map(row => `<tr>${entry.table.columns.map((column, index) => `<td${numbers[index] ? ' class="report-number"' : ""}>${cell(row[column.key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>` : "";
  supportHtml.push(supportingDisclosure(entry.label, entry.id, `<p>${downloadLink(entry.download, `Download ${entry.download.filename}`)}</p>${gzipNote(entry.download)}${table}`, escape));
}
}
if (input.shareable_export && !input.standalone_mode) {
  const listed = new Set(); const downloads = [];
  const reproductionArchive = input.reproduction_download_url
    || (input.reproduction_archive_base64 ? `data:application/zip;base64,${input.reproduction_archive_base64}` : null);
  const reproductionFilename = retainedDownloadName({ export_filename: input.reproduction_filename || "report-reproduction.shareable.zip" });
  for (const [key, file] of Object.entries(input.asset_files || {})) {
    if (listed.has(file.path) || !reproductionMaterial(key, file)) continue;
    listed.add(file.path);
    const download = retainedDownload(file, key, input.assets[key]);
    const label = file.authored_path ? file.authored_path + (download.delivery ? ".gz" : "") : download.filename;
    downloads.push(`<li>${downloadLink(download, label)}${gzipNote(download)}</li>`);
  }
  if (downloads.length || reproductionArchive) supportHtml.push(supportingDisclosure("Code and configuration", "report-reproduction", '<h2>Code and configuration</h2><p>These materials document the recorded evaluation; this export does not establish a new successful reproduction.</p>'
    + (reproductionArchive ? `<p><a href="${escape(reproductionArchive)}" download="${escape(reproductionFilename)}">Download shareable reproduction package (ZIP)</a></p><p>The package preserves the declared folder structure for code, configuration and scientific evidence. Its manifest lists included files, source and export hashes, and omitted materials.</p>` : "")
    + (downloads.length ? `<details><summary>Download individual code and configuration files</summary><p>Save these files with the displayed folder structure.</p><ul>${downloads.join("")}</ul></details>` : ""), escape));
}
if (supplements.size || needsPrimaryAnchor) html = '<a id="report-main"></a>' + html;
const scopes = [{ id: "report-print-main", label: input.standalone_mode ? "This document" : boundary ? "Report with references" : "Report", material_id: null }];
for (const entry of supplements.values()) {
  if (entry.artifact_id && entry.media_type === "text/markdown") scopes.push({ id: `${entry.prefix}print`, label: standaloneTitle(entry), material_id: entry.artifact_id, region_id: `${entry.prefix}document` });
}
if (input.print_material_id && !scopes.some((scope) => scope.material_id === input.print_material_id)) throw new Error("The selected print material has no exact retained document scope");
const reading = readingTemplate({ html, opening: parsed.some(block => block.kind === "heading" && block.level === 1) ? "" : `<h1>${escape(input.title || "Technical report")}</h1>`,
  headings: contents, notation, supportHtml, supportLinks, scopes, selectedMaterial: input.print_material_id, escape, standalone: input.standalone_mode });
html = reading.html;
const print_css = reading.print_css;
html = bundleStandaloneDownloads(html, css, [...standaloneDownloads.values()]);
return { html, css, title: input.title, print_css, print_scopes: Object.freeze(scopes.map((scope) => Object.freeze(scope))),
  encoded_materials: [...encodedMaterials.values()],
  derived_materials: [...standaloneDownloads.values()].filter(value => value.export_sha256).map(({ artifact_id, source_sha256, source_markdown_sha256, export_sha256 }) => ({ artifact_id, source_sha256, source_markdown_sha256, export_sha256 })) };
}
