import { researchBlocks } from "../src/researchMarkdown.js";
import { inlineTokens, mathBody, parseMath, validateMathText } from "../src/researchMath.js";

export function renderReport(katex, css, input) {
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const findings = validateMathText(katex, input.markdown);
if (findings.length) throw new Error(findings[0].message);
const supplements = new Map();
const primaryPaths = new Set(input.primary_paths || []);
let needsPrimaryAnchor = false;
let current = { path: input.primary_path || "", prefix: "" };
const fragmentId = fragment => {
  try { return decodeURIComponent(fragment); } catch { return fragment; }
};
const scopedId = id => `${current.prefix}${id}`;
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
    let entry = supplements.get(document.identity);
    if (!entry) {
      entry = { ...document, path: key, prefix: `report-support-${supplements.size + 1}-` };
      supplements.set(document.identity, entry);
    }
    return `#${entry.prefix}${fragment ? fragmentId(fragment) : "document"}`;
  }
  return (input.assets[key] || file) + (fragment ? `#${fragment}` : "");
}
const opaque = /(!\[[^\]]*\]\([^\s)]+\)|<a id="[A-Za-z0-9_.:-]+"><\/a>)/g;
function inline(text) {
  return String(text).split(opaque).map((part, index) => {
    if (index % 2) {
      if (part.startsWith("<a ")) return part.replace(/id="([^"]+)"/, (_, id) => `id="${escape(scopedId(id))}"`);
      const match = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
      const source = input.assets[retainedKey(match[2])];
      if (!source?.startsWith("data:")) throw new Error(`The report image ${match[2]} has no retained offline bytes`);
      return `<img src="${escape(source)}" alt="${escape(match[1])}">`;
    }
    return part.split(inlineTokens).map((token, position) => {
      if (!(position % 2)) return escape(token);
      const math = mathBody(token);
      if (math) {
        const rendered = parseMath(katex, math.latex, math.display);
        return math.display ? `<span class="report-equation" tabindex="0" role="region" aria-label="Mathematical equation">${rendered}</span>` : rendered;
      }
      if (token.startsWith("`")) return `<code>${escape(token.slice(1, -1))}</code>`;
      if (token.startsWith("**")) return `<strong>${escape(token.slice(2, -2))}</strong>`;
      const match = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      const url = linkTarget(match[2]);
      if (!/^(?:https?:\/\/|data:|#)/.test(url)) throw new Error(`The report link ${url} has no portable target`);
      return `<a href="${escape(url)}">${escape(match[1])}</a>`;
    }).join("");
  }).join("");
}
function blocks(items) {
  return items.map((block) => {
    if (block.kind === "heading") return `<h${block.level}>${inline(block.text)}</h${block.level}>`;
    if (block.kind === "code") return `<pre><code>${escape(block.text)}</code></pre>`;
    if (block.kind === "quote") return `<blockquote>${blocks(block.blocks)}</blockquote>`;
    if (block.kind === "list") {
      const tag = block.ordered ? "ol" : "ul";
      return `<${tag}>${block.items.map((item) => `<li${item.value === undefined ? "" : ` value="${item.value}"`}>${blocks(item.blocks)}</li>`).join("")}</${tag}>`;
    }
    if (block.kind === "table") return `<div class="report-table" tabindex="0" role="region" aria-label="Report table"><table><thead><tr>${block.headers.map((cell) => `<th>${inline(cell)}</th>`).join("")}</tr></thead><tbody>${block.rows.map((row) => `<tr>${row.map((cell) => `<td>${inline(cell)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
    return `<p>${inline(block.text)}</p>`;
  }).join("\n");
}
let html = blocks(researchBlocks(input.markdown));
// Map iteration includes newly discovered documents. File identities prevent
// cycles and duplicate aliases from copying the same scientific account twice.
for (const entry of supplements.values()) {
  const errors = validateMathText(katex, entry.markdown);
  if (errors.length) throw new Error(`The report support ${entry.path}: ${errors[0].message}`);
  current = entry;
  html += `\n<details class="report-supplement" id="${entry.prefix}document"><summary>Supporting document: ${escape(entry.path)}</summary>${blocks(researchBlocks(entry.markdown))}</details>`;
}
if (supplements.size || needsPrimaryAnchor) html = '<a id="report-main"></a>' + html;
return { html, css };
}
