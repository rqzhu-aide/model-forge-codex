import React from "react";
import { phaseInputSummary } from "../phaseInputSummary";
import { IssueEntry } from "./IssuesCard";

// P5 keeps its report-first layout. Only retained editorial choices add rows
// to the existing revision card, using the summary's exact question projection.
export default function ReportEditorialQuestions({ context, onSaved, onSource, onExplain }) {
  const questions = phaseInputSummary(context).questions.items;
  if (!questions.length) return null;
  return <section className="phase-work-details" data-reading-anchor="report-editorial-choices" aria-label="Editorial choices for this report">
    <h3>Editorial choices for this report</h3>
    {questions.map(({ key, issue }) => <IssueEntry key={key} compact headingLevel={5} issue={issue} projectId={context.projectId} phase="P5" branch={context.branch} onSaved={onSaved} onSource={onSource} onExplain={onExplain} />)}
  </section>;
}
