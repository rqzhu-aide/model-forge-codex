import React from "react";
import { hasExactRef, humanLabel } from "../research";
import { ResearchDocument, ResearchLabel, SourceRef } from "./Shared";
import { ActionIcon } from "./Visuals";

const relationshipLabels = { support: "Supporting evidence", counterevidence: "Counterevidence", assumption: "Assumption", strongest_support: "Strongest supporting evidence", strongest_counterevidence: "Strongest counterevidence" };
const sourceFamilyLabels = { method_catalog: "Model proposals", theory_record: "Theoretical account", complete_theory: "Theoretical account", analyst_audit: "Analyst assessment", theory_audit: "Theorist assessment", empirical_evidence_index: "Experimental evidence", empirical_synthesis: "Experimental conclusions", implementation_record: "Implementation and checks", evidence: "Experimental observations", diagnostics: "Experimental diagnostics", protocol: "Evaluation protocol", research_basis: "Research setting" };
function sourceLabel(link) {
  const family = link.generation_ref?.family || link.family;
  return link.label && link.label !== link.identifier && link.label !== family ? link.label : sourceFamilyLabels[family] || (family ? humanLabel(family) : "Recorded source");
}
// Technical-report source_refs are projected with a default support role. That
// projection does not establish a separate assessment of each cited source.
const relationshipLabel = (link, isReport) => isReport && (!link.relationship || link.relationship === "support")
  ? "Cited source" : relationshipLabels[link.relationship] || humanLabel(link.relationship || "Source");
function OutcomeEvidence({ claim, field, title }) {
  const identifiers = claim.scientific_outcome?.[field];
  return identifiers?.length ? <section><h5>{title}</h5><ul>{identifiers.map((identifier) => {
    const link = claim.evidence_links?.find((item) => item.identifier === identifier);
    return <li key={identifier}>{link ? <ResearchDocument text={sourceLabel(link)} /> : <code>{identifier}</code>}</li>;
  })}</ul></section> : null;
}
export default function ClaimTraceability({ records = [], onSource }) {
  return <section className="claim-traceability"><h3>Claims and their sources</h3>{records.length ? records.map((record, index) => {
    const isReport = Boolean(record.report_generation_ref || ["technical_report", "technical_report_candidate"].includes(record.generation_ref?.family));
    const reportRef = record.report_generation_ref || (["technical_report", "technical_report_candidate"].includes(record.generation_ref?.family) ? record.generation_ref : null);
    const reportLink = isReport ? (href, label) => {
      if (!hasExactRef(reportRef) || !onSource) return <span className="note warn">{label} (report source unavailable)</span>;
      let fragment = href.slice(1);
      try { fragment = decodeURIComponent(fragment); } catch { /* Preserve the authored fragment for exact lookup. */ }
      return <a href={`#report-${reportRef.generation_id}-${fragment}`} onClick={(event) => {
        event.preventDefault(); onSource({ ...reportRef, report_fragment: fragment });
      }}>{label}</a>;
    } : undefined;
    return <div key={record.generation_ref?.generation_id || index}>
    {record.manuscript_source_error && <p className="note warn" role="alert">{record.manuscript_source_error}</p>}
    {record.report_generation_ref && <SourceRef reference={record.report_generation_ref} onOpen={onSource} label="Report source for these claims" />}
    {record.manuscript_generation_ref && <SourceRef reference={record.manuscript_generation_ref} onOpen={onSource} label="Manuscript for these claims" />}
    {(record.claims || []).map((claim, claimIndex) => <article className="traceability-claim scientific-block" key={claim.statement_id || claimIndex}>
      <h4>{claim.title || claim.label || `${isReport ? "Report" : "Manuscript"} claim ${claimIndex + 1}`}</h4><ResearchDocument text={claim.text || claim.statement || claim.claim_markdown || "A readable statement was not recorded for this claim."} renderInternalLink={reportLink} />
      {claim.qualification && <section><h5>Qualification</h5><ResearchDocument text={claim.qualification} renderInternalLink={reportLink} /></section>}
      {claim.scope && <section><h5>Scope</h5><ResearchDocument text={claim.scope} renderInternalLink={reportLink} /></section>}
      {claim.scientific_outcome && <ResearchDocument text={claim.scientific_outcome} renderInternalLink={reportLink} />}
      <OutcomeEvidence claim={claim} field="strongest_evidence_ids" title="Strongest recorded evidence" />
      <OutcomeEvidence claim={claim} field="strongest_counterevidence_ids" title="Strongest recorded counterevidence" />
      {(claim.evidence_links || []).filter((link) => link.source_error || !hasExactRef(link.generation_ref) && !link.source_url).map((link, index) => <p className="note warn" key={`unresolved:${index}`}><ResearchLabel text={sourceLabel(link)} />: {link.source_error || "This declared source could not be resolved to an exact saved record."}</p>)}
      {(claim.source_links || []).filter((source) => source.source_error || !source.artifact_url).map((source, index) => <p className="note warn" key={`unavailable:${index}`}><ResearchLabel text={source.label || "Declared claim source"} />: {source.source_error || "A declared claim source location could not be verified."}</p>)}
      {!claim.evidence_links?.length && <p className="note">{isReport ? "No cited source links were recorded for this claim." : "No support or counterevidence links were recorded for this claim."}</p>}
      <details className="research-details traceability-source-details"><summary>Sources and claim identity</summary>
      <div className="traceability-links">{(claim.evidence_links || []).map((link, linkIndex) => <div key={`${link.relationship}:${link.identifier}:${linkIndex}`}><h5>{relationshipLabel(link, isReport)}</h5><ResearchDocument text={sourceLabel(link)} />{link.generation_ref ? <SourceRef reference={link.generation_ref} onOpen={onSource} label="Inspect exact source" /> : link.source_url ? <a className="source-link ui-action" data-action="source" data-ui-role="system" href={link.source_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Inspect exact source</a> : null}{link.identifier && <details className="research-details"><summary>Recorded reference</summary><code>{link.identifier}</code></details>}</div>)}</div>
      {(claim.source_links || []).map((source, sourceIndex) => source.artifact_url ? <div key={sourceIndex}><a className="source-link ui-action" data-action="source" data-ui-role="system" href={source.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{source.label || source.locator || "Open claim source location"}</a></div> : null)}
      {claim.statement_id && <details className="research-details"><summary>Claim identity</summary><code>{claim.statement_id}</code></details>}
      </details>
    </article>)}
    {!record.claims?.length && <p className="note">The saved traceability record has no readable claim entries.</p>}<SourceRef reference={record.generation_ref} onOpen={onSource} label="Complete traceability record" />
  </div>; }) : <p className="note">No claim-to-source account is available. Grouped claim identifiers alone do not establish supporting evidence.</p>}</section>;
}
