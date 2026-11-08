import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../../src/api";
import ProjectView from "../../src/components/ProjectView";
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource-variable/ibm-plex-sans/wght-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/marcellus/400.css";
import "../../src/styles.css";

// This fixture has no real-project mode and no accepted write operation.
// Unknown API calls fail locally instead of reaching a research service.
const params = new URLSearchParams(location.search);
const projectId = "project.synthetic-phase-states";
const branch = "method.synthetic";
const identity = { stable_id: branch, version: 1 };
let paused = params.get("pause") !== "off";
const requests = [], rejected = [];
const reject = name => async () => { rejected.push(name); throw new Error(`The synthetic phase preview rejects ${name}; no research service is contacted.`); };
for (const name of Object.keys(api)) api[name] = reject(name);
api.startRun = reject("startRun");
const fetchStatic = window.fetch.bind(window);
window.fetch = (input, options) => {
  const url = new URL(typeof input === "string" ? input : input.url, location.href);
  return url.pathname.startsWith("/api/") ? reject(`HTTP ${url.pathname}`)() : fetchStatic(input, options);
};
const source = (phase, family = "research_basis") => ({ branch: ["P1", "P2"].includes(phase) ? "trunk" : branch,
  phase, family, generation_id: `generation.synthetic.${phase}`, sha256: "a".repeat(64), run_id: `run.synthetic.${phase}`, package_id: `package.synthetic.${phase}` });
const basis = { branch: "trunk", phase: "P1", generation_ref: source("P1"), research_setting: {
  statement_markdown: "This synthetic study compares estimators of a donor-level population mean. It contains no observed scientific result.",
  research_goal_markdown: "Estimate the donor mean $\\mu_D=\\mathbb E_i[\\mu_i]$ while treating donors as the independent sampling units.",
  component_interpretations: [],
} };
const questions = ["Which population should the estimate describe?", "What donor counts are available?"].map((question, index) => {
  const reference = { ...source("P1", "attention_items"), kind: "phase_issue", object_id: `question.synthetic.${index}`, entry_pointer: `/attention_items/${index}` };
  return { attention_id: reference.object_id, phase: "P1", target_phase: "P1", branch: "trunk", kind: "researcher_decision",
    disposition: "open", severity: "major", responsible_role: "research_lead", scope: { kind: "project" },
    question, response_kind: "study_fact", context_markdown: "This unanswered synthetic question remains separate from the paused theory run.",
    likely_consequence: "An answer would refine future work in this preview's example.", explanation_target: reference, generation_ref: reference };
});
const pauseRequest = { request_id: "request.synthetic.pause", revision: 1, stage_id: "p3.synthetic", phase: "P3", branch,
  question: "Which dependence condition should the theory use?", reason: "This synthetic run is actually waiting for researcher direction.",
  context_markdown: "This fixture intentionally pauses the theory run so the header and Next route can be inspected.",
  scope: { kind: "model", method_id: branch, model_ref: identity }, evidence_refs: [], source_refs: [] };
const runs = () => [
  { run_id: "run.synthetic.P1", phase: "P1", branch_id: "trunk", mode: "p1.explore", state: "published", created_at: "2026-11-02T10:00:00Z" },
  { run_id: "run.synthetic.P2", phase: "P2", branch_id: "trunk", mode: "p2.full_catalog", state: "running", created_at: "2026-11-02T11:00:00Z" },
  ...(paused ? [{ run_id: "run.synthetic.P3", phase: "P3", branch_id: branch, mode: "p3.develop", state: "awaiting_user", created_at: "2026-11-02T12:00:00Z", researcher_pause: { pending_request: pauseRequest, saved_answers: [] } }] : []),
  { run_id: "run.synthetic.P4", phase: "P4", branch_id: branch, mode: "p4.preliminary", state: "failed", created_at: "2026-11-02T13:00:00Z", terminal_reason: "The synthetic interrupted attempt retained no experiment result." },
];
const project = { project: { project_id: projectId, name: "Donor mean estimation: synthetic phase states", research_instructions: basis.research_setting.statement_markdown },
  problem_context: { revision: 1, items: [], proposals: [] }, members: {}, catalog: { version: "synthetic-preview" },
  workflow_capabilities: { researcher_dialogue: true, technical_report: true } };
const method = { method_id: branch, branch_id: branch, title: "Synthetic donor estimator", identity, current_identity: identity,
  definition: { identity, title: "Synthetic donor estimator", summary: "A synthetic method entry for phase-navigation validation." } };
const read = (name, response) => {
  api[name] = async (...args) => {
    if (args[0] !== projectId) throw new Error("This fixture only reads its synthetic project.");
    if (args.at(-1)?.signal?.aborted) throw new DOMException("Abandoned synthetic read", "AbortError");
    requests.push(name); return structuredClone(typeof response === "function" ? response(...args) : response);
  };
};
read("project", project);
read("branches", { branches: [{ branch_id: "trunk", phases: { p1: ["synthetic"] } }, { branch_id: branch, method, phases: {} }] });
read("listRuns", () => ({ runs: runs() }));
read("artifacts", { research_bases: [basis], issues: questions });
read("decisionsPending", () => ({ attention: questions, researcher_answers: [], runs_awaiting_direction: runs().filter(run => run.state === "awaiting_user"), runs_needing_correction: [] }));
read("readiness", (pid, selectedBranch, phase) => ({ ready: false, reasons: ["Synthetic preview: run submission is disabled."], modes: [], basis: { records: [source(phase)], sha256: `synthetic:${selectedBranch}:${phase}` } }));
read("records", { records: [] });
read("assessments", { assessments: [] });
read("methods", { methods: [method], diagnostics: [] });
read("run", (pid, runId) => runs().find(run => run.run_id === runId) || null);
read("problemContext", project.problem_context);
read("phasePreparation", { revision: 1, instructions: "", input_ids: [] });
read("phaseTwoPreparation", { instructions: "" });
read("inputs", { inputs: [] });
window.__phaseStateFixture = { requests, rejected, runs, questions, get paused() { return paused; } };

function Preview() {
  const [context, setContext] = useState({ phase: ["P1", "P2", "P3", "P4", "P5"].includes(params.get("phase")) ? params.get("phase") : "P1", branch });
  const [reading, setReading] = useState({}); const [revision, setRevision] = useState(0);
  const [showPause, setShowPause] = useState(paused); const [theme, setTheme] = useState(params.get("theme") === "dark" ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
  return <>
    <section aria-label="Synthetic preview controls" style={{ padding: 12 }}>
      <p className="note">Synthetic phase states. Phase 1 is published with two unanswered questions; Phase 2 is running; Phase 3 is paused; Phase 4 was interrupted. All research-service requests and writes are blocked.</p>
      <div className="btnrow"><button type="button" onClick={() => { paused = !showPause; setShowPause(paused); setRevision(value => value + 1); }}>{showPause ? "Remove synthetic pause" : "Restore synthetic pause"}</button>
        <button type="button" onClick={() => setTheme(value => value === "light" ? "dark" : "light")}>Change theme</button></div>
    </section>
    <div id="app" style={{ gridTemplateColumns: "minmax(0, 1fr)" }}><main><ProjectView projectId={projectId} context={context} reading={reading}
      onContextChange={changes => { setContext(value => ({ ...value, ...changes })); setReading({}); }} onReadingChange={changes => setReading(value => ({ ...value, ...changes }))}
      settingsRevision={revision} onOpenRun={() => {}} onProjectUpdated={() => {}} onTeamSettings={() => {}} onOpenAIAccount={() => {}} /></main></div>
  </>;
}
createRoot(document.getElementById("root")).render(<Preview />);
