import React from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import Literature from "../../src/components/LiteratureWorkspace";
import ResearchProgress from "../../src/components/ResearchProgress";
import { literatureCollections, literatureLibrary, literatureBasis } from "./literature-updates.mjs";

createRoot(document.getElementById("root")).render(<main className="content"><h1>Two literature updates</h1><p className="note">Synthetic reading fixture. Current scopes, earlier scopes and retained papers are independently inspectable.</p>
  <ResearchProgress run={{ run_id: "run.latest", phase: "P1", state: "failed" }} retained />
  <Literature initialTab="coverage" libraries={[literatureLibrary]} collections={literatureCollections} basis={literatureBasis} onSource={(reference) => window.alert(JSON.stringify(reference, null, 2))} />
</main>);
