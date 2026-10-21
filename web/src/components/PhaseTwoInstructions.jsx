import React from "react";
import { methodStartingPointSource } from "../methodSeed";
import { ResearchDocument, SourceRef } from "./Shared";

export default function PhaseTwoInstructions({ id, value, onChange, disabled = false, suppliedMethod, onSource }) {
  const source = methodStartingPointSource(suppliedMethod);
  return <>
    <div className="field contribution-surface"><label htmlFor={id}>Additional instructions or ideas for Phase 2</label><textarea id={id} rows={3} value={value} onChange={(event) => onChange(event.target.value)} disabled={disabled} aria-describedby={`${id}-routing`} placeholder="Optional: add directions for the Research Lead or describe a model idea you want investigated." /></div>
    <p className="note" id={`${id}-routing`}>These additions go only to the Research Lead. The theorist and analyst develop independent alternatives.</p>
    <details className="research-details"><summary>How the team uses these instructions</summary><p className="note">Each member proposes exactly one model: the lead develops the candidate most aligned with your instructions and ideas; the Theorist focuses on mathematical structure, assumptions and guarantees; the Data Analyst focuses on estimation, data requirements and practical computation. The specialists develop their proposals independently from the shared research setting and literature.</p>
    <p className="note">After submitting their proposals, the Theorist reviews the analyst's and lead's models, and the Data Analyst reviews the theorist's and lead's models. The lead compares all three with those reviews, without adding another model. Proof development and executed simulations follow in later phases.</p>
    <p className="note">To change the objective or constraints for everyone, edit the shared research setting in Phase 1.</p></details>
    {suppliedMethod && <details className="research-details"><summary>Model supplied to the lead: {suppliedMethod.title}</summary><p className="note">{source ? `Starting point: Version ${source.method_identity?.version} of this model. The exact published definition${source.proposal_ref ? " and original proposal" : ""} ${source.proposal_ref ? "are" : "is"} frozen when you start this comparison run.` : "This exact formulation accompanies your instructions to the Research Lead."}</p><ResearchDocument text={suppliedMethod.specification_markdown} />{source && <><SourceRef reference={source.catalog_ref} onOpen={onSource} label="Selected catalog definition source" />{source.proposal_ref && <SourceRef reference={source.proposal_ref} onOpen={onSource} label="Original proposal source" />}</>}<details className="research-details"><summary>Original source reference</summary><p className="note">{suppliedMethod.source_reference}</p></details></details>}
  </>;
}
