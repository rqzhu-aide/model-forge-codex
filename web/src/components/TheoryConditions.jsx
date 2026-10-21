import React from "react";
import { ResearchDocument } from "./Shared";

// Use the same authored qualifications in the graph and complete reader.
export function TheoryConditions({ statement = {} }) {
  const assumption = Boolean(statement.assumption_id || statement.statement_type === "assumption" || statement.kind === "assumption");
  return <>
    {statement.regime && <section><h4>Conditions under which it applies</h4><ResearchDocument text={statement.regime} /></section>}
    {statement.quantifiers?.length > 0 && <section><h4>Scope of the statement</h4><ResearchDocument text={statement.quantifiers} /></section>}
    {statement.strength && <section><h4>Strength of the condition</h4><ResearchDocument text={statement.strength} /></section>}
    {statement.sensitivity ? <section><h4>What changes if this condition fails</h4><ResearchDocument text={statement.sensitivity} /></section> : assumption && <p className="note">The consequence of removing this condition was not recorded in this theory source.</p>}
  </>;
}
