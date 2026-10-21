import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import ResearchProgress from "../../src/components/ResearchProgress";
import "../../src/styles.css";

// Read-only synthetic progress. This fixture never calls research endpoints.
const stage = { stage_id: "p1.discovery", label: "Member literature searches", parallel: true, total_accounts: 3 };
const accepted = { run_id: "fixture.accepted", phase: "P1", state: "published", progress: {
  stages: [{ ...stage, state: "succeeded", member_detail_available: false, received_accounts: null, members: [] }],
  publication: { label: "Literature update published", state: "completed" },
} };
const active = { run_id: "fixture.active", phase: "P1", state: "running", progress: {
  stages: [{ ...stage, state: "running", member_detail_available: true, received_accounts: 1, members: [
    { role: "research_lead", label: "Research Lead", state: "received" },
    { role: "theorist", label: "Theorist", state: "running" },
    { role: "data_analyst", label: "Data Analyst", state: "pending" },
  ] }], publication: { label: "Literature update published", state: "pending" },
} };
const failed = { run_id: "fixture.failed", phase: "P1", state: "failed" };

function App() {
  const [dark, setDark] = useState(false);
  return <main className="content">
    <h1>Research progress and retained history</h1>
    <p className="note">Synthetic reading fixture. No research runs are started.</p>
    <button onClick={() => { document.documentElement.dataset.theme = dark ? "light" : "dark"; setDark(!dark); }}>Switch to {dark ? "light" : "dark"} theme</button>
    <h2>Accepted update with incomplete member history</h2>
    <ResearchProgress run={accepted} phase="P1" retained expanded />
    <h2>Current work with one report received</h2>
    <ResearchProgress run={active} phase="P1" retained expanded />
    <h2>Failed update with retained results</h2>
    <ResearchProgress run={failed} phase="P1" retained expanded />
  </main>;
}
createRoot(document.getElementById("root")).render(<App />);
