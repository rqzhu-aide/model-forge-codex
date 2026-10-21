import { inlineTokens } from "./researchMath.js";

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

export function researchBlocks(text) {
  const lines = String(text).split(/\r?\n/); const blocks = []; let i = 0;
  const startsBlock = (at) => heading(lines[at]) || fence(lines[at]) || marker(lines[at])
    || /^ {0,3}> ?/.test(lines[at]) || (lines[at].includes("|") && separator(lines[at + 1]));
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const code = fence(line);
    if (code) {
      const body = []; const end = new RegExp(`^ {0,3}${code[1][0]}{${code[1].length},}\\s*$`); i++;
      while (i < lines.length && !end.test(lines[i])) body.push(lines[i++]);
      if (i < lines.length) i++;
      blocks.push({ kind: "code", text: body.join("\n") }); continue;
    }
    const title = heading(line);
    if (title) { blocks.push({ kind: "heading", level: title[1].length, text: title[2] }); i++; continue; }
    if (/^ {0,3}> ?/.test(line)) {
      const quoted = [];
      while (i < lines.length && /^ {0,3}> ?/.test(lines[i])) quoted.push(lines[i++].replace(/^ {0,3}> ?/, ""));
      blocks.push({ kind: "quote", blocks: researchBlocks(quoted.join("\n")) }); continue;
    }
    const first = marker(line);
    if (first) {
      const items = [];
      while (i < lines.length) {
        const item = marker(lines[i]);
        if (!item || item.indent !== first.indent || item.ordered !== first.ordered) break;
        const body = [item.text]; let display = displayState(item.text); i++;
        while (i < lines.length) {
          const next = lines[i]; const nextMarker = marker(next);
          if (!display && nextMarker && nextMarker.indent <= first.indent) break;
          if (!display && next.trim() && next.search(/\S/) <= first.indent) break;
          if (!display && !next.trim()) {
            let at = i + 1; while (at < lines.length && !lines[at].trim()) at++;
            if (at >= lines.length || lines[at].search(/\S/) <= first.indent) { i = at; break; }
          }
          const content = next.slice(Math.min(next.search(/\S/) < 0 ? next.length : next.search(/\S/), item.width));
          body.push(content); display = displayState(content, display); i++;
        }
        items.push({ value: item.value, blocks: researchBlocks(body.join("\n")) });
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
