import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { PhaseOverview, TheoryReading } from "../../src/components/PhaseReading";
import Assessments from "../../src/components/Assessments";
import TestedTheorySource from "../../src/components/TestedTheorySource";
import { Dialog, ResearchDocument } from "../../src/components/Shared";
import { theoryComponentRequest } from "../../src/runRequests";
import "../../src/styles.css";

// Fictional, read-only display fixture. Actions preview their exact targets;
// they never call research endpoints or create runs.
const reference = { branch: "method.conditions", phase: "P3", family: "theory_record", generation_id: "theory.current", sha256: "a".repeat(64), run_id: "run.current" };
const earlier = { ...reference, generation_id: "theory.earlier", sha256: "b".repeat(64), run_id: "run.earlier" };
const assumption = {
  assumption_id: "assumption.regularization", label: "Vanishing regularization",
  text: String.raw`The tuning sequence satisfies $\lambda_n\to0$.`,
  strength: String.raw`The argument additionally uses $\sqrt{n}\lambda_n\to0$.`,
  sensitivity: String.raw`Dropping $\sqrt{n}\lambda_n\to0$ removes the recorded guarantee for consistency. It does not demonstrate failure of $\widehat\theta_n$. A uniform remainder bound is still needed.`,
};
const claim = {
  statement_id: "statement.consistency", label: "Conditional consistency", text: "The estimator is consistent under the stated conditions.",
  latex: String.raw`\widehat\theta_n\xrightarrow{p}\theta_0`, proof_status: "sketch", status: "conditional",
  regime: String.raw`As $n\to\infty$, require $\lambda_n\to0$ and $\sqrt{n}\lambda_n\to0$.`,
  quantifiers: [String.raw`For every $\varepsilon>0$, $\Pr(\lvert\widehat\theta_n-\theta_0\rvert>\varepsilon)\to0$.`],
  assumption_ids: [assumption.assumption_id], depends_on: [assumption.assumption_id],
  justification: { kind: "proof_sketch", summary: String.raw`The recorded argument controls a remainder involving $\sqrt{n}\lambda_n$.`, open_obligation: "A uniform remainder bound remains open.", artifacts: [{ title: "Declared argument", locator: "Lemma 2" }] },
};
const oldAssumption = { ...assumption, sensitivity: "The earlier source did not establish the consequence of removing this condition. The consequence remained unknown." };
const assessment = { assessment_id: "assessment.earlier", title: "Assessment of the earlier condition", state: "assessed", target: { ...earlier, object_id: assumption.assumption_id, kind: "assumption" }, summary: "The earlier check left the consequence unknown. This saved finding remains attached to the earlier theory.", limitations: ["No boundary example was performed."], messages: [{ role: "researcher", content: "Could a weaker condition suffice?" }] };

function App() {
  const [selected, setSelected] = useState(assumption.assumption_id);
  const [dialog, setDialog] = useState(null);
  const [dark, setDark] = useState(false);
  const source = (target) => setDialog({ title: "Exact recorded source", target });
  const request = (intent, target, label) => { const options = theoryComponentRequest(intent, target, label); if (options) setDialog({ ...options, preview: true }); };
  return <main style={{ maxWidth: 1180, margin: "auto", padding: 20 }}>
    <h1>Theory qualification verification</h1>
    <button onClick={() => { document.documentElement.dataset.theme = dark ? "light" : "dark"; setDark(!dark); }}>Switch to {dark ? "light" : "dark"} theme</button>
    <PhaseOverview phase="P3" decision={{ conclusion: "Consistency is conditional. The available argument remains a sketch, and dropping the condition removes a guarantee without demonstrating failure." }} onSource={source} />
    <TheoryReading branch={reference.branch} selected={selected} onSelect={setSelected} onRequest={request} onSource={source} onAssumptionConversation={(target) => setDialog({ title: "Explain this assumption", target, instructions: "This conversation retains the exact theory source and assumption identity." })}
      claimMaps={[{ branch: reference.branch, phase: "P3", theory_generation_ref: reference, claims: [claim], assumptions: [assumption] }]}
      falsificationLogs={[{ branch: reference.branch, phase: "P3", probes: [{ probe_id: "probe.boundary", target_statement: claim.statement_id, method: "Boundary example", outcome: "not_tested", detail: "The boundary example has not been performed." }] }]}
      assessments={<Assessments projectId="fixture.theory" assessments={[assessment]} onSource={source} embedded />} />
    <section className="card" data-card-role="research"><h2>Historical theory used by an experiment</h2><div className="body"><TestedTheorySource document={{ statements: [claim], assumptions: [oldAssumption] }} componentId={claim.statement_id} onCurrentTheory={() => setSelected(claim.statement_id)} /></div></section>
    <section className="card" data-card-role="attention"><h2>Issues and decisions</h2><div className="body"><ResearchDocument text="The uniform remainder bound is a mathematical obligation. Further investigation awaits a researcher request." /></div></section>
    <section className="card" data-card-role="action"><h2>Further theory work</h2><div className="body"><ResearchDocument text="A theory revision can investigate the bound or narrow the supported conclusion. An assessment saves a separate check." /></div></section>
    {dialog && <Dialog title={dialog.title} onClose={() => setDialog(null)}><ResearchDocument text={dialog.instructions || "This fixture displays the exact recorded source identity."} /><pre className="record">{JSON.stringify(dialog.target, null, 2)}</pre>{dialog.preview && <p className="note">Read-only request preview. No run is started.</p>}</Dialog>}
  </main>;
}
createRoot(document.getElementById("root")).render(<App />);
