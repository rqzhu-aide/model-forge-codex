import React from "react";
import { decisionBriefSections, decisionOptions, decisionPriorityLabel, recommendedDecisionOption } from "../researcherDecisions";
import { CitedRequestDocument } from "./LiteratureCitation";
import { ResearchLabel } from "./Shared";
import { issueVersionKey } from "../phaseWorkflow";

export function DecisionBrief({ item, onSource, showOptions = true, showMetadata = true, headingLevel = 4, recommendationId }) {
  const Heading = `h${headingLevel}`;
  const doc = (text, section) => <CitedRequestDocument item={item} text={text} section={section} onSource={onSource} />;
  return <div className="decision-brief">
    {showMetadata && (item.response_kind || decisionPriorityLabel(item)) && <p className="note decision-kind">{item.response_kind === "study_fact" ? "Study information" : item.response_kind === "choice" ? "Researcher choice" : "Researcher question"}{decisionPriorityLabel(item) && ` · ${decisionPriorityLabel(item)}`}</p>}
    {decisionBriefSections(item, { showOptions }).map(({ text, heading, section }) => <section key={section} id={text === item.recommendation ? recommendationId : undefined} data-reading-anchor={`decision-rationale:${issueVersionKey(item)}:${section}`}><Heading>{heading}</Heading>{doc(text, section)}</section>)}
  </div>;
}

// This is a render helper so callers retain the single response form and all
// state. Native radios also provide the browser's normal keyboard behavior.
export function decisionResponseFields({ item, id, note, origin, choice, busy, inputRef, update, select, onSource, recommendationId }) {
  const options = decisionOptions(item);
  const recommended = recommendedDecisionOption(item);
  const author = item.original_role || item.raised_by || item.requested_by || item.responsible_role;
  const suggestionLabel = author === "research_lead" ? "Lead suggests" : "Suggested option";
  const recommendationVisible = recommendationId && decisionBriefSections(item).some(({ text }) => text === item.recommendation);
  if (!options.length) return <>
    <div className="field"><label htmlFor={id}>Your answer</label><textarea id={id} ref={inputRef} rows={3} value={note} onChange={event => update(event.target.value)} disabled={busy} required={origin !== "unknown"} /></div>
    {(item.scope || item.response_kind === "study_fact") && <label className="check-label"><input type="checkbox" checked={origin === "unknown"} disabled={busy} onChange={event => update(note, event.target.checked ? "unknown" : "researcher_reported")} />This remains unknown</label>}
  </>;
  const custom = choice === "custom";
  const noteField = <div className="field"><label htmlFor={id}>{custom ? "Your response" : "Optional note"}</label><textarea id={id} ref={custom ? inputRef : undefined} rows={3} value={note} onChange={event => update(event.target.value)} disabled={busy} required={custom} /></div>;
  return <>
    <fieldset className="decision-options" disabled={busy}><legend>Your response</legend>
      {options.map((option, index) => <div className="decision-option" key={option.id}>
        <label className="decision-option-heading"><input ref={choice === `option:${option.id}` || (!choice && index === 0) ? inputRef : undefined} type="radio" name={`${id}-choice`} value={`option:${option.id}`} checked={choice === `option:${option.id}`} onChange={() => select(`option:${option.id}`)} aria-describedby={`${id}-consequence-${index}${recommended?.id === option.id && recommendationVisible ? ` ${recommendationId}` : ""}`} /><ResearchLabel className="decision-option-label" text={option.label} />{recommended?.id === option.id && <span className="note">{suggestionLabel}</span>}</label>
        <div className="decision-option-consequence" id={`${id}-consequence-${index}`}><CitedRequestDocument item={item} text={option.consequence} section={`option:${option.id}`} onSource={onSource} /></div>
      </div>)}
      <label className="decision-option decision-other"><input ref={choice === "unknown" ? inputRef : undefined} type="radio" name={`${id}-choice`} value="unknown" checked={choice === "unknown"} onChange={() => select("unknown")} /><span>Not sure yet</span></label>
      <label className="decision-option decision-other"><input type="radio" name={`${id}-choice`} value="custom" checked={custom} onChange={() => select("custom")} /><span>Suggest another option</span></label>
    </fieldset>
    {custom ? noteField : <details className="research-details decision-note" open={Boolean(note) || undefined}><summary>Add a note (optional)</summary>{noteField}</details>}
  </>;
}
