import React, { useId, useState } from "react";
import { ResearchDocument, SourceRef, MethodStatusNote } from "./Shared";
import { ActionButton, ActionIcon, EmptyState } from "./Visuals";
import { hasExactRef, humanLabel, sameRef, scoped } from "../research";
import { researchDocumentContent, researchDocumentTitle, retainedReviewNote } from "../researchContent";
import TheoryWorkbench from "./TheoryWorkbench";
import { TheoryConditions } from "./TheoryConditions";
import { TheoryAssessmentAccount, TheoryLeadResponses, theorySupportPresentation } from "./TheoryAssessment";
import ClaimTraceability from "./ClaimTraceability";
import { NotationLookup } from "./SharedNotation";

export function PhaseTabs({ tabs, label, heading, initialTab, selectedTab, onTabChange }) {
  const id = useId(); const [picked, setPicked] = useState(initialTab || tabs[0]?.id);
  const selected = tabs.find((tab) => tab.id === (selectedTab || picked)) || tabs[0];
  const choose = (tab) => { setPicked(tab); onTabChange?.(tab); };
  const selectKey = (event, index) => {
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
      : event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : null;
    if (next == null) return;
    event.preventDefault(); choose(tabs[next].id);
    event.currentTarget.parentElement.children[next]?.focus();
  };
  return <><div className={heading ? "card-heading reader-heading" : undefined}>{heading && <h2>{heading}</h2>}<div className="phase-reader-tabs" role="tablist" aria-label={label}>{tabs.map((tab, index) => <button type="button" key={tab.id} role="tab" id={`${id}-${tab.id}`} aria-selected={tab.id === selected?.id} aria-controls={`${id}-panel`} tabIndex={tab.id === selected?.id ? 0 : -1} onClick={() => choose(tab.id)} onKeyDown={(event) => selectKey(event, index)}>{tab.label}</button>)}</div></div>
    <div className={heading ? "body" : undefined}>{selected && <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${selected.id}`} tabIndex={0} className="phase-reader-panel">{selected.content}</div>}</div></>;
}

export function PhaseOverview({ phase, decision, summaries = [], methodLabel, reviewContext, onSource }) {
  const title = phase === "P3" ? "What is established about this model" : "Current report conclusion";
  const accountSource = decision?.conclusion || decision?.headline ? decision : summaries[0];
  const account = decision?.conclusion || decision?.headline || accountSource?.evaluation_markdown || accountSource?.summary_markdown;
  const headline = typeof decision?.headline === "string" && typeof decision?.conclusion === "string"
    && decision.headline.trim() && decision.conclusion.trim() && decision.headline.trim() !== decision.conclusion.trim() ? decision.headline : null;
  const accountLink = accountSource && scientificDocumentLink(accountSource, onSource);
  const decisionLink = decision && scientificDocumentLink(decision, onSource);
  return <section className="card phase-overview" data-card-role="summary"><div className="card-heading"><h2>{title}</h2></div><div className="body">
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    {phase === "P3" && accountSource === decision && account && <p className="note">Research Lead assessment</p>}
    {headline && <div className="phase-overview-headline"><ResearchDocument text={headline} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></div>}
    {account ? <ResearchDocument text={account} renderSourceLink={accountLink} renderFileLink={accountLink} /> : <EmptyState><p className="note">{phase === "P3" ? "No theoretical account has been completed for this model yet." : "No technical report account has been completed for this model yet."}</p></EmptyState>}
    <NotationLookup record={accountSource} onSource={onSource} />
    {decision?.fundamental_contribution && <section><h3>Contribution</h3><ResearchDocument text={decision.fundamental_contribution} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.principal_uncertainty && <section><h3>Main uncertainty</h3><ResearchDocument text={decision.principal_uncertainty} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.principal_risk && <section><h3>Main risk or limitation</h3><ResearchDocument text={decision.principal_risk} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.material_disagreement?.length > 0 && <section><h3>Unresolved differences</h3><ResearchDocument text={decision.material_disagreement} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {phase === "P3" && decision?.what_changed && <section><h3>What changed</h3><ResearchDocument text={decision.what_changed} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.smallest_decisive_result && <section><h3>What remains to be established</h3><ResearchDocument text={decision.smallest_decisive_result} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {phase === "P3" && account && <p className="note">The claims below retain their individual conditions, current assessments and attributed arguments.</p>}
    {phase === "P5" && reviewContext && <ManuscriptReviewStatus context={reviewContext} onSource={onSource} />}
    <SourceRef reference={accountSource?.generation_ref || decision?.generation_ref} onOpen={onSource} />
  </div></section>;
}

function scientificDocumentLink(document, onSource) {
  if ((document.phase || document.generation_ref?.phase) !== "P3") return undefined;
  return (source, label) => {
    if (/^(?:https?:\/\/|\/api\/|#)/i.test(source)) return null;
    const separator = source.indexOf("#");
    const uri = separator < 0 ? source : source.slice(0, separator);
    const fragment = separator < 0 ? "" : source.slice(separator + 1);
    const matches = (document.inline_sources || []).filter((item) => item.uri === uri);
    const target = matches.length === 1 ? matches[0] : null;
    if (target?.source_verified === true && !target.source_error) {
      if (hasExactRef(target.generation_ref) && (!fragment || fragment.startsWith("/"))) {
        const reference = { ...target.generation_ref, ...(fragment ? { entry_pointer: fragment } : {}) };
        return <SourceRef reference={reference} onOpen={onSource} label={label} />;
      }
      if (/^\/api\//.test(target.artifact_url || "")) return <a className="source-link ui-action" data-action="source" data-ui-role="system" href={target.artifact_url + (fragment ? `#${fragment}` : "")} target="_blank" rel="noreferrer"><ActionIcon name="source" />{label}</a>;
    }
    return <span className="note">{label} (source unavailable)</span>;
  };
}

export function ScientificDocuments({ documents = [], onSource, showRecordSource = true, empty = "No account has been recorded for this topic yet." }) {
  return documents.length ? documents.map((doc, index) => {
    const link = scientificDocumentLink(doc, onSource);
    return <article className="scientific-block" key={`${doc.kind}:${doc.generation_ref?.generation_id || index}`}>
    <h3>{researchDocumentTitle(doc) || humanLabel(doc.kind || "Research account")}</h3>
    <NotationLookup record={doc} onSource={onSource} />
    {doc.method_status && <MethodStatusNote status={doc.method_status} onOpen={onSource} />}
    {doc.kind === "review_issue_ledger" && <p className="note">{retainedReviewNote}</p>}
    {doc.review_focus && <details className="research-details"><summary>Review focus and scope</summary><ResearchDocument text={doc.review_focus} />{doc.review_focus_url && <a className="source-link ui-action" href={doc.review_focus_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open frozen review directions</a>}</details>}
    {doc.review_focus_error && <p className="note warn">{doc.review_focus_error}</p>}
    {doc.document_error && <p className="note warn">The full document could not be loaded. {doc.document_error}</p>}
    {["manuscript", "manuscript_candidate"].includes(doc.kind) && <ManuscriptMetadata document={doc} />}
    {doc.primary_artifact_kind === "tex_source" ? <><p className="note">A rendered preview is unavailable for this saved TeX manuscript. Open the source to inspect the exact document.</p>{doc.source_text && <details className="research-details manuscript-tex-source"><summary>Inspect TeX source</summary><pre className="record">{doc.source_text}</pre></details>}</> : doc.primary_artifact_kind === "pdf" && doc.primary_artifact_url ? <iframe className="manuscript-pdf-preview" title={`${researchDocumentTitle(doc) || "Manuscript"} PDF preview`} src={doc.primary_artifact_url} loading="lazy" /> : <ResearchDocument text={researchDocumentContent(doc)} renderSourceLink={link} renderFileLink={link} />}
    {doc.kind === "analyst_audit" && ["pdf", "tex_source"].includes(doc.primary_artifact_kind) && <ResearchDocument text={researchDocumentContent(doc)} renderSourceLink={link} renderFileLink={link} />}
    <div className="btnrow">{showRecordSource && <SourceRef reference={doc.generation_ref} onOpen={onSource} />}{doc.primary_artifact_url && <a className="source-link ui-action" href={doc.primary_artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{doc.primary_artifact_kind === "tex_source" ? "Open TeX source" : doc.primary_artifact_media_type === "application/pdf" || doc.primary_artifact_kind === "pdf" ? "Open manuscript PDF" : "Open original document"}</a>}</div>
    {doc.supplementary_artifacts?.length > 0 && <details className="research-details manuscript-supplements"><summary>Sources and supplements</summary>{doc.supplementary_artifacts.map((artifact, index) => <div key={index}>{artifact.artifact_url ? <a className="source-link ui-action" href={artifact.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{artifact.label || artifact.title || artifact.path || artifact.artifact_id || "Open supplement"}</a> : <p className="note warn">{artifact.label || artifact.title || artifact.path || artifact.artifact_id || "Supplement"}: {artifact.source_error || "This retained supplement is unavailable."}</p>}</div>)}</details>}
  </article>;
  }) : <p className="note">{empty}</p>;
}

export function ManuscriptMetadata({ document }) {
  const record = document.structured || document;
  return <dl className="manuscript-metadata">{record.manuscript_kind && <div><dt>Draft</dt><dd>{({ assembly_candidate: "Assembled manuscript", revised_candidate: "Revised manuscript" })[record.manuscript_kind] || humanLabel(record.manuscript_kind)}</dd></div>}{record.venue_length && <div><dt>Manuscript scope</dt><dd>{({ journal: "Journal article", conference: "Conference paper" })[record.venue_length] || record.venue_length}</dd></div>}{record.target_audience && <div><dt>Intended readers</dt><dd>{record.target_audience}</dd></div>}{record.sections_present?.length > 0 && <div><dt>Included sections</dt><dd>{record.sections_present.map(humanLabel).join(", ")}</dd></div>}{(record.method_identity?.version || document.method_identity?.version) && <div><dt>Model version</dt><dd>{record.method_identity?.version || document.method_identity.version}</dd></div>}{document.published_at && <div><dt>Saved publication</dt><dd>{document.published_at.slice(0, 16).replace("T", " ")}</dd></div>}</dl>;
}

export function TheoryStatement({ statement, reference, onSource, proofSources }) {
  return <>{statement.status && <p className="note">Statement status: {humanLabel(statement.status)}</p>}<ResearchDocument text={statement} />
    <TheoryConditions statement={statement} />
    <TheoryAssessmentAccount statement={statement} onSource={onSource} proofSources={proofSources} />
    <SourceRef reference={reference} onOpen={onSource} />
  </>;
}

export function TheoryReading({ documents = [], assessments, onSource, reading = {}, onReadingChange, ...props }) {
  const map = scoped(props.claimMaps, props.branch, "P3")[0];
  const reference = map?.theory_generation_ref || map?.generation_ref;
  const canExplain = hasExactRef(reference) && ["theory_record", "complete_theory"].includes(reference.family);
  const claims = map?.claims || [];
  const proofSources = documents.flatMap((doc) => doc.inline_sources || []);
  return <section className="card" data-card-role="research"><PhaseTabs heading="Claims, assumptions and proofs" label="Theoretical detail" selectedTab={reading.tab} onTabChange={(tab) => onReadingChange?.({ tab })} tabs={[
    { id: "claims", label: "Claims", content: <TheoryWorkbench {...props} proofSources={proofSources} reading={reading} onReadingChange={onReadingChange} onSource={onSource} embedded /> },
    { id: "assumptions", label: "Assumptions", content: (map?.assumptions || []).length ? map.assumptions.map((assumption, index) => <article className="scientific-block" key={assumption.assumption_id || index}><TheoryStatement statement={assumption} reference={reference} onSource={onSource} proofSources={proofSources} />{props.onAssumptionConversation && canExplain && <ActionButton action="ask" uiRole="research" onClick={() => props.onAssumptionConversation({ ...reference, kind: "assumption", object_id: assumption.assumption_id || assumption.id, label: assumption.label || assumption.title, statement: assumption.text || assumption.statement, latex: assumption.latex })}>Explain this assumption</ActionButton>}</article>) : <p className="note">No linked assumptions have been recorded yet.</p> },
    { id: "arguments", label: "Arguments", content: <>{claims.map((claim, index) => <article className="scientific-block" key={claim.statement_id || claim.id || index}>{!theorySupportPresentation(claim).reassessed && <p className="note">{claim.proof_status ? `${humanLabel(claim.proof_status)} proof` : "Proof status not recorded"}</p>}<TheoryStatement statement={claim} reference={reference} onSource={onSource} proofSources={proofSources} /></article>)}<ScientificDocuments documents={documents.filter((doc) => !/audit|review|falsification/.test(doc.kind || ""))} onSource={onSource} empty={claims.length ? "The claims above retain their arguments, remaining obligations, and available proof sources." : "No arguments have been recorded yet."} /></> },
    { id: "review", label: "Review", content: <><ScientificDocuments documents={documents.filter((doc) => /audit|review|falsification/.test(doc.kind || ""))} onSource={onSource} empty="No separate review account is available yet." /><TheoryLeadResponses responses={map?.issue_dispositions} onSource={onSource} />{assessments}</> },
  ]} /></section>;
}

export function ManuscriptReviewStatus({ context, onSource }) {
  const record = Array.isArray(context) ? context[0] : context;
  const message = { not_reviewed: "This manuscript has not received an independent review.", reviewed: "The independent review assessed this exact draft.", revised_after_review: "This draft was revised in response to an independent review of the earlier draft linked below. The present revision has not itself been independently reviewed.", earlier_draft_review: "The available reviews concern an earlier draft. They do not establish that the current draft has been independently reviewed.", reviewed_draft_unavailable: "An independent review is recorded, but the draft it assessed could not be identified from the available sources." }[record?.status];
  return <div className="manuscript-review-status"><p className="note">{message || record?.message || "I can't confirm an independent review of this draft."}</p>{record?.reviewed_manuscript_ref && <SourceRef reference={record.reviewed_manuscript_ref} onOpen={onSource} label="Read the reviewed draft" />}</div>;
}

export function ManuscriptReading({ documents = [], traceability = [], decision, reviewContext, onSource, initialTab, selectedTab, onTabChange }) {
  const manuscript = documents.filter((doc) => ["manuscript", "manuscript_candidate"].includes(doc.kind));
  const reviews = documents.filter((doc) => /review|audit/.test(doc.kind || ""));
  const changes = documents.filter((doc) => /revision|change|reconciliation/.test(doc.kind || ""));
  const supporting = documents.filter((doc) => !manuscript.includes(doc) && !reviews.includes(doc) && !changes.includes(doc) && !(traceability.length && doc.kind === "claim_traceability"));
  const context = Array.isArray(reviewContext) ? reviewContext[0] : reviewContext;
  const reviewDraft = (doc) => doc.reviewed_manuscript_ref || (doc.generation_ref?.run_id && doc.generation_ref.run_id === context?.review_run_id ? context.reviewed_manuscript_ref : null);
  return <section className="card" data-card-role="research"><PhaseTabs heading="Manuscript and reviews" label="Paper detail" initialTab={initialTab} selectedTab={selectedTab} onTabChange={onTabChange} tabs={[
    { id: "manuscript", label: "Manuscript", content: <ScientificDocuments documents={manuscript} onSource={onSource} empty="No paper has been drafted for this model yet." /> },
    { id: "evidence", label: "Supporting evidence", content: <><ClaimTraceability records={traceability} onSource={onSource} /><ScientificDocuments documents={supporting} onSource={onSource} empty={traceability.length ? "" : "The manuscript and its cited theory and experiments retain their original sources."} /></> },
    { id: "reviews", label: "Reviews", content: reviews.length ? reviews.map((doc, index) => { const draft = reviewDraft(doc); return <section key={`${doc.kind}:${index}`} className="manuscript-review-draft">{draft ? <>{!sameRef(draft, context?.current_manuscript_ref || manuscript[0]?.generation_ref) && <p className="note">This assessment concerns the earlier draft linked here. It does not establish an assessment of the current revision.</p>}<SourceRef reference={draft} onOpen={onSource} label="Draft assessed by this review" /></> : !/issue/.test(doc.kind || "") && <p className="note">The exact draft assessed by this review is not identified in the available records.</p>}<ScientificDocuments documents={[doc]} onSource={onSource} /></section>; }) : <p className="note">No independent reviews have been recorded yet.</p> },
    { id: "changes", label: "Changes", content: <>{decision?.what_changed && <section className="scientific-block"><h3>What changed</h3><ResearchDocument text={decision.what_changed} /><SourceRef reference={decision.generation_ref && { ...decision.generation_ref, entry_pointer: "/what_changed" }} onOpen={onSource} label="Change account source" /></section>}{changes.length > 0 ? <ScientificDocuments documents={changes} onSource={onSource} /> : !decision?.what_changed && <p className="note">No revision account has been recorded yet.</p>}</> },
  ]} /></section>;
}
