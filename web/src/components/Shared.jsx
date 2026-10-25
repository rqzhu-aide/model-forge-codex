import React, { useEffect, useId, useRef } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import "../researchMath.css";
import { inlineTokens, inlineStrongParts, mathBody, renderMath } from "../researchMath";
import { humanLabel, OUTCOMES, methodUpdateMessage, methodStatusBadge } from "../research";
import { readableSections } from "../researchContent";
import { researchBlocks } from "../researchMarkdown";
import { executionStatus } from "../visualSemantics";
import { ActionButton, ActionIcon } from "./Visuals";
import { availableFocusTarget, dialogFocusTargets } from "../dialogFocus";

const dialogStack = [];

export function Outcome({ state }) {
  // Execution states must never become a scientific finding by fallback.
  const [kind, label] = OUTCOMES[state] || OUTCOMES.not_assessed;
  const icon = kind === "ok" ? "check" : kind === "fail" ? "close" : "details";
  return <span className={`outcome-badge ${kind}`}><ActionIcon name={icon} /><span className="outcome-label">Finding:</span><span>{label}</span></span>;
}
export function RunState({ state }) {
  const { tone, label } = executionStatus(state);
  return <span className={`pill ${tone}`}>{label}</span>;
}
export function Dialog({ title, children, onClose, busy = false, className = "", returnFocus }) {
  const titleId = useId(); const ref = useRef(null); const closeRef = useRef(onClose); closeRef.current = onClose;
  const busyRef = useRef(busy); busyRef.current = busy;
  const returnRef = useRef(returnFocus); returnRef.current = returnFocus;
  useEffect(() => {
    const previous = document.activeElement;
    const box = ref.current;
    dialogStack.push(box);
    const active = () => dialogStack.at(-1) === box;
    const firstFocus = () => (dialogFocusTargets(box)[0] || box).focus({ preventScroll: true });
    firstFocus();
    const repairFocus = () => {
      if (active() && (!box.contains(document.activeElement) || !availableFocusTarget(document.activeElement))) firstFocus();
    };
    const observer = new MutationObserver(repairFocus);
    observer.observe(box, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled", "hidden", "open", "inert", "style", "class"] });
    const handle = (event) => {
      if (!active()) return;
      if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); if (!busyRef.current) closeRef.current(); }
      if (event.key !== "Tab") return;
      const elements = dialogFocusTargets(box);
      const first = elements[0]; const last = elements[elements.length - 1];
      if (!first) { event.preventDefault(); box.focus(); }
      else if (event.shiftKey && (document.activeElement === first || !elements.includes(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !elements.includes(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", handle);
    const overflow = document.body.style.overflow; document.body.style.overflow = "hidden";
    return () => {
      observer.disconnect(); document.removeEventListener("keydown", handle);
      dialogStack.splice(dialogStack.indexOf(box), 1); document.body.style.overflow = overflow;
      const fallback = typeof returnRef.current === "function" ? returnRef.current() : returnRef.current?.current || returnRef.current;
      const parent = dialogStack.at(-1);
      const invoker = previous !== document.body && availableFocusTarget(previous) ? previous : null;
      const target = parent ? invoker && parent.contains(invoker) ? invoker : dialogFocusTargets(parent)[0] || parent : invoker || (availableFocusTarget(fallback) ? fallback : null);
      target?.focus({ preventScroll: true });
    };
  }, []);
  return <div className="modal-back" onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onClose(); }}>
    <section className={`modal ${className}`.trim()} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-busy={busy} tabIndex={-1} ref={ref}>
      <div className="section-heading modal-header"><h2 id={titleId}>{title}</h2><ActionButton action="close" aria-label="Close dialog" onClick={onClose} disabled={busy}>Close</ActionButton></div>
      <div className="modal-body" role="region" aria-label={`${title} content`} tabIndex={0}>{children}</div>
    </section>
  </div>;
}

export function MathText({ latex, display = true }) {
  if (!latex) return null;
  return <span className={display ? "math-block" : "math-inline"} dangerouslySetInnerHTML={{ __html: renderMath(katex, String(latex), display) }} />;
}

// Disclosure labels keep authored inline mathematics without nested links or
// block elements inside the keyboard-operable summary.
export function ResearchLabel({ text, className }) {
  return <span className={className}>{String(text || "").split(inlineTokens).map((part, index) => {
    const math = index % 2 && mathBody(part);
    if (math?.latex) return <MathText key={index} latex={math.latex} display={false} />;
    if (index % 2 && part.startsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (index % 2 && part.startsWith("`")) return <code key={index}>{part.slice(1, -1)}</code>;
    const link = part.match(/^\[([^\]]+)\]\([^)]*\)$/);
    return link ? link[1] : part;
  })}</span>;
}

const safeUrl = (url) => /^(https?:\/\/|\/api\/)/i.test(url) ? url : undefined;
// Display delimiters may appear between sentences, not just on their own lines.
// Code spans are consumed as one token before their contents can become math.
function inline(text, renderInternalLink, renderImage, renderAnchor, path = "document", renderFileLink, renderSourceLink) {
  const emphasis = inlineStrongParts(text);
  if (emphasis.some((part) => part.strong)) return emphasis.map((part, index) => {
    const children = inline(part.text, renderInternalLink, renderImage, renderAnchor, `${path}.emphasis${index}`, renderFileLink, renderSourceLink);
    return part.strong ? <strong key={index}>{children}</strong> : <React.Fragment key={index}>{children}</React.Fragment>;
  });
  if (renderImage || renderAnchor) {
    const source = String(text);
    // An authored anchor or image is markup only in prose. Keep examples in
    // code and mathematics intact before resolving exact report targets.
    const opaque = [...source.matchAll(/(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)/g),
      ...[...source.matchAll(inlineTokens)].filter((match) => mathBody(match[0]))]
      .map((match) => [match.index, match.index + match[0].length]);
    const parts = []; let at = 0;
    for (const match of source.matchAll(/(!\[[^\]]*\]\([^\s)]+\)|<a id="[A-Za-z0-9_.:-]+"><\/a>)/g)) {
      if (opaque.some(([start, end]) => match.index >= start && match.index < end)) continue;
      parts.push(source.slice(at, match.index), match[0]); at = match.index + match[0].length;
    }
    parts.push(source.slice(at));
    return parts.map((part, index) => {
    if (!(index % 2)) return <React.Fragment key={index}>{inline(part, renderInternalLink, undefined, undefined, `${path}.part${index}`, renderFileLink, renderSourceLink)}</React.Fragment>;
    if (part.startsWith("<a ")) return <React.Fragment key={index}>{renderAnchor?.(part.match(/id="([^"]+)"/)[1], path) ?? part}</React.Fragment>;
    const match = part.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    return <React.Fragment key={index}>{renderImage?.(match[2], match[1]) ?? part}</React.Fragment>;
    });
  }
  const parts = String(text).split(inlineTokens);
  return parts.map((part, i) => {
    if (i % 2 === 0) {
      // Display math supplies its own block separation. A preserved separator
      // newline would add an empty line box in the surrounding pre-line prose.
      const before = mathBody(parts[i - 1] || ""), after = mathBody(parts[i + 1] || "");
      if (before?.display && before.latex) part = part.replace(/^[ \t]*\r?\n/, "");
      if (after?.display && after.latex) part = part.replace(/\r?\n[ \t]*$/, "");
      return part;
    }
    const math = mathBody(part);
    if (math) return math.latex ? <MathText key={i} {...math} /> : part;
    if (part.startsWith("**")) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`")) return <code key={i}>{part.slice(1, -1)}</code>;
    const match = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (match && match[2].startsWith("#") && renderInternalLink) return <React.Fragment key={i}>{renderInternalLink(match[2], match[1], `${path}.inline${i}`) ?? match[1]}</React.Fragment>;
    if (match && renderSourceLink) {
      const link = renderSourceLink(match[2], match[1], `${path}.inline${i}`);
      if (link != null) return <React.Fragment key={i}>{link}</React.Fragment>;
    }
    if (match && safeUrl(match[2])) return <a key={i} href={safeUrl(match[2])} target="_blank" rel="noreferrer">{match[1]}</a>;
    if (match && !match[2].startsWith("#") && renderFileLink) {
      const link = renderFileLink(match[2], match[1], `${path}.inline${i}`);
      if (link != null) return <React.Fragment key={i}>{link}</React.Fragment>;
    }
    // Unresolved saved-record citations remain readable without inventing a URL.
    // Their exact targets are preserved in the complete source record.
    if (match && /^(artifact|generation):\/\//i.test(match[2])) return <span key={i} title="Reference retained in the complete source record">{match[1]}</span>;
    return part;
  });
}

const headingTag = (level) => `h${Math.max(1, Math.min(6, level))}`;
function DocumentBlocks({ blocks, headingLevel, renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading, path }) {
  const firstLevel = Math.min(...blocks.filter((block) => block.kind === "heading").map((block) => block.level));
  return blocks.map((block, index) => {
    const blockPath = `${path}.block${index}`;
    if (block.kind === "heading") {
      const level = headingLevel + block.level - firstLevel; const Heading = headingTag(level);
      const children = inline(block.text, renderInternalLink, renderImage, renderAnchor, blockPath, renderFileLink, renderSourceLink);
      const rendered = renderHeading?.({ level, authoredLevel: block.level, text: block.text, path: blockPath, children });
      return rendered != null ? <React.Fragment key={index}>{rendered}</React.Fragment> : <Heading key={index}>{children}</Heading>;
    }
    if (block.kind === "code") return <pre key={index} className="record"><code>{block.text}</code></pre>;
    if (block.kind === "quote") return <blockquote key={index}><DocumentBlocks blocks={block.blocks} headingLevel={headingLevel} path={`${blockPath}.quote`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} /></blockquote>;
    if (block.kind === "list") { const List = block.ordered ? "ol" : "ul"; return <List key={index} start={block.ordered ? block.items[0]?.value : undefined}>{block.items.map((item, j) => <li key={j} value={item.value}><DocumentBlocks blocks={item.blocks} headingLevel={headingLevel} path={`${blockPath}.item${j}`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} /></li>)}</List>; }
    if (block.kind === "table") return <div className="table-scroll" key={index} tabIndex={0} role="region" aria-label="Research table, scroll to inspect all columns"><table><thead><tr>{block.headers.map((cell, j) => <th scope="col" key={j}>{inline(cell, renderInternalLink, undefined, undefined, `${blockPath}.header${j}`, renderFileLink, renderSourceLink)}</th>)}</tr></thead><tbody>{block.rows.map((row, j) => <tr key={j}>{row.map((cell, k) => <td key={k}>{inline(cell, renderInternalLink, undefined, undefined, `${blockPath}.row${j}.cell${k}`, renderFileLink, renderSourceLink)}</td>)}</tr>)}</tbody></table></div>;
    return <p key={index}>{inline(block.text, renderInternalLink, renderImage, renderAnchor, blockPath, renderFileLink, renderSourceLink)}</p>;
  });
}

// Render the common research-document subset without executing authored HTML.
// Original content remains available in the source drawer for unsupported markup.
export function ResearchDocument({ text, headingLevel = 3, renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading, path = "document" }) {
  if (text == null || text === "") return <p className="note">No readable document has been recorded yet.</p>;
  if (Array.isArray(text)) return text.every((item) => typeof item === "string")
    ? <ul className="research-items">{text.map((item, i) => <li key={i}><ResearchDocument text={item} headingLevel={headingLevel} path={`${path}.item${i}`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} /></li>)}</ul>
    : <div className="research-record-list">{text.map((item, i) => <div key={i}><ResearchDocument text={item} headingLevel={headingLevel} path={`${path}.item${i}`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} /></div>)}</div>;
  if (typeof text === "object") {
    const sections = readableSections(text);
    const title = text.title || text.label || text.headline;
    const Heading = headingTag(headingLevel); const sectionLevel = title ? headingLevel + 1 : headingLevel; const SectionHeading = headingTag(sectionLevel);
    return <div className="research-record">{title && <Heading>{inline(title)}</Heading>}
      {text.severity && <span className={`pill ${["major", "blocking", "critical"].includes(text.severity) ? "warn" : "mut"}`}>{humanLabel(text.severity)}</span>}
      {OUTCOMES[text.state] && <Outcome state={text.state} />}
      {text.disposition && <span className="pill mut">{humanLabel(text.disposition)}</span>}
      {text.status && (text.issue || text.issue_id || text.finding) && <span className="pill mut">{humanLabel(text.status)}</span>}
      {text.latex && <MathText latex={text.latex} />}
      {!text.latex && text.symbol && <MathText latex={text.symbol} />}
      {sections.map(({ key, label, body }) => <section key={key}>{label && <SectionHeading>{label}</SectionHeading>}{key === "algorithm_or_update_rule" && Array.isArray(body) ? <ol className="research-algorithm">{body.map((step, index) => <li key={index}><ResearchDocument text={step} headingLevel={sectionLevel + 1} path={`${path}.${key}.step${index}`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} /></li>)}</ol> : <ResearchDocument text={body} headingLevel={label ? sectionLevel + 1 : sectionLevel} path={`${path}.${key}`} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading }} />}</section>)}
      {!sections.length && !text.latex && <p className="note">This record has no readable research account. Its complete structured content is available in the source details.</p>}
    </div>;
  }
  if (typeof text !== "string") return null;
  return <div className="research-document"><DocumentBlocks blocks={researchBlocks(text)} headingLevel={headingLevel} {...{ renderInternalLink, renderImage, renderAnchor, renderFileLink, renderSourceLink, renderHeading, path }} /></div>;
}

export function SourceRef({ reference, onOpen, label = "Open source" }) {
  if (!reference) return null;
  if (!reference.generation_id) return <span className="note">The exact source is not identified in this record.</span>;
  return <button type="button" className="source-link ui-action" data-action="source" data-ui-role="system" title={[humanLabel(reference.family || "Research source"), reference.generation_id].filter(Boolean).join(" · ")} onClick={() => onOpen?.(reference)} disabled={!onOpen}>
    <ActionIcon name="source" />{label}
  </button>;
}

// Derived method-freshness surfaces (backend projection: methods.py). The
// banner explains the state beside the affected work; the pill marks runs.
export function MethodStatusNote({ status, onOpen }) {
  const message = methodUpdateMessage(status);
  if (!message) return null;
  const needsUpdate = status.status === "needs_update";
  return <div className={`note method-status${needsUpdate ? " warn" : ""}`} role={needsUpdate ? "alert" : "status"}>
    <p>{message}</p>
    {needsUpdate && status.change_summary && <p>{status.change_summary}</p>}
    {needsUpdate && <SourceRef reference={status.source_ref} onOpen={onOpen} label="Open the revision source" />}
  </div>;
}

export function MethodStatusPill({ status }) {
  const badge = methodStatusBadge(status);
  return badge ? <span className={`pill ${badge[0]}`}>{badge[1]}</span> : null;
}
