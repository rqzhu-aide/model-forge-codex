import React, { useId, useState } from "react";
import { ActionButton } from "./Visuals";
import { ProjectBriefEditor } from "./ProjectBrief";
import LiteratureWorkspace from "./LiteratureWorkspace";
import { hasConciseP1Account } from "../phaseOneReader";

export default function PhaseOneWorkspace({ project, basis, artifacts = {}, activeRunCount, onSaved, onSource, onGoal, goalCorrectionCount = 0, issues, furtherWork, progress, reading, onReadingChange }) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const concise = hasConciseP1Account(basis);
  const setting = ({ renderDocument, onNotation }) => <section className="card research-setting" data-card-role="summary" data-reading-anchor="research-setting" aria-labelledby={`${id}-setting`}>
      <div className="card-heading"><h2 id={`${id}-setting`}>Research Setting</h2><ActionButton action="edit" uiRole="research" onClick={() => setEditing(true)}>Project instructions</ActionButton></div><div className="body">
        {basis?.research_setting?.statement_markdown ? concise ? <><h3>Study description</h3>{renderDocument(basis.research_setting.statement_markdown, "setting")}</> : <details className="research-details" data-reading-anchor="earlier-setting"><summary>Read the earlier study formulation</summary>{renderDocument(basis.research_setting.statement_markdown, "setting")}</details> : <p className="note">Your project instructions are saved. The team's formulation will appear after the literature study.</p>}
        {basis?.research_setting?.research_goal_markdown ? <section className="scientific-passage research-goal"><div className="section-heading"><h3>Study goal <span className="note">· Lead's interpretation</span></h3>{onGoal && <ActionButton action="edit" uiRole="research" aria-haspopup="dialog" onClick={onGoal}>Correct or discuss goal</ActionButton>}</div>{concise ? renderDocument(basis.research_setting.research_goal_markdown, "goal") : <details className="research-details" data-reading-anchor="earlier-goal"><summary>Read the earlier interpreted goal</summary>{renderDocument(basis.research_setting.research_goal_markdown, "goal")}</details>}{goalCorrectionCount > 0 && <p className="note" role="status">{goalCorrectionCount === 1 ? "Your correction is saved" : "Your corrections are saved"} for future work.</p>}</section> : <p className="note">A Lead-interpreted goal is not available yet.</p>}
        {basis?.research_setting?.component_interpretations?.length > 0 && <div className="btnrow setting-footer"><ActionButton action="details" aria-haspopup="dialog" onClick={onNotation}>Notation</ActionButton></div>}
    </div></section>;
  return <div className="phase-one-workspace">
    <LiteratureWorkspace reading={reading} onReadingChange={onReadingChange} progress={progress} libraries={artifacts.literature_libraries} bases={artifacts.research_bases} basis={basis} setting={setting} decisions={issues} onSource={onSource} />
    {furtherWork}
    {editing && <ProjectBriefEditor project={project} activeRunCount={activeRunCount} onClose={() => setEditing(false)} onSaved={(updated) => { onSaved(updated); setEditing(false); }} />}
  </div>;
}
