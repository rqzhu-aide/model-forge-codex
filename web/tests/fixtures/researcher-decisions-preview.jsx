import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import IssuesCard from "../../src/components/IssuesCard";
import { Dialog } from "../../src/components/Shared";
import { decisionFixtureItems, legacyQuestion } from "./researcher-decisions.mjs";

const parameters = new URLSearchParams(location.search);
const backendProject = parameters.get("projectId");
const projectId = backendProject || "project.illustrative-decisions";
document.documentElement.dataset.theme = parameters.get("theme") === "dark" ? "dark" : "light";
const storageKey = "model-forge-illustrative-decision-answers";
const initialAnswers = [{ attention_id: legacyQuestion.attention_id, attention: legacyQuestion, question_ref: legacyQuestion.explanation_target, scope: legacyQuestion.scope, note: "The schedule remains unknown until the collection records are checked.", origin: "unknown", revision: 1 }];
let fixtureAnswers = JSON.parse(localStorage.getItem(storageKey) || "null") || initialAnswers;
const saves = [];
if (!backendProject) api.resolveAttention = async (pid, id, note, options) => {
  const attention = decisionFixtureItems.find(item => item.attention_id === id);
  if (pid !== projectId || !attention) throw new Error("This preview saves only its illustrative questions.");
  const previous = fixtureAnswers.find(answer => answer.attention_id === id);
  if (options.expected_revision !== (previous?.revision || 0) || JSON.stringify(options.expected_source) !== JSON.stringify(attention.explanation_target)) throw new Error("The exact question or saved revision changed. Reload the preview.");
  if (parameters.get("failure") === "1") throw new Error("The illustrative save failed. Your response remains in the editor. Reload without failure=1 to retry.");
  const selected = options.selection && attention.options.find(option => option.id === options.selection.option_id);
  const selection = selected && { option_id: selected.id, label: selected.label, consequence: selected.consequence, note: options.selection.note || "" };
  const canonicalNote = selection ? `Selected option: ${selection.label}\n\n${selection.consequence}${selection.note ? `\n\nYour note: ${selection.note}` : ""}` : note;
  const answer = { attention_id: id, attention, question_ref: attention.explanation_target, scope: attention.scope, note: canonicalNote, origin: options.origin, revision: (previous?.revision || 0) + 1, ...(selection ? { selection } : {}) };
  fixtureAnswers = [...fixtureAnswers.filter(item => item.attention_id !== id), answer];
  localStorage.setItem(storageKey, JSON.stringify(fixtureAnswers)); saves.push({ id, note, options });
  return { answer };
};

function Preview() {
  const [items, setItems] = useState(backendProject ? [] : decisionFixtureItems);
  const [answers, setAnswers] = useState(backendProject ? [] : fixtureAnswers);
  const [source, showSource] = useState(null); const [discussion, setDiscussion] = useState(null); const [error, setError] = useState(null);
  const refresh = async () => {
    if (!backendProject) { setAnswers([...fixtureAnswers]); return; }
    try { const pending = await api.decisionsPending(projectId); setItems(pending.attention || []); setAnswers(pending.researcher_answers || []); }
    catch (failure) { setError(failure.message); }
  };
  useEffect(() => { if (backendProject) refresh(); }, []);
  return <main style={{ maxWidth: 1000, margin: "0 auto", padding: 16 }}>
    <h1>Researcher decisions · illustrative preview</h1>
    <p>{backendProject ? "This view reads the selected test project and saves through the real API." : "These questions are illustrative. Saves stay in this browser fixture; no account or agent is used."}</p>
    {error && <p className="error" role="alert">{error}</p>}
    <IssuesCard title="Decisions to Discuss" projectId={projectId} phase={parameters.get("phase") || "P2"} branch={parameters.get("branch") || "trunk"} issues={items} answers={answers} questionsOnly onSaved={refresh} onExplain={setDiscussion} onSource={showSource} />
    {source && <Dialog title="Exact question source" onClose={() => showSource(null)}><p>The source retains its original generation and entry pointer.</p><pre>{JSON.stringify(source, null, 2)}</pre></Dialog>}
    {discussion && <Dialog title="Targeted discussion preview" onClose={() => setDiscussion(null)}><p>This fixture records the exact discussion target without starting an agent.</p><pre>{JSON.stringify(discussion, null, 2)}</pre></Dialog>}
    {!backendProject && <details className="research-details"><summary>Preview save evidence</summary><pre>{JSON.stringify(saves, null, 2)}</pre></details>}
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
