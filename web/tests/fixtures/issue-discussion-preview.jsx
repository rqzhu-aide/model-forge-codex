import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import IssuesCard from "../../src/components/IssuesCard";
import Conversations from "../../src/components/AssumptionConversations";
import { Dialog } from "../../src/components/Shared";

// Synthetic browser fixture. All API actions stay here; no provider is contacted.
const projectId = "project.item-dialogue-preview";
const target = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "catalog_assessment", generation_id: "generation.preview", sha256: "a".repeat(64), run_id: "run.preview", package_id: "package.preview", entry_pointer: "/attention_items/0", object_id: "attention.collection" };
const issue = { issue_id: "attention.collection", attention_id: "attention.collection", phase: "P2", branch: "trunk", kind: "researcher_decision", disposition: "open", responsible_role: "data_analyst", scope: { kind: "project" }, title: "How were observation times chosen?", question: "How were observation times chosen?", why_it_matters: "A fixed schedule and measurements prompted by changing conditions require different assumptions.", context_markdown: "Let $N_i(t)$ count observations before time $t$. The observation process determines which parts of a trajectory become available.", explanation_target: target, generation_ref: target };
const previewOptions = new URLSearchParams(location.search);
document.documentElement.dataset.theme = previewOptions.get("theme") === "dark" ? "dark" : "light";
const storageKey = previewOptions.get("example") === "colors" ? "model-forge-discussion-color-preview-note" : "model-forge-item-discussion-preview-note";
let answer = JSON.parse(localStorage.getItem(storageKey) || "null");
let conversations = [], requests = [], sequence = 0;
api.resolveAttention = async (pid, id, note, options) => {
  if (pid !== projectId || id !== issue.issue_id || options.expected_revision !== (answer?.revision || 0)) throw new Error("Preview response revision changed.");
  answer = { attention_id: id, attention: issue, note, revision: (answer?.revision || 0) + 1, question_ref: target };
  localStorage.setItem(storageKey, JSON.stringify(answer));
  return { answer };
};
api.startRun = async (pid, body) => {
  if (pid !== projectId) throw new Error("Preview project only.");
  requests.push(structuredClone(body));
  const id = `preview.${++sequence}`;
  const suggestions = body.assessment_purpose === "issue_suggestions";
  conversations.unshift({ assessment_id: id, assessment_purpose: body.assessment_purpose, target: body.target, responsible_role: suggestions ? "research_lead" : "data_analyst", researcher_answer: structuredClone(answer), researcher_note_draft: body.researcher_note_draft, created_at: new Date().toISOString(), turns: [{ run_id: id, instructions: body.instructions, state: "assessed", assessment_markdown: suggestions ? "Simulated Research Lead suggestion: describe who chose the observation schedule and whether it changed with circumstances. Keep the mechanism unknown until those records are checked." : "Simulated explanation: this question asks whether observation timing was fixed in advance or changed in response to the evolving process. The distinction affects what the observed trajectories can tell us." }] });
  return { run_id: id, assessment_id: id, state: "assessed" };
};
api.assessmentMessage = async (pid, id, body) => {
  if (pid !== projectId) throw new Error("Preview project only.");
  const conversation = conversations.find(row => row.assessment_id === id);
  const run_id = `preview.${++sequence}`;
  conversation.turns.push({ run_id, instructions: body.instructions, state: "assessed", assessment_markdown: "Simulated follow-up: the original question and note snapshot remain the context for this conversation." });
  return { run_id, assessment_id: id, state: "assessed" };
};
function Preview() {
  const [, redraw] = useState(0); const [selected, select] = useState(null); const [source, showSource] = useState(false);
  const refresh = () => redraw(value => value + 1);
  return <main style={{ maxWidth: 1050, margin: "0 auto", padding: 16 }}>
    <h1>Discussion items · simulated preview</h1><p>No account is used. Notes are saved only in this browser fixture; agent responses are scripted.</p>
    <IssuesCard title="Decisions to Discuss" projectId={projectId} phase="P2" branch="trunk" issues={[issue]} answers={answer ? [answer] : []} questionsOnly onSaved={refresh} onExplain={target => select({ ...target, assessmentPurpose: target.assessmentPurpose || "model_dialogue" })} onSource={() => showSource(true)} />
    {selected && <Conversations key={JSON.stringify(selected)} projectId={projectId} target={selected} conversations={conversations} onClose={() => select(null)} onSource={() => showSource(true)} onStarted={refresh} />}
    {source && <Dialog title="Exact preview source" onClose={() => showSource(false)}><p>Observation process question, generation.preview. Synthetic source only.</p></Dialog>}
    <details><summary>Preview request evidence</summary><pre>{JSON.stringify(requests, null, 2)}</pre></details>
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
