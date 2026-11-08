import { readableSections } from "./researchContent.js";
import { inlineStrongParts, inlineTokens, mathBody } from "./researchMath.js";
import { referenceMarkdown, researchBlocks } from "./researchMarkdown.js";

const empty = () => ({ words: 0, equations: 0 });
const add = (left, right) => ({ words: left.words + right.words, equations: left.equations + right.equations });
const total = (values) => values.reduce(add, empty());
const addressPattern = /\b(?:https?|artifact|generation):\/\/[^\s<>]+/gi;

// Code and explicit raw-field fallbacks are literal text, not rendered TeX.
// URLs and long digest tokens do not describe the amount of scientific prose.
export function plainReadingSize(text) {
  const prose = String(text ?? "").replace(addressPattern, " ").replace(/\b[a-f\d]{32,}\b/gi, " ");
  return { words: (prose.match(/[\p{L}\p{N}][\p{L}\p{N}\p{M}_]*(?:['’][\p{L}\p{N}\p{M}_]+)*/gu) || []).length, equations: 0 };
}

function inlineReadingSize(text) {
  const source = String(text);
  const emphasis = inlineStrongParts(source);
  if (emphasis.some((part) => part.strong)) return total(emphasis.map((part) => inlineReadingSize(part.text)));
  const addresses = [...source.matchAll(addressPattern)].map((match) => [match.index, match.index + match[0].length]);
  const plainRange = (start, end) => {
    let prose = "", at = start;
    for (const [from, to] of addresses) {
      if (to <= at || from >= end) continue;
      prose += source.slice(at, Math.max(at, from)) + " ";
      at = Math.min(end, to);
    }
    return plainReadingSize(prose + source.slice(at, end));
  };
  let size = empty(), at = 0;
  for (const match of source.matchAll(inlineTokens)) {
    size = add(size, plainRange(at, match.index));
    const token = match[0];
    if (!addresses.some(([start, end]) => match.index >= start && match.index < end)) {
      const math = mathBody(token);
      if (math?.latex) {
        if (math.latex.trim()) {
          if (math.display) size.equations++;
          else size.words++;
        }
      }
      else if (token.startsWith("`")) size = add(size, plainReadingSize(token.slice(1, -1)));
      else {
        const link = token.match(/^\[([^\]]+)\]\((?:<[^<>\n]+>|[^\s)]+)\)$/);
        size = add(size, link ? plainReadingSize(link[1]) : inlineReadingSize(token.slice(2, -2)));
      }
    }
    at = match.index + token.length;
  }
  return add(size, plainRange(at, source.length));
}

function blockReadingSize(block) {
  if (block.kind === "code") return plainReadingSize(block.text);
  if (block.kind === "quote") return total(block.blocks.map(blockReadingSize));
  if (block.kind === "list") return total(block.items.flatMap((item) => item.blocks.map(blockReadingSize)));
  if (block.kind === "table") return total([...block.headers, ...block.rows.flat()].map(inlineReadingSize));
  return inlineReadingSize(block.text);
}

// Follow ResearchDocument's own projection. Unknown objects and source metadata
// are not prose; a caller can separately count an explicitly displayed fallback.
// Generated field headings, status badges and empty-state copy are UI, not text
// authored for the scientific document.
export function researchReadingSize(value) {
  if (value == null || value === "") return empty();
  if (Array.isArray(value)) return total(value.map(researchReadingSize));
  if (typeof value === "object") {
    const title = value.title || value.label || value.headline;
    const formula = value.latex || value.symbol;
    return total([
      title ? inlineReadingSize(title) : empty(),
      formula ? { words: 0, equations: 1 } : empty(),
      ...readableSections(value).map(({ body }) => researchReadingSize(body)),
    ]);
  }
  return typeof value === "string" ? total(researchBlocks(referenceMarkdown(value)).map(blockReadingSize)) : empty();
}

export function formatReadingSize({ words = 0, equations = 0 } = {}) {
  const count = (value) => Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0;
  const prose = count(words), math = count(equations);
  return [
    prose ? `About ${prose.toLocaleString("en-US")} ${prose === 1 ? "word" : "words"}` : "",
    math ? `${math.toLocaleString("en-US")} displayed ${math === 1 ? "equation" : "equations"}` : "",
  ].filter(Boolean).join(" · ") || "No detailed text recorded";
}
