// The artifact checker and renderer share the same supported math delimiters.
// Code and URLs are opaque: examples of TeX commands there are not equations.
// Single dollars declare a multiline block only on their own opening/closing
// lines. Pass the full enclosed body to KaTeX, including malformed inner dollars.
const standaloneDollar = String.raw`(?<![^\n])[ \t]*\$(?!\$)[ \t]*\r?\n[\s\S]*?(?<![^\n])[ \t]*\$(?!\$)[ \t]*(?=\r?\n|$)`;
const mathPattern = String.raw`(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$|(?<!\\)\\\[[\s\S]*?(?<!\\)\\\]|${standaloneDollar}|(?<![$\\])\$(?!\$)(?:\\.|[^$\n])+\$(?!\$)|(?<!\\)\\\([^\n]*?\\\)`;
const opaquePattern = String.raw`\x60{3,}[^\n]*\n[\s\S]*?(?:\x60{3,}|$)|~{3,}[^\n]*\n[\s\S]*?(?:~{3,}|$)|\x60+[^\x60]*\x60+|https?:\/\/[^\s<>]+`;
export const inlineTokens = new RegExp(`(\x60[^\x60]+\x60|${mathPattern}|\\*\\*[^*]+\\*\\*|\\[[^\\]]+\\]\\((?:<[^<>\\n]+>|[^\\s)]+)\\))`, "g");

export function mathBody(token) {
  if (token.startsWith("$$") || token.startsWith("\\[")) return { latex: token.slice(2, -2), display: true };
  if (/^[ \t]*\$(?!\$)[ \t]*\r?\n/.test(token) && /\n[ \t]*\$(?!\$)[ \t]*$/.test(token)) {
    return { latex: token.slice(token.indexOf("$") + 1, token.lastIndexOf("$")), display: true };
  }
  if (token.startsWith("\\(")) return { latex: token.slice(2, -2), display: false };
  if (token.startsWith("$")) return { latex: token.slice(1, -1), display: false };
  return null;
}

export function opaqueInlineRanges(text) {
  const code = /(?<!`)(`+)(?!`)[\s\S]*?(?<!`)\1(?!`)/;
  return [...String(text).matchAll(new RegExp(`${code.source}|${mathPattern}|!?\\[[^\\]]*\\]\\((?:<[^<>\\n]+>|[^\\s)]+)\\)`, "g"))]
    .map((token) => [token.index, token.index + token[0].length]);
}

// Bold can contain code, mathematics and links. Their own asterisks cannot
// close the surrounding emphasis or create emphasis inside an opaque token.
export function inlineStrongParts(text) {
  const source = String(text);
  // The first opening token owns its contents, including literal math/code
  // delimiters, rather than allowing overlapping opaque spans to hide prose.
  const opaque = opaqueInlineRanges(source);
  const parts = []; let opened = null, at = 0;
  for (const marker of source.matchAll(/(?<!\\)\*\*/g)) {
    if (opaque.some(([start, end]) => marker.index >= start && marker.index < end)) continue;
    if (opened === null) opened = marker.index;
    else {
      parts.push({ text: source.slice(at, opened), strong: false },
        { text: source.slice(opened + 2, marker.index), strong: true });
      at = marker.index + 2; opened = null;
    }
  }
  parts.push({ text: source.slice(at), strong: false });
  return parts;
}

// Presentation recovery for bare definitions in known mathematical objects.
// Share this exact boundary with the artifact checker: sentences, mixed prose,
// code, URLs and existing math delimiters keep their normal interpretation.
export function isBareMathDefinition(text) {
  if (typeof text !== "string") return false;
  const definition = text.trim();
  const hasRelation = /[=<>≤≥]|\\(?:leq?|geq?|equiv|approx|in|sim)\b/.test(definition);
  const hasProse = /[A-Za-z]{2,}/.test(definition.replace(/\\[A-Za-z]+/g, ""));
  return hasRelation && !hasProse && !/[$`]|\\[()[\]]/.test(definition);
}

export function mathSegments(text, raw = false) {
  if (raw) return [{ latex: String(text), display: true, offset: 0 }];
  const segments = [];
  for (const { text: chunk, offset, prefix } of proseChunks(text)) {
    for (const match of `${prefix ? "\0" : ""}${chunk}`.matchAll(new RegExp(mathPattern, "g"))) {
      segments.push({ ...mathBody(match[0]), offset: offset + match.index - prefix });
    }
  }
  return segments;
}

function proseChunks(text) {
  const source = String(text); const chunks = []; let start = 0;
  const append = (end) => {
    // Opaque code/URLs cannot turn the remainder of their line into a new line.
    const prefix = start > 0 && source[start - 1] !== "\n" ? 1 : 0;
    chunks.push({ text: source.slice(start, end), offset: start, prefix });
  };
  for (const opaque of source.matchAll(new RegExp(opaquePattern, "g"))) {
    append(opaque.index);
    start = opaque.index + opaque[0].length;
  }
  append(source.length);
  return chunks;
}

function displayDelimiterFindings(text) {
  const findings = [];
  for (const chunk of proseChunks(text)) {
    let opened = null;
    for (const match of `${chunk.prefix ? "\0" : ""}${chunk.text}`.matchAll(/(?<!\\)\$\$|(?<!\\)\\\[|(?<!\\)\\\]|(?<![^\n])[ \t]*\$(?!\$)[ \t]*(?=\r?\n|$)/g)) {
      const token = match[0].trim(); const offset = chunk.offset + match.index - chunk.prefix + match[0].indexOf(token);
      if (!opened) {
        if (token === "\\]") findings.push({ code: "math.invalid_delimiter", offset,
          message: "Display equation has a closing \\] without an opening \\[." });
        else opened = { token, offset, expected: token === "\\[" ? "\\]" : token };
      } else if (token === opened.expected) opened = null;
      else {
        findings.push({ code: "math.invalid_delimiter", offset: opened.offset,
          message: `Display equation opened with ${opened.token} but encountered ${token}; close it with ${opened.expected}.` });
        opened = null;
      }
    }
    if (opened) findings.push({ code: "math.invalid_delimiter", offset: opened.offset,
      message: `Display equation opened with ${opened.token} is unclosed; finish it with ${opened.expected}.` });
  }
  return findings;
}

const options = (display) => ({ throwOnError: true, displayMode: display, trust: false, strict: "ignore", maxExpand: 1000 });

// Older summaries sometimes double-encode the prose/equation separator.
// Recover only a single unescaped literal \\n before a complete opening display
// equation. Existing math, code, URLs and malformed display blocks stay authored.
export function legacySummaryForDisplay(summary) {
  if (typeof summary !== "string") return summary;
  const separators = [];
  for (const chunk of proseChunks(summary)) {
    if (displayDelimiterFindings(chunk.text).length) continue;
    for (const segment of mathSegments(chunk.text)) {
      if (!segment.display) continue;
      const separator = /(?<!\\)\\n\s*$/.exec(chunk.text.slice(0, segment.offset));
      if (separator) separators.push(chunk.offset + separator.index);
    }
  }
  let rendered = summary;
  for (const offset of separators.reverse()) {
    rendered = `${rendered.slice(0, offset)}\n\n${rendered.slice(offset + 2)}`;
  }
  return rendered;
}

export function parseMath(katex, latex, display = false) {
  return katex.renderToString(latex, options(display));
}

// Legacy JSON sometimes contains two literal backslashes before every TeX
// command. Recover only a uniformly doubled, recognizable command sequence.
// Never touch environments, single commands, or row breaks in aligned/matrix.
export function legacyMathCandidate(katex, latex) {
  if (/(?:\\begin|\\end)\s*\{/.test(latex) || /(?<!\\)\\[A-Za-z]+/.test(latex)) return null;
  const commands = [...latex.matchAll(/(?<!\\)\\\\([A-Za-z]+)/g)];
  if (!commands.length) return null;
  // Multi-letter operators/symbols must actually be accepted commands. This
  // excludes ordinary words after legitimate row breaks (such as \\next).
  if (commands.some(([, command]) => command.length < 2 || ["begin", "end"].includes(command))) return null;
  try {
    for (const [, command] of commands) {
      if (!["left", "right", "middle", "limits", "nolimits"].includes(command)) parseMath(katex, `\\${command}{X}{X}`);
    }
    const candidate = latex.replace(/(?<!\\)\\\\([A-Za-z]+)/g, "\\$1");
    parseMath(katex, candidate, true);
    return candidate;
  } catch { return null; }
}

export function validateMathText(katex, text, raw = false, checkMathEscapes = false) {
  const findings = raw ? [] : displayDelimiterFindings(text);
  for (const segment of mathSegments(text, raw)) {
    if (checkMathEscapes && /\r(?!\n)/.test(segment.latex)) {
      findings.push({ code: "math.corrupt_escape", offset: segment.offset,
        message: "This equation contains a lone carriage return, which may be a decoded TeX command escape such as \\rm. Restore the intended literal TeX backslash in the owned source; ordinary CRLF line endings are supported." });
      continue;
    }
    const candidate = legacyMathCandidate(katex, segment.latex);
    if (candidate !== null) {
      findings.push({ code: "math.overescaped_latex", offset: segment.offset,
        message: "This equation contains doubled TeX command backslashes after JSON decoding. Store one literal backslash per command (escaped once in JSON); preserve genuine aligned/matrix row breaks." });
      continue;
    }
    try { parseMath(katex, segment.latex, segment.display); }
    catch (error) {
      findings.push({ code: "math.invalid_latex", offset: segment.offset,
        message: String(error.message).slice(0, 600) });
    }
  }
  return findings;
}

export function renderMath(katex, latex, display) {
  // Recovery affects presentation only. The saved artifact stays unchanged,
  // and new drafts must correct the error through validate_artifacts.
  const candidate = legacyMathCandidate(katex, latex);
  return katex.renderToString(candidate ?? latex, { ...options(display), throwOnError: false });
}
