import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import PhaseOneWorkspace from "../../src/components/PhaseOneWorkspace";
import example from "./p1-visible-math-preview.json";
import "../../src/styles.css";

// Exact catalog snapshots, with only display metadata and the authored correction
// projected locally. The original example objects remain unchanged.
const { research_basis: originalBasis, literature_findings: literature, catalog_pin: pin } = example;
const cards = literature.papers.map((paper) => {
  const binding = originalBasis.landscape.citation_refs.find((item) => item.entry_ref.entry_id === paper.entry_id);
  const correction = originalBasis.entry_corrections.find((item) => item.target.entry_id === paper.entry_id);
  const original = { ...paper, ...binding.entry_ref, entry_sha256: correction?.target.entry_sha256 || binding.entry_ref.entry_sha256, catalog_pin: pin };
  return correction ? { ...original, ...correction.changes, entry_sha256: binding.entry_ref.entry_sha256, assessment_history: [original], lead_revision: { correction } } : original;
});
const sources = cards.map((card) => ({ ...card.source, cards: [card] }));
const basis = { ...originalBasis, catalog_pin: pin, generation_ref: { generation_id: "basis.catalog.example" }, citations: originalBasis.landscape.citation_refs.map((binding) => {
  const card = cards.find((item) => item.entry_id === binding.entry_ref.entry_id);
  return { ...binding, canonical_source_id: card.source.source_id, status: "available", bibliography: card.source, card };
}) };
const artifacts = { literature_libraries: [{ branch: "trunk", phase: "P1", sources }] };

// Even the real project editor cannot write to a backend from this local fixture.
window.fetch = () => Promise.reject(new Error("This illustrative catalog example has no API access."));

function Preview() {
  const [source, setSource] = useState(null);
  const [theme, setTheme] = useState("light");
  const chooseTheme = (value) => { document.documentElement.dataset.theme = value; setTheme(value); };
  return <main>
    <h1>P1 visible mathematics</h1>
    <p className="note">Illustrative catalog example, not a live study. Uses catalog {pin.catalog_version} example text and its recorded correction. No API or model calls are made; no scientific verification is claimed.</p>
    <div className="btnrow"><button aria-pressed={theme === "light"} onClick={() => chooseTheme("light")}>Light</button><button aria-pressed={theme === "dark"} onClick={() => chooseTheme("dark")}>Dark</button></div>
    <PhaseOneWorkspace project={{ project_id: "project.catalog.example", name: originalBasis.title, research_instructions: "Illustrative catalog example for local rendering validation." }} basis={basis} artifacts={artifacts} reading={{ paperId: sources[0].source_id }} onSource={setSource} onSaved={() => {}} />
    {source && <section className="card"><div className="card-heading"><h2>Local example reference</h2></div><div className="body"><pre className="record">{JSON.stringify(source, null, 2)}</pre></div></section>}
    <details className="research-details"><summary>Exact snapshot provenance</summary><pre className="record">{JSON.stringify(example.source_sha256, null, 2)}</pre></details>
  </main>;
}

createRoot(document.getElementById("root")).render(<Preview />);
