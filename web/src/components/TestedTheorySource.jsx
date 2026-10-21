import React from "react";
import { humanLabel } from "../research";
import { theoryComponent } from "../runRequests";
import { MathText, ResearchDocument } from "./Shared";
import { ActionButton } from "./Visuals";
import { TheoryConditions } from "./TheoryConditions";

export default function TestedTheorySource({ document, componentId, onCurrentTheory }) {
  const component = theoryComponent(document, componentId);
  const dependencies = component ? [...new Set([...(component.assumption_ids || []), ...(component.depends_on_assumption_ids || []), ...(component.depends_on_statement_ids || [])])] : [];
  return <>
    <p className="context-note">This is the recorded theory component used by the experiment. The current theory may differ.</p>
    <h3>{component?.label || component?.title || humanLabel(componentId)}</h3>
    {component ? <><ResearchDocument text={component.text || component.statement || component.description} />{component.latex && <MathText latex={component.latex} />}<TheoryConditions statement={component} />
      {dependencies.length > 0 && <details className="research-details"><summary>Assumptions and supporting statements</summary>{dependencies.map((id) => { const dependency = theoryComponent(document, id); return <div className="inspector-group" key={id}><h4>{dependency?.label || dependency?.title || humanLabel(id)}</h4><ResearchDocument text={dependency?.text || dependency?.statement || "This dependency is not present in the recorded theory."} />{dependency?.latex && <MathText latex={dependency.latex} />}{dependency && <TheoryConditions statement={dependency} />}</div>; })}</details>}
      <details className="research-details"><summary>Complete component</summary><ResearchDocument text={component} /></details></> : <p className="note warn">The claim is not present in this exact theory record. Inspect the complete source for its original context.</p>}
    <ActionButton action="details" onClick={onCurrentTheory}>Open current theory graph</ActionButton>
  </>;
}
