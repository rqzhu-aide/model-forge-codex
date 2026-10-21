import React, { useId, useState } from "react";
import { ResearchDocument } from "./Shared";
import { useEmpiricalSourceLink } from "./EmpiricalDocument";

export function bibliographyText(source = {}) {
  return [source.authors?.join(", "), source.year, source.title, source.venue,
    ...(source.identifiers || []).map((item) => `${item.kind}: ${item.value}`)].filter(Boolean).join(". ");
}

export function LiteratureCitation({ label, citation, anchor, onOpen }) {
  const id = useId(); const [open, setOpen] = useState(false);
  const available = citation?.status === "available" && citation.card && citation.entry_ref?.entry_sha256;
  if (!available) return <span className="citation-unavailable" title="The exact cited assessment is unavailable">{label} <span className="note">(reference unavailable)</span></span>;
  return <span className="literature-citation-preview" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
    <button type="button" className="inline-citation" data-reading-anchor={anchor} aria-describedby={open ? id : undefined}
      aria-label={`${label}. Read the exact cited paper assessment`} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}
      onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); setOpen(false); } }}
      onClick={(event) => { setOpen(false); onOpen?.(citation, { anchor, label, element: event.currentTarget }); }}>{label}</button>
    {open && <span id={id} role="tooltip" className="citation-tooltip">{bibliographyText(citation.bibliography)}</span>}
  </span>;
}

export function CitedResearchDocument({ text, basis, section, onOpenCitation, ...props }) {
  const sourceLink = useEmpiricalSourceLink();
  const renderInternalLink = (href, label, occurrence) => {
    if (!href.startsWith("#cite:")) return null;
    const sourceId = href.slice(6); const citation = basis?.citations?.find((item) => item.source_id === sourceId);
    const anchor = `citation:${basis?.generation_ref?.generation_id || "unpublished"}:${section}:${occurrence}`;
    return <LiteratureCitation {...{ label, citation, anchor }} onOpen={(item, origin) => onOpenCitation?.(item, { ...origin, basis })} />;
  };
  return <ResearchDocument {...props} text={text} renderInternalLink={renderInternalLink} renderSourceLink={props.renderSourceLink || sourceLink} />;
}

export function CitedRequestDocument({ item, text, section = "context", onSource, ...props }) {
  return <CitedResearchDocument {...props} text={text} basis={item}
    section={`request:${item.attention_version_id || item.attention_id || item.issue_id}:${section}`}
    onOpenCitation={(citation) => onSource?.({ ...citation.card.generation_ref, entry_pointer: citation.card.entry_pointer })} />;
}
