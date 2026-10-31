import { inlineTokens, opaqueInlineRanges } from "./researchMath.js";

// Resolve document-local reference links before block rendering. Destinations
// still pass through the same safe inline/source resolvers as authored links.
// Definitions and uses inside code, mathematics or existing links stay literal.
export function referenceMarkdown(text) {
  const source = String(text); const opaque = []; let offset = 0;
  const lineRanges = source.split(/(?<=\n)/).map(line => {
    const range = [offset, offset + line.length]; offset += line.length; return range;
  });
  // Use the block reader's own container boundaries, including quoted/listed
  // and unclosed fences, instead of maintaining a second code-block parser.
  researchBlocks(source, (line) => { if (lineRanges[line]) opaque.push(lineRanges[line]); });
  opaque.push(...opaqueInlineRanges(source));
  const protectedAt = (index) => opaque.some(([start, end]) => index >= start && index < end);
  const labelKey = (label) => label.trim().replace(/\s+/g, " ").toLowerCase();
  const definitions = new Map(); const edits = [];
  const declaration = /^ {0,3}\[([^\]\r\n]+)\]:[ \t]*(?:<([^<>\r\n]+)>|(\S+))(?:[ \t]+(?:"[^"\r\n]*"|'[^'\r\n]*'|\([^\)\r\n]*\)))?[ \t]*\r?$/gm;
  for (const match of source.matchAll(declaration)) {
    if (protectedAt(match.index)) continue;
    const key = labelKey(match[1]);
    if (!key) continue;
    if (!definitions.has(key)) definitions.set(key, match[2] || match[3]);
    edits.push({ start: match.index, end: match.index + match[0].length, text: "" });
  }
  for (const match of source.matchAll(/(?<![!\\\]])\[([^\]\n]+)\](?:\[([^\]\n]*)\])?/g)) {
    if (protectedAt(match.index) || edits.some(({ start, end }) => match.index >= start && match.index < end)) continue;
    const target = definitions.get(labelKey(match[2] || match[1]));
    if (target) edits.push({ start: match.index, end: match.index + match[0].length, text: `[${match[1]}](<${target}>)` });
  }
  let resolved = source;
  for (const { start, end, text: replacement } of edits.sort((a, b) => b.start - a.start)) resolved = resolved.slice(0, start) + replacement + resolved.slice(end);
  return resolved;
}

// A deliberately small scientific Markdown reader. It creates structure only;
// React escapes prose/code, and Shared owns the existing safe inline renderer.
const marker = (line) => {
  const match = line.match(/^( *)([-+*]|\d+[.)])( +)(.*)$/);
  return match && { indent: match[1].length, ordered: /^\d/.test(match[2]),
    value: /^\d/.test(match[2]) ? Number.parseInt(match[2], 10) : undefined,
    width: match[1].length + match[2].length + match[3].length, text: match[4] };
};
const heading = (line) => line.match(/^ {0,3}(#{1,6})\s+(.*)$/);
const fence = (line) => line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
const indentedCode = (line) => line.startsWith("    ") ? line.slice(4) : line.startsWith("\t") ? line.slice(1) : null;

function displayState(line, current = null) {
  if (/^[ \t]*\$(?!\$)[ \t]*$/.test(line)) return current === "$" ? null : current || "$";
  for (const token of line.match(/`[^`]*`|(?<!\\)\$\$|(?<!\\)\\\[|(?<!\\)\\\]/g) || []) {
    if (token.startsWith("`")) continue;
    if (current === token) current = null;
    else if (!current && (token === "$$" || token === "\\[")) current = token === "$$" ? "$$" : "\\]";
  }
  return current;
}

export function tableCells(line) {
  const cells = [""];
  // Pipes inside declared math, code and links remain part of the authored cell.
  for (const [index, part] of line.trim().split(inlineTokens).entries()) {
    if (index % 2) { cells[cells.length - 1] += part; continue; }
    for (let i = 0; i < part.length; i++) {
      if (part[i] === "\\" && part[i + 1] === "|") { cells[cells.length - 1] += "|"; i++; }
      else if (part[i] === "|") cells.push("");
      else cells[cells.length - 1] += part[i];
    }
  }
  if (line.trim().startsWith("|")) cells.shift();
  if (line.trim().endsWith("|") && !line.trim().endsWith("\\|")) cells.pop();
  return cells.map((cell) => cell.trim());
}
const separator = (line) => {
  const cells = tableCells(line || "");
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
};

export function researchBlocks(text, onCodeLine) {
  const lines = String(text).split(/\r?\n/); const blocks = []; let i = 0;
  const startsBlock = (at) => heading(lines[at]) || fence(lines[at]) || marker(lines[at])
    || /^ {0,3}> ?/.test(lines[at]) || (lines[at].includes("|") && separator(lines[at + 1]));
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    // Indented code starts only at a block boundary. It cannot interrupt the
    // ordinary paragraph continuation handled below.
    if (indentedCode(line) !== null) {
      const body = [];
      while (i < lines.length && (!lines[i].trim() || indentedCode(lines[i]) !== null)) {
        onCodeLine?.(i);
        body.push(lines[i].trim() ? indentedCode(lines[i]) : ""); i++;
      }
      while (body.at(-1) === "") body.pop();
      blocks.push({ kind: "code", text: body.join("\n") }); continue;
    }
    const code = fence(line);
    if (code) {
      const body = []; const end = new RegExp(`^ {0,3}${code[1][0]}{${code[1].length},}\\s*$`); onCodeLine?.(i); i++;
      while (i < lines.length && !end.test(lines[i])) { onCodeLine?.(i); body.push(lines[i++]); }
      if (i < lines.length) { onCodeLine?.(i); i++; }
      blocks.push({ kind: "code", text: body.join("\n") }); continue;
    }
    const title = heading(line);
    if (title) { blocks.push({ kind: "heading", level: title[1].length, text: title[2] }); i++; continue; }
    if (/^ {0,3}> ?/.test(line)) {
      const quoted = [], origins = [];
      while (i < lines.length && /^ {0,3}> ?/.test(lines[i])) { origins.push(i); quoted.push(lines[i++].replace(/^ {0,3}> ?/, "")); }
      blocks.push({ kind: "quote", blocks: researchBlocks(quoted.join("\n"), onCodeLine && (at => onCodeLine(origins[at]))) }); continue;
    }
    const first = marker(line);
    if (first) {
      const items = [];
      while (i < lines.length) {
        const item = marker(lines[i]);
        if (!item || item.indent !== first.indent || item.ordered !== first.ordered) break;
        const body = [item.text], origins = [i]; let display = displayState(item.text); i++;
        while (i < lines.length) {
          const next = lines[i]; const nextMarker = marker(next);
          if (!display && nextMarker && nextMarker.indent <= first.indent) break;
          if (!display && next.trim() && next.search(/\S/) <= first.indent) break;
          if (!display && !next.trim()) {
            let at = i + 1; while (at < lines.length && !lines[at].trim()) at++;
            if (at >= lines.length || lines[at].search(/\S/) <= first.indent) { i = at; break; }
          }
          const content = next.slice(Math.min(next.search(/\S/) < 0 ? next.length : next.search(/\S/), item.width));
          origins.push(i); body.push(content); display = displayState(content, display); i++;
        }
        items.push({ value: item.value, blocks: researchBlocks(body.join("\n"), onCodeLine && (at => onCodeLine(origins[at]))) });
      }
      blocks.push({ kind: "list", ordered: first.ordered, items }); continue;
    }
    if (line.includes("|") && separator(lines[i + 1])) {
      const headers = tableCells(line); const rows = []; i += 2;
      while (i < lines.length && lines[i].trim() && lines[i].includes("|")) rows.push(tableCells(lines[i++]));
      blocks.push({ kind: "table", headers, rows }); continue;
    }
    const body = [line]; let display = displayState(line); i++;
    // A fenced code block cannot close an unfinished prose equation.
    while (i < lines.length && !fence(lines[i]) && (display || (lines[i].trim() && !startsBlock(i)))) {
      body.push(lines[i]); display = displayState(lines[i], display); i++;
    }
    blocks.push({ kind: "paragraph", text: body.join("\n") });
  }
  return blocks;
}
