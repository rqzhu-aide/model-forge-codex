import React from "react";
import { hasExactRef, humanLabel } from "../research";
import { ResearchDocument, SourceRef } from "./Shared";
import { ActionIcon } from "./Visuals";

const proofLabel = (status) => ({ full: "Full proof", sketch: "Proof sketch", cited: "Cited proof", missing: "Proof missing" }[status] || "Proof not recorded");
export const theoryAssessmentTone = (status) => ["contradicted", "retracted", "rejected"].includes(status) ? "fail"
  : ["conditional", "incomplete", "untested", "weakened", "unverified"].includes(status) ? "warn" : status === "established" ? "ok" : "mut";

// The submitted proof flag describes the original account after reassessment.
// This presentation rule makes no new scientific verdict or object comparison.
export function theorySupportPresentation(statement = {}) {
  const reassessed = Boolean(statement.assessment_context || statement.theorist_account || statement.assessment_source_error);
  const proofStatus = reassessed ? null : statement.proof_status;
  return { reassessed, status: statement.status, proofStatus,
    missingProof: !reassessed && (!proofStatus || proofStatus === "missing"),
    label: reassessed ? humanLabel(statement.status) || "Current assessment not recorded" : proofLabel(proofStatus),
    tone: reassessed ? theoryAssessmentTone(statement.status) : !proofStatus || proofStatus === "missing" ? "warn" : "mut" };
}

export function TheorySupportBadge({ statement }) {
  const support = theorySupportPresentation(statement);
  return <span className={`pill ${support.tone}`}>{support.label}</span>;
}

function AccountSource({ reference, error, onSource, label }) {
  return error || !hasExactRef(reference) ? <p className="note">{error || "The exact source is unavailable in the retained records."}</p>
    : <SourceRef reference={reference} onOpen={onSource} label={label} />;
}

export function TheoryJustification({ justification, heading }) {
  if (!justification) return null;
  return <section className="inspector-group"><h4>{heading || humanLabel(justification.kind || "Argument and remaining obligation")}</h4>
    {heading && justification.kind && <p className="note">{humanLabel(justification.kind)}</p>}
    {justification.summary && <ResearchDocument text={justification.summary} />}
    {justification.open_obligation && <div className="note warn"><b>Open obligation.</b><ResearchDocument text={justification.open_obligation} /></div>}
    {justification.locator && <p className="note">{justification.locator}</p>}
    {(justification.artifacts || []).map((artifact, index) => <div key={index}>{artifact.artifact_url
      ? <a className="source-link ui-action" data-action="source" data-ui-role="system" href={artifact.artifact_url} target="_blank" rel="noreferrer"><ActionIcon name="source" />{artifact.title || artifact.label || "Open support source"}{artifact.locator && ` · ${artifact.locator}`}</a>
      : <p className="note">The retained {justification.kind === "counterexample" || justification.kind === "empirical_evidence" ? "support" : "proof"} file is unavailable: {artifact.title || artifact.label || artifact.path || artifact.artifact_id || "See complete theory"}{artifact.locator && ` · ${artifact.locator}`}</p>}</div>)}
  </section>;
}

export function OriginalTheoristAccount({ statement, onSource, compact = false }) {
  if (!theorySupportPresentation(statement).reassessed) return null;
  const original = statement.theorist_account;
  return <details className="research-details theory-original-account"><summary>Original theorist account</summary>
    {original ? <>{original.status && <p className="note">Theorist submitted status: {humanLabel(original.status)}</p>}
      {original.proof_status && <p className="note">Theorist submitted proof assessment: {proofLabel(original.proof_status)}</p>}
      {!compact && <TheoryJustification justification={original.justification} heading="Theorist submitted argument" />}
      <AccountSource reference={original.generation_ref} error={original.source_error} onSource={onSource} label="Original theorist source" />
    </> : <p className="note">The original theorist account is unavailable in the retained records.</p>}
  </details>;
}

export function TheoryAssessmentAccount({ statement, onSource }) {
  const context = statement.assessment_context;
  return <>{context && <section className="inspector-group theory-assessment"><h4>Research Lead assessment</h4>
    {context.origin === "lead_concern" && <p className="note">This concern was raised by the Research Lead and has not received independent Analyst review.</p>}
    {context.reason && <ResearchDocument text={context.reason} />}
    <AccountSource reference={context.generation_ref} error={statement.assessment_source_error} onSource={onSource} label="Lead assessment source" />
    {context.origin === "analyst_issue" && <AccountSource reference={context.issue_ref} error={context.source_error} onSource={onSource} label="Original Analyst concern" />}
  </section>}
    {!context && statement.assessment_source_error && <p className="note">{statement.assessment_source_error}</p>}
    {!(theorySupportPresentation(statement).reassessed && statement.original_justification_retained === true) && <TheoryJustification justification={statement.justification} heading={context?.origin === "analyst_issue" ? "Current support from the Analyst" : undefined} />}
    <OriginalTheoristAccount statement={statement} onSource={onSource} />
  </>;
}

export function TheoryLeadResponses({ responses = [], onSource }) {
  if (!responses.length) return null;
  return <details className="research-details theory-lead-responses"><summary>Research Lead responses to Analyst concerns ({responses.length})</summary>
    <p className="note">These are the Lead's responses. The independent Analyst account above retains its original findings.</p>
    {responses.map((response, index) => <section className="scientific-block" key={response.issue_id || index}>
      <h4>{response.issue?.title || "Analyst concern"}</h4>
      {response.issue && <><ResearchDocument text={response.issue} /><AccountSource reference={response.issue_ref} onSource={onSource} label="Original Analyst concern" /></>}
      {!response.issue && <p className="note">{response.source_error || "The original Analyst concern is unavailable in the retained records."}</p>}
      <p className="note">Lead response: {humanLabel(response.status) || "Not recorded"}</p>
      {response.reason && <ResearchDocument text={response.reason} />}
      <AccountSource reference={response.generation_ref} onSource={onSource} label="Lead response source" />
    </section>)}
  </details>;
}
