import React from "react";
import { runSetupStatus } from "../runSetup";
import { ActionButton } from "./Visuals";

export default function RunSetupGuidance({ id, project, onTeamSettings, onOpenAIAccount, disabled = false }) {
  const status = runSetupStatus(project);
  return <div className="run-setup-guidance">
    <p className="note" id={id} role="status">{status.summary} Connections and runtime have not been tested here.</p>
    <div className="btnrow">
      {onTeamSettings && <ActionButton action="edit" variant="link" onClick={onTeamSettings} disabled={disabled}>Team Settings</ActionButton>}
      {status.needsOpenAI && onOpenAIAccount && <ActionButton variant="link" onClick={onOpenAIAccount} disabled={disabled}>OpenAI Account</ActionButton>}
    </div>
    {status.issues.length > 0 && <details className="run-setup-details"><summary>Setup details</summary><ul>{status.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul></details>}
  </div>;
}
