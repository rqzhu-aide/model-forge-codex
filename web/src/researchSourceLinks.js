// Called only for prose left after the inline reader consumes code, math and
// authored Markdown links. A locator still needs the existing exact resolver.
export function bareRunSourceParts(text) {
  const source = String(text); const parts = []; let at = 0;
  const urls = [...source.matchAll(/(?:https?:\/\/|file:\/\/|mailto:)[^\s<>]+/gi)]
    .map((match) => [match.index, match.index + match[0].length]);
  for (const match of source.matchAll(/(?<![\w:/\\<])run:\/\/[A-Za-z0-9][A-Za-z0-9._-]*\/[^\s<>"'`]+/g)) {
    if (urls.some(([start, end]) => match.index >= start && match.index < end)) continue;
    let uri = match[0].replace(/[.,;:!?]+$/, "");
    // Closing sentence punctuation does not belong to a locator. Preserve
    // balanced parentheses/brackets when they actually occur in its path.
    while (/[)\]}]$/.test(uri)) {
      const close = uri.at(-1); const open = { ")": "(", "]": "[", "}": "{" }[close];
      if ([...uri].filter((char) => char === close).length <= [...uri].filter((char) => char === open).length) break;
      uri = uri.slice(0, -1).replace(/[.,;:!?]+$/, "");
    }
    if (!uri.slice(uri.indexOf("://") + 3).includes("/")) continue;
    parts.push({ text: source.slice(at, match.index) }, { text: uri, source: uri });
    at = match.index + uri.length;
  }
  parts.push({ text: source.slice(at) });
  return parts;
}
