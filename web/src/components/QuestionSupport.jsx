import React from "react";
import { decisionBriefSections, decisionPriorityLabel, decisionSupportSections } from "../researcherDecisions";
import { issueIdentifiers, issueSourceIdentity, issueVersionKey } from "../phaseWorkflow";
import { issueDisplayKind } from "../phaseUiState";
import { requestSourceReferences } from "../contextualRequests";
import { researchReadingSize } from "../readingSize";
import { humanLabel } from "../research";
import { CitedRequestDocument } from "./LiteratureCitation";
import { ResearchLabel, SourceRef } from "./Shared";

// Use the existing brief/support projection and exact authored-text deduplication.
// A limitation may equal another support section, but it still belongs inline.
// A title that only repeats a source identifier is provenance, not reading.
export function questionSupport(issue, title, questionSources = []) {
  const limits = issue.information_limits || issue.information_limits_markdown;
  const inlineLimits = limits && ![title, ...decisionBriefSections(issue).map(({ text }) => text)].includes(limits) ? limits : null;
  const sections = decisionSupportSections(issue, title).filter(({ text }) => text !== limits);
  const originalTitle = issue.title && issue.title !== title && !issueIdentifiers(issue).has(issue.title) ? issue.title : null;
  const sources = requestSourceReferences(issue);
  const size = researchReadingSize([originalTitle, ...sections.map(({ text }) => text)]);
  const sourceCount = sources.length + questionSources.length;
  const hasProse = Boolean(originalTitle || sections.length);
  const teamWork = ["research_task", "scientific_issue"].includes(issueDisplayKind(issue));
  const empirical = (issue.phase || issue.generation_ref?.phase || issue.explanation_target?.phase) === "P4";
  const original = issue.generation_ref && { ...issue.generation_ref,
    ...(issue.generation_ref.entry_pointer == null && issue.entry_pointer ? { entry_pointer: issue.entry_pointer } : {}) };
  const originalCount = original && sources.some(({ reference }) => JSON.stringify(ordered(reference)) === JSON.stringify(ordered(original))) ? 1 : 0;
  const evidenceCount = sources.length - originalCount;
  const citationCount = new Set(questionSources.map(text => text.match(/\(([^)]+)\)$/)?.[1] || text)).size;
  const sourceLabel = empirical ? [evidenceCount ? `${evidenceCount} scientific ${evidenceCount === 1 ? "source" : "sources"}` : null,
    originalCount ? evidenceCount ? "original request" : "Original request" : null,
    citationCount ? `${citationCount} ${citationCount === 1 ? "citation" : "citations"}` : null].filter(Boolean).join(" · ")
    : `${sourceCount} scientific ${sourceCount === 1 ? "source" : "sources"}`;
  const sourceTitle = !empirical || evidenceCount ? "View scientific sources"
    : originalCount ? citationCount ? "View sources" : "View original request" : "View citations";
  return { inlineLimits, sections, originalTitle, questionSources, sources, size, teamWork,
    available: hasProse || sourceCount > 0,
    title: hasProse ? "Read background and sources" : sourceTitle,
    readerTitle: hasProse ? "Background and sources" : sourceTitle.slice(5).replace(/^./, character => character.toUpperCase()),
    sizeLabel: hasProse ? undefined : sourceLabel };
}

const ordered = value => value && typeof value === "object" ? Array.isArray(value) ? value.map(ordered)
  : Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value ?? null;
// The viewing phase and selected branch/model own the reader; answer-draft keys stay separate.
export function questionSupportReadingKey({ projectId, phase, branch, methodId, modelRef }, issue) {
  return JSON.stringify(ordered([projectId, phase, { branch, methodId, modelRef }, "question-support", issueSourceIdentity(issue) || issueVersionKey(issue),
    issue.generation_ref, issue.related_source_refs, issue.scientific_source_refs, (issue.citations || []).map(citation => [citation.source_id, citation.entry_ref, citation.card?.generation_ref, citation.card?.entry_pointer])]));
}

// Freeze the question once so polling or a replaced question cannot change an open reader.
export function questionSupportSnapshot(scope, issue, questionTitle, questionSources, onSource) {
  const frozen = structuredClone(issue);
  const support = questionSupport(frozen, questionTitle, questionSources);
  return { key: questionSupportReadingKey(scope, frozen),
    title: support.readerTitle,
    subtitle: <ResearchLabel text={questionTitle} />, size: support.size, sizeLabel: support.sizeLabel,
    body: <QuestionSupportDocument issue={frozen} support={support} onSource={onSource} /> };
}

export function QuestionSupportDocument({ issue, support, onSource }) {
  const doc = (text, section) => <CitedRequestDocument item={issue} text={text} section={section} onSource={onSource} />;
  return <div className="question-support">
    {!support.teamWork && (issue.response_kind || decisionPriorityLabel(issue)) && <p className="note">{issue.response_kind === "study_fact" ? "Study information" : "Researcher choice"}{decisionPriorityLabel(issue) && ` · ${decisionPriorityLabel(issue)}`}</p>}
    {issue.severity && <p className="note">Scientific importance: {humanLabel(issue.severity)}.</p>}
    {support.originalTitle && <section><h3>Original title</h3>{doc(support.originalTitle, "title")}</section>}
    {issue.original_role === "outside_reviewer" && <p className="note">The Research Lead can explain this comment as an interpretation of the independent review.</p>}
    {support.sections.map(({ text, heading, section }) => <section key={section}><h3>{heading}</h3>{doc(text, section)}</section>)}
    {support.questionSources.length > 0 && <section><h3>Question sources</h3>{doc(support.questionSources.join("\n\n"), "question-sources")}</section>}
    {issue.disposition && issue.disposition !== "open" && <p className="note">Team assessment: {humanLabel(issue.disposition)}.{!support.teamWork && " Your response is kept separately."}</p>}
    {support.sources.length > 0 && <div className="btnrow issue-actions">{support.sources.map(({ label, reference }, index) => <SourceRef key={index} reference={reference} onOpen={onSource} label={(issue.phase || issue.generation_ref?.phase || issue.explanation_target?.phase) === "P4" || issue.scientific_source_refs?.length ? label : index === 0 ? "Read the scientific context" : label} />)}</div>}
  </div>;
}
