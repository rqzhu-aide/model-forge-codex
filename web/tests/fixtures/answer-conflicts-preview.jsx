import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import IssuesCard from "../../src/components/IssuesCard";
import { exactAnswerSnapshot, sameAnswerSource } from "../../src/answerDrafts";
import { populationChoice } from "./researcher-decisions.mjs";

// Deliberately has no backend-project mode. Both tabs share only synthetic
// fixture state in localStorage; answer drafts remain tab-local sessionStorage.
const parameters = new URLSearchParams(location.search);
const scenario = parameters.get("scenario") || "two-tabs";
const projectId = `project.answer-conflict-preview.${scenario}`;
const storageKey = `model-forge-answer-conflict-preview:${scenario}`;
const initialQuestion = { ...populationChoice, attention_id: "decision.preview.population", question: "Which patients should receive a risk prediction?" };
const initialSource = { ...populationChoice.explanation_target, object_id: initialQuestion.attention_id };
initialQuestion.explanation_target = initialSource; initialQuestion.generation_ref = initialSource;
document.documentElement.dataset.theme = parameters.get("theme") === "dark" ? "dark" : "light";
const initial = () => ({ question: initialQuestion, answers: [], saves: [] });
const read = () => JSON.parse(localStorage.getItem(storageKey) || "null") || initial();
const write = value => localStorage.setItem(storageKey, JSON.stringify(value));
const conflict = message => Object.assign(new Error(message), { status: 409 });
function savedAnswer(state, item, note, options = {}) {
  const revision = Math.max(0, ...state.answers.map(answer => answer.revision)) + 1;
  const selected = options.selection && item.options.find(option => option.id === options.selection.option_id);
  const selection = selected && { option_id: selected.id, label: selected.label, consequence: selected.consequence, note: options.selection.note || "" };
  const answer = { attention_id: item.attention_id, attention: item, question_ref: item.explanation_target, scope: item.scope, revision, origin: options.origin || "researcher_reported", note: selection ? `Selected option: ${selection.label}\n\n${selection.consequence}${selection.note ? `\n\nYour note: ${selection.note}` : ""}` : note, ...(selection ? { selection } : {}) };
  return { ...state, answers: [...state.answers.filter(previous => !sameAnswerSource(previous.question_ref, item.explanation_target)), answer], saves: [...state.saves, { note, options, returned_revision: revision }] };
}
api.decisionsPending = async pid => {
  if (pid !== projectId) throw new Error("This preview only reads its synthetic project.");
  const state = read(); return { attention: [state.question], researcher_answers: state.answers };
};
api.resolveAttention = async (pid, id, note, options) => {
  if (pid !== projectId || id !== initialQuestion.attention_id) throw new Error("This preview only saves its synthetic question.");
  const state = read();
  const original = state.answers.find(answer => sameAnswerSource(answer.question_ref, options.expected_source))?.attention;
  const target = sameAnswerSource(state.question.explanation_target, options.expected_source) ? state.question : original;
  if (!target) throw conflict("This question's source version changed; reopen the original question before saving your response.");
  const snapshot = exactAnswerSnapshot(target, state.answers);
  if (snapshot.revision !== options.expected_revision) throw conflict("Your saved response changed; reload it before saving");
  const next = savedAnswer(state, target, note, options); write(next);
  return { answer: next.answers.find(answer => sameAnswerSource(answer.question_ref, target.explanation_target)) };
};

function Preview() {
  const [state, setState] = useState(read);
  const [polling, setPolling] = useState(true);
  const refresh = () => setState(read());
  useEffect(() => {
    if (!polling) return;
    const timer = setInterval(refresh, 1000);
    const listener = event => { if (event.key === storageKey) refresh(); };
    addEventListener("storage", listener);
    return () => { clearInterval(timer); removeEventListener("storage", listener); };
  }, [polling]);
  const saveElsewhere = () => { const latest = read(); write(savedAnswer(latest, latest.question, "The saved answer in the other tab keeps the target population unknown.", { origin: "unknown" })); if (polling) refresh(); };
  const publishSuccessor = () => {
    const latest = read(), generation = `generation.preview.${Date.now()}`;
    const source = { ...initialSource, generation_id: generation, sha256: "b".repeat(64) };
    write({ ...latest, question: { ...latest.question, question: "Which patients should receive predictions under the revised design?", explanation_target: source, generation_ref: source, options: [{ id: "revised", label: "Patients in the revised design", consequence: "Applies only to the revised design." }] } });
    if (polling) refresh();
  };
  const reset = () => {
    localStorage.removeItem(storageKey);
    for (const key of Object.keys(sessionStorage)) if (key.startsWith("issue-response:") && key.includes(projectId)) sessionStorage.removeItem(key);
    location.reload();
  };
  return <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
    <h1>Answer conflicts · synthetic preview</h1>
    <p>Open this URL in two tabs. Both tabs share synthetic saved answers. Each tab keeps its own draft. No research project, account or model is used.</p>
    <div className="btnrow"><button onClick={saveElsewhere}>Save an answer in the other tab</button><button onClick={() => setPolling(value => !value)}>{polling ? "Pause refresh" : "Resume refresh"}</button><button onClick={refresh}>Refresh now</button><button onClick={publishSuccessor}>Publish a successor question</button><button onClick={reset}>Reset synthetic answers and this tab's draft</button></div>
    <p className="note">{polling ? "Refresh is active." : "Refresh is paused. A conflicting save can reach the server guard before a refresh."}</p>
    <IssuesCard title="Question and answer" projectId={projectId} phase="P2" branch="trunk" issues={[state.question]} answers={state.answers} questionsOnly onSaved={refresh} />
    <details className="research-details"><summary>Synthetic save evidence</summary><pre>{JSON.stringify(state.saves, null, 2)}</pre></details>
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
