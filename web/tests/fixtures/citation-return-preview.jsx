import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import LiteratureWorkspace from "../../src/components/LiteratureWorkspace";
import "../../src/styles.css";

// Synthetic, local display only. No requests or research records are written.
const reference = { role: "research_lead", family: "lead_literature", run_id: "run.fixture", entry_id: "entry.fixture", entry_sha256: "a".repeat(64) };
const bibliography = { source_id: "source.fixture", title: "Synthetic exact paper", authors: ["Fixture Author"], year: 2020, venue: "Fixture journal", identifiers: [] };
const card = { ...reference, source: bibliography, formulation_markdown: "$Y_i=X_i+e_i$", explanation_markdown: "Synthetic explanation. ".repeat(70) };
const basis = { branch: "trunk", phase: "P1", generation_ref: { generation_id: "basis.fixture" }, landscape: { summary_markdown: "First [Author, 2020](#cite:source.fixture).\n\n" + "Context for reading continuity. ".repeat(60) + "\n\nSecond [Author, 2020](#cite:source.fixture).", topics: [] }, citations: [{ source_id: "source.fixture", canonical_source_id: "source.fixture", entry_ref: reference, status: "available", bibliography, card }] };
const libraries = [{ branch: "trunk", phase: "P1", sources: [{ ...bibliography, cards: [card] }] }];

function Fixture() {
  const [legacy, setLegacy] = useState(false); const [epoch, setEpoch] = useState(0);
  const reading = legacy ? { paperId: "source.fixture", entrySelection: { sourceId: "source.fixture", reference, citationBasisId: "basis.fixture" }, origin: { kind: "citation", id: "source.fixture", title: "Author, 2020", anchor: "citation:basis.fixture:summary:0", position: { y: 0, offset: 0, anchor: { kind: "data-reading-anchor", value: "citation:basis.fixture:summary:0" }, disclosures: [] } } } : {};
  return <main><button onClick={() => { setLegacy(true); setEpoch((n) => n + 1); }}>Load legacy citation return</button><button onClick={() => setEpoch((n) => n + 1)}>Reset reader</button><LiteratureWorkspace key={epoch} {...{ libraries, basis, reading }} /></main>;
}
createRoot(document.getElementById("root")).render(<Fixture />);
