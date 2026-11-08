import React, { useId } from "react";
import { modificationOptionsFor } from "../methodWorkspace";
import { researchReadingSize } from "../readingSize";
import { perspective } from "./LiteratureWorkspace";
import { ReadingDocumentButton } from "./MethodReadingWindow";
import { ResearchDocument, SourceRef } from "./Shared";
import EmpiricalDocument, { useEmpiricalSources } from "./EmpiricalDocument";
import { empiricalReadingSnapshot } from "./EmpiricalReading";

const hasText = (value) => {
  const size = researchReadingSize(value);
  return size.words > 0 || size.equations > 0;
};

const methodLabelFor = (method) => [method?.title, method?.identity?.version != null ? `Version ${method.identity.version}` : null].filter(Boolean).join(" · ");
const attributed = (methodLabel, author) => [methodLabel, author].filter(Boolean).join(" · ");
const sourceRow = (reference, onSource, label) => reference ? <div className="p2-reader-sources"><SourceRef reference={reference} onOpen={onSource} label={label} /></div> : null;

// ProjectView supplies Phase 1 notes only when they are the actual preparation
// basis. The method being read can differ from the work being prepared.
function phaseTwoDocuments({ selected, method, reviewed, phaseOne } = {}, onSource, documents, notes) {
  const methodLabel = methodLabelFor(method);
  if (selected) {
    const comparison = reviewed?.comparison;
    const options = modificationOptionsFor(comparison, selected.proposal_id);
    if (options.length) {
      documents.push({ name: "suggested-modifications", title: "Suggested modifications", subtitle: `${methodLabel} · Research Lead`,
        sources: [selected.proposal_id, selected.generation_ref, method?.identity, comparison.generation_ref || options],
        size: researchReadingSize(options.map((option) => ({ title: option.title,
          text: [option.what_changes_markdown, option.when_preferable_markdown].filter(Boolean) }))),
        body: <>{options.map((option, index) => <section className="modification-option" key={option.option_id || index}>
          <h3>{option.title || `Modification option ${index + 1}`}</h3>
          {option.what_changes_markdown && <><h4>What changes mathematically</h4><ResearchDocument text={option.what_changes_markdown} /></>}
          {option.when_preferable_markdown && <><h4>When it is preferable</h4><ResearchDocument text={option.when_preferable_markdown} /></>}
          {!option.what_changes_markdown && !option.when_preferable_markdown && <p className="note">No details were recorded for this modification option.</p>}
        </section>)}<div className="p2-reader-sources"><SourceRef reference={comparison.generation_ref} onOpen={onSource} label="Lead assessment source" /></div></> });
    } else notes.push(!reviewed ? "No Lead assessment is linked to this exact proposal run."
      : !Array.isArray(comparison?.modification_options) ? "This earlier Lead assessment did not record separate modification options."
      : "The Lead recorded no modification options for this proposal.");
    if (hasText(selected.proposed_evaluation_markdown)) {
      documents.push({ name: "proposed-investigations", title: "Proposed investigations", subtitle: `${methodLabel} · ${perspective(selected)}`,
        sources: [selected.proposal_id, selected.generation_ref || selected.proposed_evaluation_markdown, method?.identity], size: researchReadingSize(selected.proposed_evaluation_markdown),
        body: <><p className="note">These are proposed steps, not completed proofs or simulations.</p><ResearchDocument text={selected.proposed_evaluation_markdown} />
          <div className="p2-reader-sources"><SourceRef reference={selected.generation_ref} onOpen={onSource} label="Proposed work source" /></div></> });
    } else notes.push("Proposed investigations were not recorded for this proposal.");
  } else if (method) notes.push("This catalog definition has no linked proposal with suggested modifications or proposed investigations.");
  if (phaseOne && hasText(phaseOne.preparation)) documents.push({ name: "phase-one-notes", title: "Notes from Phase 1", subtitle: "Literature-to-model preparation",
    sources: [phaseOne.generation_ref || phaseOne.preparation], size: researchReadingSize(phaseOne.preparation),
    body: <><ResearchDocument text={phaseOne.preparation} /><div className="p2-reader-sources"><SourceRef reference={phaseOne.generation_ref} onOpen={onSource} label="Phase 1 preparation source" /></div></> });
}

// The Lead's decision record lists the actions it recommends with their consequences.
function phaseThreeDocuments({ decision, methodLabel, method } = {}, onSource, documents) {
  const actions = (Array.isArray(decision?.available_actions) ? decision.available_actions : [])
    .filter((action) => typeof action === "string" ? action.trim() : action && (action.label || action.consequence));
  if (!actions.length) return;
  const items = actions.map((action, index) => typeof action === "string" ? { title: `Action ${index + 1}`, text: action }
    : { title: action.label || `Action ${index + 1}`, text: action.consequence });
  documents.push({ name: "lead-recommended-actions", title: "Lead's recommended actions", subtitle: attributed(methodLabel ?? methodLabelFor(method), "Research Lead"),
    sources: [decision.generation_ref || items], size: researchReadingSize(items),
    body: <>{items.map((item, index) => <section className="modification-option" key={index}>
      <h3>{item.title}</h3>
      {hasText(item.text) ? <ResearchDocument text={item.text} /> : <p className="note">No consequence was recorded for this action.</p>}
    </section>)}{sourceRow(decision.generation_ref, onSource, "Lead assessment source")}</> });
}

// The evaluation summary carries the Lead's recommendation; each question carries
// next steps from the Lead's review and the Analyst's result, attributed separately.
function phaseFourDocuments({ summary, questions, methodLabel, method } = {}, onSource, documents) {
  const label = methodLabel ?? methodLabelFor(method);
  const recommendation = summary?.decision_summary?.recommendation_markdown;
  if (hasText(recommendation)) documents.push({ name: "lead-recommendation", title: "Lead's recommendation", subtitle: attributed(label, "Research Lead"),
    sources: [summary.generation_ref || recommendation], size: researchReadingSize(recommendation),
    body: <><EmpiricalDocument text={recommendation} />{sourceRow(summary.generation_ref, onSource, "Evaluation summary source")}</> });
  const steps = (Array.isArray(questions) ? questions : []).map((question) => ({ question, parts: [
    { author: "Research Lead", text: question?.review?.next_steps_markdown, reference: question?.review?.generation_ref, label: "Lead review source" },
    { author: "Data Analyst", text: question?.result?.next_steps_markdown, reference: question?.result?.generation_ref, label: "Analyst result source" },
  ].filter((part) => hasText(part.text)) })).filter((item) => item.parts.length);
  if (steps.length) documents.push({ name: "question-next-steps", title: "Question next steps", subtitle: attributed(label, "Research Lead and Data Analyst"),
    sources: steps.map(({ question, parts }) => [question.question_id, question.generation_ref, ...parts.map((part) => part.reference || part.text)]),
    size: researchReadingSize(steps.map(({ question, parts }) => ({ title: question.title, text: parts.map((part) => part.text) }))),
    body: <>{steps.map(({ question, parts }, index) => <section className="modification-option" key={question.question_id || index}>
      <h3>{question.title || `Question ${index + 1}`}</h3>
      {parts.map((part) => <React.Fragment key={part.author}><h4>{part.author}</h4><EmpiricalDocument text={part.text} /></React.Fragment>)}
      {parts.some((part) => part.reference) && <div className="p2-reader-sources">{parts.filter((part) => part.reference).map((part) => <SourceRef key={part.author} reference={part.reference} onOpen={onSource} label={part.label} />)}</div>}
    </section>)}</> });
}

// One input shape for every phase: the phase, the method or branch being prepared,
// and the texts with their sources. Documents carry the phase and scope they were
// built for so a frozen reader never outlives the method or branch it describes.
export function preparationReadingDocuments(input, onSource) {
  const documents = [], notes = [];
  const { phase = "P2", branch = null } = input || {};
  if (phase === "P2") phaseTwoDocuments(input || {}, onSource, documents, notes);
  else if (phase === "P3") phaseThreeDocuments(input, onSource, documents);
  else if (phase === "P4") phaseFourDocuments(input, onSource, documents);
  const scope = [phase, branch];
  return { documents: documents.map((document) => ({ ...document, phase, scope })), notes };
}

export function preparationReadingKey(projectId, document) {
  return JSON.stringify([projectId, document.phase || "P2", document.scope ?? null, document.name, document.sources]);
}

export function preparationReadingSnapshot(projectId, input, name, onSource, sources = {}) {
  const frozen = structuredClone(input);
  const document = preparationReadingDocuments(frozen, onSource).documents.find((item) => item.name === name);
  if (!document) return null;
  if (document.phase === "P4") {
    const empirical = empiricalReadingSnapshot({ scope: { projectId, phase: document.phase, branch: frozen.branch },
      kind: name, title: document.title, subtitle: document.subtitle, input: frozen, sources, onSource,
      renderBody: (value, openSource) => preparationReadingDocuments(value, openSource).documents.find((item) => item.name === name).body });
    return { ...document, ...empirical, projectId };
  }
  return { ...document, key: preparationReadingKey(projectId, document), projectId };
}

// The ProjectView owns the open window outside its keyed preparation form.
// A catalog replacement can change the form's draft scope during polling.
export default function PreparationDocuments({ projectId, input, onSource, onReadDocument }) {
  const id = useId();
  const sources = useEmpiricalSources();
  const { documents, notes } = preparationReadingDocuments(input, onSource);
  const open = (name, trigger) => {
    const document = preparationReadingSnapshot(projectId, input, name, onSource, sources);
    if (document) onReadDocument?.({ ...document, trigger });
  };
  const noteContent = notes.map((note) => <p className="note" key={note}>{note}</p>);
  return documents.length ? <section aria-labelledby={`${id}-supporting`}>
      <h3 id={`${id}-supporting`} tabIndex={-1}>Supporting reading</h3>
      <p className="note">Reading these documents does not add them to your instructions or selected sources.</p>
      <div className="p2-reading-links">{documents.map((document) => <ReadingDocumentButton key={document.name} title={document.title} size={document.size} onClick={(event) => open(document.name, event.currentTarget)} />)}</div>
      {noteContent}
    </section> : <>{noteContent}</>;
}
