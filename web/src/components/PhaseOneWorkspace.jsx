import React, { useId, useState } from "react";
import { ActionButton } from "./Visuals";
import { SourceRef } from "./Shared";
import { ProjectBriefEditor } from "./ProjectBrief";
import LiteratureWorkspace from "./LiteratureWorkspace";
import { goalCorrections, goalSource } from "../phaseOneReader";
import { hasSharedNotation } from "../sharedNotation";
import ResearchCardLayout from "./ResearchCardLayout";

export default function PhaseOneWorkspace({ project, basis, problemContext, artifacts = {}, activeRunCount = 0, onSaved, onSource, onGoal, issues, furtherWork, progress, reading, onReadingChange }) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const reference = goalSource(basis);
  const clarifications = reference ? goalCorrections(problemContext, reference) : [];
  const setting = ({ renderDocument, onNotation }) => {
    const statement = basis?.research_setting?.statement_markdown;
    const interpreted = basis?.research_setting?.research_goal_markdown;
    const description = statement ? <><h3>Study description</h3>{renderDocument(statement, "setting")}</> : <p className="note">Your project instructions are saved. The team's formulation will appear after the literature study.</p>;
    const goal = interpreted ? <section className="scientific-passage research-goal"><div className="section-heading"><h3>Study goal <span className="note">{clarifications.length ? clarifications.length === 1 ? "· Your clarification" : "· Your clarifications" : "· Lead's interpretation"}</span></h3></div>
      {clarifications.length ? <>
        {clarifications.map(item => <div key={item.item_id} data-reading-anchor={`goal-clarification:${item.item_id}:${item.revision}`}>{renderDocument(item.statement, `goal-correction:${item.item_id}:${item.revision}`)}</div>)}
        <div className="research-goal-lead" data-reading-anchor="lead-goal"><h4>Lead's published interpretation</h4>{renderDocument(interpreted, "goal")}</div>
        <p className="note">The study description and Lead's interpretation are from the published Phase 1 results.</p>
      </> : renderDocument(interpreted, "goal")}
    </section> : <p className="note">A Lead-interpreted goal is not available yet.</p>;
    const actions = <section className="research-resource-group"><h3>Project and goal</h3><div className="btnrow">
        <ActionButton action="edit" uiRole="research" onClick={() => setEditing(true)}>Project instructions</ActionButton>
        {interpreted && onGoal && <ActionButton action="edit" uiRole="research" aria-haspopup="dialog" onClick={onGoal}>Correct or discuss goal</ActionButton>}
      </div></section>;
    const hasNotation = hasSharedNotation(basis) || basis?.research_setting?.component_interpretations?.length > 0;
    const resources = hasNotation || basis?.generation_ref ? <>
      {hasNotation && <section className="research-resource-group"><h3>Notation</h3><ActionButton action="details" aria-haspopup="dialog" onClick={onNotation}>Notation</ActionButton></section>}
      {basis?.generation_ref && <section className="research-resource-group"><h3>Supporting reading</h3><SourceRef reference={basis.generation_ref} onOpen={onSource} label="Research basis source" /></section>}
    </> : null;
    return <section className="card research-setting" data-card-role="summary" data-reading-anchor="research-setting" aria-labelledby={`${id}-setting`}>
      <div className="card-heading"><h2 id={`${id}-setting`}>Research Setting</h2></div><div className="body">
        <ResearchCardLayout actions={actions} resources={resources} actionsLabel="Research setting actions" label="Research setting supporting reading">{clarifications.length ? <>{goal}{description}</> : <>{description}{goal}</>}</ResearchCardLayout>
    </div></section>;
  };
  return <div className="phase-one-workspace">
    <LiteratureWorkspace reading={reading} onReadingChange={onReadingChange} progress={progress} libraries={artifacts.literature_libraries} bases={artifacts.research_bases} basis={basis} setting={setting} decisions={issues} onSource={onSource} />
    {furtherWork}
    {editing && <ProjectBriefEditor project={project} activeRunCount={activeRunCount} onClose={() => setEditing(false)} onSaved={(updated) => { onSaved(updated); setEditing(false); }} />}
  </div>;
}
