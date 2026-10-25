import React, { useId, useState } from "react";
import { humanLabel } from "../research";
import { buildFrameworkGraph, graphTitleLines, landscapeRecords, paperReviewFindings, resolveLandscapeEntry } from "../literatureLandscape";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";

const roleLabel = (role) => ({ research_lead: "Research Lead", theorist: "Theorist", data_analyst: "Data Analyst" }[role] || "Member");
const supportLabel = { source_supported: "Source support recorded", partially_supported: "Partial source support", disputed: "Disputed", unverified: "Not verified" };
const findingLabel = { source_checked: "Source checked", corrected: "Correction recorded", disputed: "Disputed", not_checked: "Not checked" };
const groups = [["framework", "Frameworks"], ["variant", "Variants"], ["relationship", "Relationships"], ["algorithm", "Existing algorithm families"]];
const activate = (event, callback) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); callback(); } };

export function ScientificReviewFindings({ review, card, compact = false }) {
  const findings = paperReviewFindings(review, card);
  if (!findings.length) return null;
  const content = findings.map(({ finding, earlier }) => <div className={`scientific-finding ${["disputed", "not_checked"].includes(finding.status) ? "needs-attention" : ""}`} key={finding.finding_id}>
    <p className="note review-status">{findingLabel[finding.status] || humanLabel(finding.status)}{earlier ? " · Earlier entry version" : " · This entry version"}</p>
    <ResearchDocument text={finding.assessment_markdown} />
    {finding.evidence_locations?.length > 0 && <details className="research-details"><summary>Review evidence locations</summary><ResearchDocument text={finding.evidence_locations} /></details>}
  </div>);
  return compact ? <details className="research-details scientific-findings"><summary>Lead review: {[...new Set(findings.map(({ finding }) => findingLabel[finding.status] || humanLabel(finding.status)))].join("; ")}{findings.every((item) => item.earlier) ? " · Earlier entry version" : ""}</summary>{content}</details> : <div className="scientific-findings"><h4>Research Lead · review of this entry</h4>{content}</div>;
}

function SupportingEntries({ references = [], sources, review, onEvidence }) {
  if (!references.length) return null;
  return <details className="research-details framework-evidence"><summary>Supporting paper entries ({references.length})</summary><ul>{references.map((reference, index) => {
    const match = resolveLandscapeEntry(sources, reference);
    return <li key={`${reference.role}:${reference.entry_id}:${reference.entry_sha256 || index}`}>
      {match ? <><ActionButton action="details" variant="link" onClick={() => onEvidence?.(match)} disabled={!onEvidence}>{match.source.title || "Open paper entry"}</ActionButton><span className="note">{roleLabel(reference.role)}{match.historyIndex != null ? " · Earlier version referenced" : match.card.lead_revision ? " · Revised by Research Lead" : ""}</span><ScientificReviewFindings review={review} card={match.card} compact /></> : <p className="note warn">{roleLabel(reference.role)}: the exact supporting entry is unavailable in this published library. Open the lead-authored record for its reference.</p>}
    </li>;
  })}</ul></details>;
}

function FrameworkGraph({ landscape, selectedId, onSelect }) {
  const graph = buildFrameworkGraph(landscape); const id = useId().replaceAll(":", "");
  if (!graph.nodes.length) return null;
  return <div className="framework-map-region" role="group" aria-label="Framework relationship map" tabIndex={0}>
    <svg className="framework-map" viewBox={`0 0 ${graph.width} ${graph.height}`} width={graph.width} height={graph.height} role="group" aria-label="Select a formulation, algorithm family, or numbered relationship">
      <defs><marker id={`${id}-arrow`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
      {graph.edges.map((edge) => <g key={edge.id} role="button" tabIndex={0} aria-label={`Relationship ${edge.index}: ${edge.record.title}`} aria-pressed={selectedId === edge.id} className={`framework-edge${selectedId === edge.id ? " selected" : ""}`} onClick={() => onSelect(edge.id)} onKeyDown={(event) => activate(event, () => onSelect(edge.id))}>
        <title>{edge.record.title}</title><path className="framework-edge-hit" d={edge.path} /><path className="framework-edge-line" d={edge.path} markerEnd={`url(#${id}-arrow)`} /><circle cx={edge.labelX} cy={edge.labelY} r="13" /><text x={edge.labelX} y={edge.labelY + 4} textAnchor="middle">{edge.index}</text>
      </g>)}
      {graph.nodes.map((node) => <g key={node.id} role="button" tabIndex={0} aria-label={`${node.kind === "algorithm" ? "Existing algorithm family" : humanLabel(node.kind)}: ${node.record.title}`} aria-pressed={selectedId === node.id} className={`framework-node ${node.kind}${selectedId === node.id ? " selected" : ""}`} onClick={() => onSelect(node.id)} onKeyDown={(event) => activate(event, () => onSelect(node.id))}>
        <title>{node.record.title}</title><rect x={node.x} y={node.y} width={node.width} height={node.height} rx={node.kind === "algorithm" ? "16" : "7"} /><text className="framework-node-kind" x={node.x + 13} y={node.y + 18}>{node.kind === "algorithm" ? "ALGORITHM FAMILY" : node.kind.toUpperCase()}</text>{graphTitleLines(node.record.title).map((line, index) => <text key={index} className="framework-node-title" x={node.x + 13} y={node.y + 39 + index * 18}>{line}</text>)}
      </g>)}
    </svg>
  </div>;
}

export function LandscapeRecord({ selection, landscape, sources = [], review, basisReference, onSelect, onEvidence, onSource, focusRef }) {
  if (!selection) return null;
  const { record, kind, id } = selection; const all = landscapeRecords(landscape);
  const title = (recordId) => all.find((item) => item.id === recordId)?.record.title || "Unavailable formulation";
  const related = kind === "framework" ? all.filter((item) => item.kind === "variant" && item.record.framework_id === id || item.kind === "algorithm" && item.record.framework_ids?.includes(id)) : [];
  const field = { framework: "frameworks", variant: "variants", relationship: "relationships", algorithm: "algorithm_families" }[kind];
  const index = (landscape[field] || []).indexOf(record);
  return <article className="framework-inspector" ref={focusRef} tabIndex={-1} aria-label={`Selected ${kind === "algorithm" ? "algorithm family" : kind}`}>
    <h3>{record.title}</h3><p className="note framework-inspector-meta">{kind === "algorithm" ? "Existing algorithm family" : humanLabel(kind)} · Research Lead</p>
    {kind === "relationship" && <p className="framework-connection"><ActionButton action="details" variant="link" onClick={() => onSelect?.(record.from_id)}>{title(record.from_id)}</ActionButton><span aria-hidden="true"> → </span><span className="visually-hidden"> to </span><ActionButton action="details" variant="link" onClick={() => onSelect?.(record.to_id)}>{title(record.to_id)}</ActionButton><span className="note">{humanLabel(record.relationship_type)}</span></p>}
    {kind === "variant" && <p className="note">Variant of <ActionButton action="details" variant="link" onClick={() => onSelect?.(record.framework_id)}>{title(record.framework_id)}</ActionButton></p>}
    {kind === "algorithm" && record.framework_ids?.length > 0 && <p className="framework-connection"><span className="note">Addresses</span>{record.framework_ids.map((frameworkId) => <ActionButton action="details" variant="link" key={frameworkId} onClick={() => onSelect?.(frameworkId)}>{title(frameworkId)}</ActionButton>)}</p>}
    {record.support_status && <p className={`note framework-support ${record.support_status !== "source_supported" ? "warn" : ""}`}>Lead's source assessment of this {kind === "algorithm" ? "algorithm family" : kind}: {supportLabel[record.support_status] || humanLabel(record.support_status)}.</p>}
    {record.formulation_markdown && <><h4>{kind === "relationship" ? "Mathematical relationship" : "Mathematical formulation"}</h4><ResearchDocument text={record.formulation_markdown} /></>}
    {record.assumptions_markdown && <><h4>{kind === "relationship" ? "Conditions" : "Assumptions"}</h4><ResearchDocument text={record.assumptions_markdown} /></>}
    {record.changes_markdown && <><h4>What changes mathematically</h4><ResearchDocument text={record.changes_markdown} /></>}
    {record.explanation_markdown && <><h4>Interpretation</h4><ResearchDocument text={record.explanation_markdown} /></>}
    {record.consequences_markdown && <><h4>Consequences</h4><ResearchDocument text={record.consequences_markdown} /></>}
    {record.limitations?.length > 0 && <div className="framework-limitations"><h4>Limits and unresolved questions</h4><ResearchDocument text={record.limitations} /></div>}
    {(record.relevance_markdown || record.computational_requirements_markdown || related.length > 0) && <details className="research-details framework-further-details"><summary>Relevance and related approaches</summary>
      {record.relevance_markdown && <><h4>Relevance to this setting</h4><ResearchDocument text={record.relevance_markdown} /></>}
      {record.computational_requirements_markdown && <><h4>Information and computational requirements</h4><ResearchDocument text={record.computational_requirements_markdown} /></>}
      {related.length > 0 && <div className="framework-related"><h4>Variants and existing algorithm families</h4><ul>{related.map((item) => <li key={item.id}><ActionButton action="details" variant="link" onClick={() => onSelect?.(item.id)}>{item.record.title}</ActionButton><span className="note">{item.kind === "algorithm" ? "Existing algorithm family" : "Variant"}</span></li>)}</ul></div>}
    </details>}
    <SupportingEntries references={record.entry_refs} sources={sources} review={review} onEvidence={onEvidence ? (match) => onEvidence(match, selection) : undefined} />
    <SourceRef reference={basisReference} onOpen={onSource ? (reference) => onSource({ ...reference, entry_pointer: `/landscape/${field}/${index}` }) : undefined} label="Lead-authored record" />
  </article>;
}

export default function FrameworkLandscape({ basis, sources = [], selectedId, onSelect, onEvidence, onSource, focusRef, embedded = false }) {
  const [localSelectedId, setLocalSelectedId] = useState(""); const id = useId();
  const landscape = basis?.landscape || {}; const records = landscapeRecords(landscape);
  const currentId = selectedId === undefined ? localSelectedId : selectedId;
  const selection = records.find((item) => item.id === currentId) || null;
  const select = (recordId) => { if (selectedId === undefined) setLocalSelectedId(recordId); onSelect?.(recordId); };
  const Heading = embedded ? "h3" : "h2";
  return <section className={embedded ? "framework-landscape embedded-science" : "card framework-landscape"} data-card-role="research" aria-labelledby={`${id}-heading`}><div className={embedded ? "section-heading" : "card-heading"}><Heading id={`${id}-heading`}>Frameworks and relationships</Heading></div><div className={embedded ? "framework-content" : "body"}>
    {records.length > 0 ? <>
      <div className="framework-navigation">
        <FrameworkGraph landscape={landscape} selectedId={selection?.id} onSelect={select} />
        {landscape.relationships?.length > 0 && <p className="note framework-map-note">Numbered arrows open the lead's recorded relationships and conditions.</p>}
        <div className="field framework-selector"><label htmlFor={`${id}-record`}>Explore a framework or relationship</label><select id={`${id}-record`} value={selection?.id || ""} onChange={(event) => select(event.target.value)}>
          <option value="">Choose a formulation, relationship, or algorithm family</option>
          {groups.map(([kind, label]) => {
            const items = records.filter((item) => item.kind === kind); if (!items.length) return null;
            return <optgroup key={kind} label={`${label} (${items.length})`}>{items.map((item, index) => <option key={item.id} value={item.id}>{kind === "relationship" ? `${index + 1}. ` : ""}{item.record.title}</option>)}</optgroup>;
          })}
        </select></div>
      </div>
      {selection ? <LandscapeRecord selection={selection} landscape={landscape} sources={sources} review={basis?.scientific_review} basisReference={basis?.generation_ref} onSelect={select} onEvidence={onEvidence} onSource={onSource} focusRef={focusRef} /> : <p className="note framework-empty">Select a map item or use the dropdown to read its mathematical formulation and evidence.</p>}
    </> : <p className="note framework-empty">No framework map has been published yet. Available paper assessments remain in Papers.</p>}
  </div></section>;
}
