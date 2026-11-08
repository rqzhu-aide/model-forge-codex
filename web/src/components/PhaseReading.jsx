import React, { useId, useState } from "react";
import { ResearchDocument, SourceRef, MethodStatusNote } from "./Shared";
import { ActionButton, ActionIcon, EmptyState } from "./Visuals";
import { buildTheoryGraph, hasExactRef, humanLabel, sameRef, scoped } from "../research";
import { researchDocumentContent, researchDocumentTitle, retainedReviewNote } from "../researchContent";
import TheoryWorkbench from "./TheoryWorkbench";
import { TheoryConditions } from "./TheoryConditions";
import { TheoryAssessmentAccount, TheoryLeadResponses, TheorySupportBadge, theorySupportPresentation } from "./TheoryAssessment";
import { NotationLookup } from "./SharedNotation";
import { hasSharedNotation } from "../sharedNotation";
import ResearchCardLayout from "./ResearchCardLayout";
import { ReadingDocumentButton } from "./MethodReadingWindow";
import { readingDocumentKey, useReadingHost } from "./ReadingHost";
import { researchReadingSize } from "../readingSize";
import ReportDeliveryStatus from "./ReportDeliveryStatus";

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

export function PhaseOverview({ decision, summaries = [], methodLabel, onSource, onReadTheory }) {
  const host = useReadingHost();
  const accountSource = decision?.conclusion || decision?.headline ? decision : summaries[0];
  const account = decision?.conclusion || decision?.headline || accountSource?.evaluation_markdown || accountSource?.summary_markdown;
  const headline = typeof decision?.headline === "string" && typeof decision?.conclusion === "string"
    && decision.headline.trim() && decision.conclusion.trim() && decision.headline.trim() !== decision.conclusion.trim() ? decision.headline : null;
  const accountLink = accountSource && scientificDocumentLink(accountSource, onSource);
  const decisionLink = decision && scientificDocumentLink(decision, onSource);
  const whatChanged = decision?.what_changed ? { text: decision.what_changed, size: researchReadingSize(decision.what_changed) } : null;
  const whatChangedReader = whatChanged && account && host.scope.projectId ? <ReadingDocumentButton title="What changed" size={whatChanged.size} onClick={(event) => host.open({
    key: readingDocumentKey(host.scope, "theory-what-changed", [decision.generation_ref || decision.what_changed]), title: "What changed", subtitle: methodLabel ? `${methodLabel} · Research Lead` : "Research Lead", size: whatChanged.size,
    body: <><ResearchDocument text={decision.what_changed} renderSourceLink={decisionLink} renderFileLink={decisionLink} />{decision.generation_ref && <div className="p2-reader-sources"><SourceRef reference={decision.generation_ref} onOpen={onSource} label="Lead assessment source" /></div>}</> }, event.currentTarget)} /> : null;
  const actions = account && onReadTheory ? <section><h3>Explore the theory</h3><div className="btnrow">
      {[["claims", "Claims"], ["assumptions", "Assumptions"], ["arguments", "Arguments and proofs"], ["review", "Scientific review"]].map(([tab, label]) => <ActionButton key={tab} action="details" onClick={() => onReadTheory(tab)}>{label}</ActionButton>)}
    </div></section> : null;
  const resources = account && (hasSharedNotation(accountSource) || accountSource?.generation_ref || decision?.generation_ref || whatChangedReader) ? <>
    {hasSharedNotation(accountSource) && <section><h3>Notation</h3><p className="note">Not sure what a symbol means? Open the notation table.</p><NotationLookup record={accountSource} onSource={onSource} /></section>}
    {(accountSource?.generation_ref || decision?.generation_ref || whatChangedReader) && <section><h3>Supporting reading</h3>{whatChangedReader && <div className="p2-reading-links">{whatChangedReader}</div>}{(accountSource?.generation_ref || decision?.generation_ref) && <SourceRef reference={accountSource?.generation_ref || decision?.generation_ref} onOpen={onSource} />}</section>}
  </> : null;
  return <section className="card phase-overview" data-card-role="summary"><div className="card-heading"><h2>What is established about this model</h2></div><div className="body">
    <ResearchCardLayout actions={actions} resources={resources} actionsLabel="Theory actions" label="Theory supporting reading">
    {methodLabel && <p className="note">Model: {methodLabel}</p>}
    {accountSource === decision && account && <p className="note">Research Lead assessment</p>}
    {headline && <div className="phase-overview-headline"><ResearchDocument text={headline} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></div>}
    {account ? <ResearchDocument text={account} renderSourceLink={accountLink} renderFileLink={accountLink} /> : <EmptyState><p className="note">No theoretical account has been completed for this model yet.</p></EmptyState>}
    {decision?.fundamental_contribution && <section><h3>What this analysis adds</h3><ResearchDocument text={decision.fundamental_contribution} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.principal_uncertainty && <section><h3>What remains uncertain</h3><ResearchDocument text={decision.principal_uncertainty} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.principal_risk && <section><h3>Main risk or limitation</h3><ResearchDocument text={decision.principal_risk} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.material_disagreement?.length > 0 && <section><h3>Unresolved differences</h3><ResearchDocument text={decision.material_disagreement} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {whatChanged && !whatChangedReader && <section><h3>What changed</h3><ResearchDocument text={decision.what_changed} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {decision?.smallest_decisive_result && <section><h3>Next useful step</h3><ResearchDocument text={decision.smallest_decisive_result} renderSourceLink={decisionLink} renderFileLink={decisionLink} /></section>}
    {account && <p className="note">The claims below retain their individual conditions, current assessments and attributed arguments.</p>}
    </ResearchCardLayout>
    {!resources && <><NotationLookup record={accountSource} onSource={onSource} /><SourceRef reference={accountSource?.generation_ref || decision?.generation_ref} onOpen={onSource} /></>}
  </div></section>;
}

export function scientificDocumentLink(document, onSource) {
  if (!["P3", "P4"].includes(document.phase || document.generation_ref?.phase)) return undefined;
  return (source, label) => {
    if (/^(?:https?:\/\/|\/api\/|#)/i.test(source)) return null;
    const separator = source.indexOf("#");
    const uri = separator < 0 ? source : source.slice(0, separator);
    const fragment = separator < 0 ? "" : source.slice(separator + 1);
    const matches = (document.inline_sources || []).filter((item) => item.uri === uri);
    const target = matches.length === 1 ? matches[0] : null;
    if (target?.source_verified === true && !target.source_error) {
      const exhibit = target.exhibit_ref;
      const origin = document.generation_ref;
      if (!fragment && origin?.phase === "P4" && hasExactRef(exhibit) && exhibit.phase === "P4" && exhibit.family === "exhibits"
        && /^\/(0|[1-9]\d*)$/.test(exhibit.entry_pointer || "")
        && exhibit.run_id === target.producing_run_id
        && ["branch", "run_id", "package_id"].every(key => origin?.[key] && exhibit[key] === origin[key])) {
        return <SourceRef reference={exhibit} onOpen={onSource} label={label} />;
      }
      const namedSource = target.generation_ref?.phase === "P3" && /^[A-Za-z0-9_.:-]+$/.test(fragment)
        && ["text/markdown", "text/plain"].includes(target.media_type?.split(";")[0]);
      if (hasExactRef(target.generation_ref) && (!fragment || fragment.startsWith("/") || namedSource)) {
        const reference = { ...target.generation_ref, ...(fragment ? namedSource ? { source_locator: `#${fragment}` } : { entry_pointer: fragment } : {}) };
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
    <ReportDeliveryStatus state={doc.delivery_state} onSource={onSource} includeHistory />
    <NotationLookup record={doc} onSource={onSource} />
    {doc.method_status && <MethodStatusNote status={doc.method_status} onOpen={onSource} />}
    {doc.kind === "review_issue_ledger" && <p className="note">{retainedReviewNote}</p>}
    {doc.review_focus && <details className="research-details"><summary>Review focus and scope</summary><ResearchDocument text={doc.review_focus} />{doc.review_focus_url && <a className="source-link ui-action" href={doc.review_focus_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open frozen review directions</a>}</details>}
    {doc.review_focus_error && <p className="note warn">{doc.review_focus_error}</p>}
    {doc.document_error && <p className="note warn">The full document could not be loaded. {doc.document_error}</p>}
    {doc.kind === "analyst_synthesis" && doc.lead_reporting_notes?.producer_role === "research_lead" && doc.lead_reporting_notes.notes?.length > 0 && <section className="scientific-passage">
      <h4>Research Lead reporting notes for this evaluation</h4>
      <p className="note">The Research Lead recorded these notes separately from the Analyst account below.</p>
      {doc.lead_reporting_notes.notes.map((note, index) => <div key={index}><ResearchDocument text={note.text} /><SourceRef reference={note.generation_ref} onOpen={onSource} label="Reporting note source" /></div>)}
    </section>}
    <ResearchDocument text={researchDocumentContent(doc)} renderSourceLink={link} renderFileLink={link}
      renderAnchor={(doc.phase || doc.generation_ref?.phase) === "P3" ? name => <span data-source-anchor={name} /> : undefined} />
    {doc.delivery_history?.length > 0 && <details className="research-details"><summary>Recorded concern and scientific context</summary><ResearchDocument text={doc.delivery_history} /></details>}
    <div className="btnrow">{showRecordSource && <SourceRef reference={doc.generation_ref} onOpen={onSource} />}{doc.primary_artifact_url && <a className="source-link ui-action" href={doc.primary_artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />Open original document</a>}</div>
    {doc.supplementary_artifacts?.length > 0 && <details className="research-details document-supplements"><summary>Sources and supplements</summary>{doc.supplementary_artifacts.map((artifact, index) => <div key={index}>{artifact.artifact_url ? <a className="source-link ui-action" href={artifact.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{artifact.label || artifact.title || artifact.path || artifact.artifact_id || "Open supplement"}</a> : <p className="note warn">{artifact.label || artifact.title || artifact.path || artifact.artifact_id || "Supplement"}: {artifact.source_error || "This retained supplement is unavailable."}</p>}</div>)}</details>}
  </article>;
  }) : <p className="note">{empty}</p>;
}

export function TheoryStatement({ statement, reference, onSource, proofSources }) {
  return <>{statement.status && <p className="note">Statement status: {humanLabel(statement.status)}</p>}<ResearchDocument text={statement} />
    <TheoryConditions statement={statement} />
    <TheoryAssessmentAccount statement={statement} onSource={onSource} proofSources={proofSources} />
    <SourceRef reference={reference} onOpen={onSource} />
  </>;
}

// A graph projection alone cannot establish the complete theory's scope. Only
// compact an authoritative map beside its exact, readable structured record.
export function exactArgumentsDocument(map, documents = []) {
  const reference = map?.theory_generation_ref || map?.generation_ref;
  if (map?.authoritative !== true || !hasExactRef(reference) || !["theory_record", "complete_theory"].includes(reference.family)) return null;
  const matches = documents.filter(doc => ["theory_record", "complete_theory"].includes(doc.kind)
    && hasExactRef(doc.generation_ref) && sameRef(reference, doc.generation_ref)
    && ["run_id", "package_id"].every(key => !reference[key] || !doc.generation_ref[key] || reference[key] === doc.generation_ref[key]));
  if (matches.length !== 1) return null;
  const document = matches[0]; const theory = document.structured;
  if (!theory || !Array.isArray(theory.statements) || !Array.isArray(theory.assumptions)
    || !map.claims?.length || !map.claims.every(claim => claim.statement_id)
    || new Set(map.claims.map(claim => claim.statement_id)).size !== map.claims.length
    || theory.statements.length !== map.claims.length
    || !theory.statements.every(statement => map.claims.some(claim => claim.statement_id === statement.statement_id))) return null;
  return document;
}

export function TheoryArguments({ map, documents = [], glossaries = [], branch, selected, onSelect, onSource, proofSources }) {
  const claims = map?.claims || []; const reference = map?.theory_generation_ref || map?.generation_ref;
  const complete = onSource && onSelect ? exactArgumentsDocument(map, documents) : null;
  if (!complete) return <>{map?.source_warning && <p className="note warn">{map.source_warning}</p>}{claims.map((claim, index) => <article className="scientific-block" key={claim.statement_id || claim.id || index}>{!theorySupportPresentation(claim).reassessed && <p className="note">{claim.proof_status ? `${humanLabel(claim.proof_status)} proof` : "Proof status not recorded"}</p>}<TheoryStatement statement={claim} reference={reference} onSource={onSource} proofSources={proofSources} /></article>)}<ScientificDocuments {...{ documents, onSource }} empty={claims.length ? "The claims above retain their arguments, remaining obligations, and available proof sources." : "No arguments have been recorded yet."} /></>;
  const theory = complete.structured;
  const assumptions = theory.assumptions.map(assumption => map.assumptions?.find(item => (item.assumption_id || item.id) === assumption.assumption_id) || assumption);
  const graph = buildTheoryGraph(map, scoped(glossaries, branch, "P3")[0]?.glossary || {}, assumptions);
  // Keep all supported record-level fields, including older readable fields.
  // Only registered statements and assumptions move into the selection below.
  const { statements: _statements, assumptions: _assumptions, ...context } = theory;
  return <>
    {map.source_warning && <p className="note warn">{map.source_warning}</p>}
    <ResearchDocument text={context} />
    {theory.empirical_implications?.length > 0 && <section className="scientific-passage"><h3>Empirical implications</h3>{theory.empirical_implications.map((implication, index) => <article key={implication.implication_id || index} className="scientific-block">
      <ResearchDocument text={implication} />
      {[["conditions", "Conditions"], ["observable_or_metric", "Observable or metric"], ["expected_pattern", "Expected pattern"], ["falsifying_result", "What would falsify this implication"]].map(([key, label]) => implication[key] && <section key={key}><h4>{label}</h4><ResearchDocument text={implication[key]} /></section>)}
    </article>)}</section>}
    {complete.method_status && <MethodStatusNote status={complete.method_status} onOpen={onSource} />}
    {complete.document_error && <p className="note warn">The full document could not be loaded. {complete.document_error}</p>}
    {claims.map(claim => {
      const assumptionIds = claim.assumption_ids || claim.depends_on_assumption_ids || [];
      return <details className="research-details theory-argument" key={claim.statement_id} open={selected === claim.statement_id} onToggle={event => { const expanded = selected === claim.statement_id; if (event.currentTarget.open !== expanded) onSelect(event.currentTarget.open ? claim.statement_id : null); }}>
        <summary><span>{graph.nodes.find(node => node.id === claim.statement_id)?.label || humanLabel(claim.statement_id)}</span> <TheorySupportBadge statement={claim} /></summary>
        {selected === claim.statement_id && <><TheoryStatement statement={claim} reference={reference} onSource={onSource} proofSources={proofSources} />
          {assumptionIds.length > 0 && <section className="scientific-passage"><h4>Registered assumptions used</h4>{assumptionIds.map(id => { const assumption = assumptions.find(item => (item.assumption_id || item.id) === id); return <article key={id} className="scientific-block">{assumption ? <TheoryStatement statement={assumption} reference={reference} onSource={onSource} proofSources={proofSources} /> : <p className="note warn">{humanLabel(id)}: the registered assumption is unavailable in this theory source.</p>}</article>; })}</section>}
        </>}
      </details>;
    })}
    <div className="btnrow"><SourceRef reference={complete.generation_ref} onOpen={onSource} label={researchDocumentTitle(complete) || "Complete theory document"} /></div>
    <ScientificDocuments documents={documents.filter(document => document !== complete)} onSource={onSource} empty="" />
  </>;
}

export function TheoryReading({ documents = [], assessments, onSource, reading = {}, onReadingChange, ...props }) {
  const map = scoped(props.claimMaps, props.branch, "P3")[0];
  const reference = map?.theory_generation_ref || map?.generation_ref;
  const canExplain = hasExactRef(reference) && ["theory_record", "complete_theory"].includes(reference.family);
  const proofSources = documents.flatMap((doc) => doc.inline_sources || []);
  return <section className="card" data-card-role="research" data-reading-anchor="theory-reading" tabIndex={-1}><PhaseTabs heading="Claims, assumptions and proofs" label="Theoretical detail" selectedTab={reading.tab} onTabChange={(tab) => onReadingChange?.({ tab })} tabs={[
    { id: "claims", label: "Claims", content: <TheoryWorkbench {...props} proofSources={proofSources} reading={reading} onReadingChange={onReadingChange} onSource={onSource} embedded /> },
    { id: "assumptions", label: "Assumptions", content: (map?.assumptions || []).length ? map.assumptions.map((assumption, index) => <article className="scientific-block" key={assumption.assumption_id || index}><TheoryStatement statement={assumption} reference={reference} onSource={onSource} proofSources={proofSources} />{props.onAssumptionConversation && canExplain && <ActionButton action="ask" uiRole="research" onClick={() => props.onAssumptionConversation({ ...reference, kind: "assumption", object_id: assumption.assumption_id || assumption.id, label: assumption.label || assumption.title, statement: assumption.text || assumption.statement, latex: assumption.latex })}>Explain this assumption</ActionButton>}</article>) : <p className="note">No linked assumptions have been recorded yet.</p> },
    { id: "arguments", label: "Arguments", content: <TheoryArguments {...props} map={map} documents={documents.filter(doc => !/audit|review|falsification/.test(doc.kind || ""))} onSource={onSource} proofSources={proofSources} /> },
    { id: "review", label: "Review", content: <><ScientificDocuments documents={documents.filter((doc) => /audit|review|falsification/.test(doc.kind || ""))} onSource={onSource} empty="No separate review account is available yet." /><TheoryLeadResponses responses={map?.issue_dispositions} onSource={onSource} />{assessments}</> },
  ]} /></section>;
}
