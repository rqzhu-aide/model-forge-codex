import React from "react";
import { decisionOptions, decisionPriorityLabel, legacyOptionText } from "../researcherDecisions";
import { CitedRequestDocument } from "./LiteratureCitation";
import { ResearchLabel } from "./Shared";

export function DecisionBrief({ item, onSource, showOptions = true, showMetadata = true }) {
  const options = decisionOptions(item);
  const consequence = item.likely_consequence || item.consequence_markdown || item.why_it_matters || item.why_it_matters_markdown;
  const authoredBrief = ["choice", "study_fact"].includes(item.response_kind);
  const context = authoredBrief ? item.context_markdown || item.summary_markdown : null;
  const role = item.original_role || item.responsible_role || item.raised_by;
  const recommendationLabel = authoredBrief || role === "research_lead" ? "Lead recommendation" : role === "outside_reviewer" ? "Reviewer recommendation" : "Author recommendation";
  const doc = (text, section) => <CitedRequestDocument item={item} text={text} section={section} onSource={onSource} />;
  return <div className="decision-brief">
    {showMetadata && (item.response_kind || decisionPriorityLabel(item)) && <p className="note decision-kind">{item.response_kind === "study_fact" ? "Study information" : item.response_kind === "choice" ? "Researcher choice" : "Researcher question"}{decisionPriorityLabel(item) && ` · ${decisionPriorityLabel(item)}`}</p>}
    {context && <section><h4>{item.response_kind === "study_fact" ? "Missing study information" : "Affected point"}</h4>{doc(context, "context")}</section>}
    {consequence && consequence !== context && <section><h4>{item.response_kind === "study_fact" ? "What depends on it" : "Practical consequence"}</h4>{doc(consequence, "consequence")}</section>}
    {showOptions && !options.length && item.response_kind !== "study_fact" && legacyOptionText(item.options) && <section><h4>Possible directions</h4>{doc(legacyOptionText(item.options), "options")}</section>}
    {item.recommendation && item.response_kind !== "study_fact" && <section><h4>{recommendationLabel}</h4>{doc(item.recommendation, "recommendation")}</section>}
  </div>;
}

// This is a render helper so callers retain the single response form and all
// state. Native radios also provide the browser's normal keyboard behavior.
export function decisionResponseFields({ item, id, note, origin, choice, busy, inputRef, update, select, onSource }) {
  const options = decisionOptions(item);
  if (!options.length) return <>
    <div className="field"><label htmlFor={id}>{item.response_kind === "study_fact" ? "Your study information" : "Your instruction"}</label><textarea id={id} ref={inputRef} rows={3} value={note} onChange={event => update(event.target.value)} disabled={busy} required={origin !== "unknown"} /></div>
    {(item.scope || item.response_kind === "study_fact") && <label className="check-label"><input type="checkbox" checked={origin === "unknown"} disabled={busy} onChange={event => update(note, event.target.checked ? "unknown" : "researcher_reported")} />This remains unknown</label>}
  </>;
  const custom = choice === "custom";
  const noteField = <div className="field"><label htmlFor={id}>{custom ? "Your response" : "Optional note"}</label><textarea id={id} ref={custom ? inputRef : undefined} rows={3} value={note} onChange={event => update(event.target.value)} disabled={busy} required={custom} /></div>;
  return <>
    <fieldset className="decision-options" disabled={busy}><legend>Your response</legend>
      {options.map((option, index) => <div className="decision-option" key={option.id}>
        <label className="decision-option-heading"><input ref={choice === `option:${option.id}` || (!choice && index === 0) ? inputRef : undefined} type="radio" name={`${id}-choice`} value={`option:${option.id}`} checked={choice === `option:${option.id}`} onChange={() => select(`option:${option.id}`)} aria-describedby={`${id}-consequence-${index}`} /><ResearchLabel className="decision-option-label" text={option.label} /></label>
        <div className="decision-option-consequence" id={`${id}-consequence-${index}`}><CitedRequestDocument item={item} text={option.consequence} section={`option:${option.id}`} onSource={onSource} /></div>
      </div>)}
      <label className="decision-option decision-other"><input ref={choice === "unknown" ? inputRef : undefined} type="radio" name={`${id}-choice`} value="unknown" checked={choice === "unknown"} onChange={() => select("unknown")} /><span>I am unsure</span></label>
      <label className="decision-option decision-other"><input type="radio" name={`${id}-choice`} value="custom" checked={custom} onChange={() => select("custom")} /><span>Give a different response</span></label>
    </fieldset>
    {custom ? noteField : <details className="research-details decision-note" open={Boolean(note) || undefined}><summary>Add a note (optional)</summary>{noteField}</details>}
  </>;
}
