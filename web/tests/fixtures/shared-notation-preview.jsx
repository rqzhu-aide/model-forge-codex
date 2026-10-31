import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import PhaseOneWorkspace from "../../src/components/PhaseOneWorkspace";
import MethodProposals from "../../src/components/MethodProposals";
import { PhaseOverview, TheoryReading } from "../../src/components/PhaseReading";
import EmpiricalWorkbench from "../../src/components/EmpiricalWorkbench";
import { TechnicalReportDocument } from "../../src/components/TechnicalReportReading";
import { NotationProvider } from "../../src/components/SharedNotation";
import { Dialog, ResearchDocument } from "../../src/components/Shared";
import { ActionButton } from "../../src/components/Visuals";
import { changedStudy, createCorrectionFixture, fixtureNotationViews, methodIdentity, records, refs, snapshots } from "./shared-notation.mjs";
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource-variable/ibm-plex-sans/wght-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/marcellus/400.css";
import "../../src/styles.css";

// Every request in this fixture is deterministic and synthetic. Unknown API
// routes fail rather than reaching a live service, model, or research project.
const originalFetch = window.fetch.bind(window);
const corrections = createCorrectionFixture(); const requests = [];
window.__notationFixture = { requests, corrections };
window.fetch = async (input, options = {}) => {
  const url = new URL(typeof input === "string" ? input : input.url, location.href);
  if (!url.pathname.startsWith("/api/")) return originalFetch(input, options);
  requests.push({ path: url.pathname, query: url.search, body: options.body && JSON.parse(options.body) });
  const respond = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
  if (url.pathname === "/api/__notation-fixture__/proof") return new Response("# Proof appendix\n\nThe fourth-moment condition is $\\mathbb E[|\\mu_i-\\mu_D|^4]\\le\\kappa$. Here $\\kappa$ is a moment bound, not the evaluation's bandwidth. This retained synthetic argument does not establish a live scientific result.", { headers: { "Content-Type": "text/markdown" } });
  if (url.pathname.endsWith("/notation/correction")) {
    try {
      return respond(options.method === "PUT" ? corrections.save(JSON.parse(options.body)) : corrections.load(JSON.parse(url.searchParams.get("target"))));
    } catch (error) { return respond({ detail: error.message }, error.status || 422); }
  }
  if (url.pathname.endsWith("/notation")) {
    const source = JSON.parse(url.searchParams.get("source"));
    const notation = fixtureNotationViews.find((snapshot) => snapshot.source_ref.generation_id === source.generation_id && snapshot.source_ref.sha256 === source.sha256);
    return notation ? respond({ notation }) : respond({ detail: "The exact synthetic notation is unavailable." }, 404);
  }
  if (url.pathname.includes("/records/")) {
    const [family, generation] = url.pathname.split("/records/")[1].split("/").map(decodeURIComponent);
    const view = fixtureNotationViews.find(snapshot => snapshot.source_ref.family === family && snapshot.source_ref.generation_id === generation);
    return view ? respond({ definition: "The exact synthetic source preserves its original scientific definition.", notation_updates: { entries: Object.fromEntries(view.entries.map(entry => [entry.entry_id, entry.definition_markdown])) } }) : respond({ detail: "The exact synthetic source is unavailable." }, 404);
  }
  return respond({ detail: "This synthetic preview does not contact a research service." }, 404);
};

const basis = (record) => ({ ...record, research_setting: { statement_markdown: "The study estimates population mean expression from cells nested within independent donors. Donors are the sampling units.", research_goal_markdown: record === changedStudy ? "Estimate the cell-weighted population mean $\\mu_C=\\mathbb E_i[m_i\\mu_i]/\\mathbb E_i[m_i]$. This later target weights donors by their cell counts." : "Estimate the donor-weighted population mean $\\mu_D=\\mathbb E_i[\\mu_i]$. This target gives donors equal weight even when their observed cell counts $m_i$ differ.", component_interpretations: [] }, landscape: { topics: [] } });
const method = { identity: methodIdentity, title: "Donor-level ridge mean estimator", summary: "The method fits a donor-level regularized model and retains the donor-weighted target $\\mu_D$. The penalty $\\lambda$ controls the stated fitting criterion.", scientific_question: "Can donor-level shrinkage stabilize estimation while retaining equal donor weighting?", mathematical_definition: { canonical_definition: "The fitted parameter minimizes the stated donor-level loss plus $\\lambda\\lVert\\beta\\rVert_2^2$. This synthetic fixture does not establish a bias or error guarantee." } };
const proposal = { ...records.P2, generation_ref: refs.proposal, notation_source_ref: refs.P2, proposal_id: "proposal.donor", role: "research_lead", method, is_current_package: true };
const theory = { ...records.P3, theory_generation_ref: refs.P3, claims: [{ statement_id: "claim.mean", label: "Conditional donor-level mean behavior", statement: "Under the stated independent-donor and moment conditions, analyze the donor-level estimator. The synthetic proof condition uses $\\kappa$ for a fourth-moment bound.", latex: "\\mathbb E[|\\mu_i-\\mu_D|^4]\\le\\kappa", proof_status: "conditional", depends_on: [] }], assumptions: [] };
const empirical = { ...records.P4, scientific_outcome: { conclusion: "The synthetic fixture tests scientific reading, rather than reporting a measured method comparison.", scope: "The target remains the donor-weighted mean retained with this evaluation." }, decision_summary: { method_recap_markdown: "The evaluated method estimates the donor-weighted target $\\mu_D=\\mathbb E_i[\\mu_i]$ from independent donors. Cells remain nested observations. The sensitivity experiment uses $\\kappa$ as a bandwidth.", implementation_markdown: "This interface fixture contains no executed experiment or actual researcher data.", coverage: [] } };
const reportSections = [
  ["problem", "problem-target", "Problem and target", "The target is the donor-weighted mean $\\mu_D=\\mathbb E_i[\\mu_i]$. Donors are the independent sampling units; observed cells are nested within each donor."],
  ["model", "model-definition", "Model", method.mathematical_definition.canonical_definition],
  ["existing_approaches", "existing-approaches", "Existing approaches", "This fixture does not assert a measured comparison with existing methods."],
  ["justification", "conditional-justification", "Justification", "The conditional synthetic argument uses $\\kappa$ for a fourth-moment bound. Read the [retained proof appendix](proof.md)."],
  ["numerical_analysis", "numerical-evidence", "Numerical analysis", "The main result denotes the evaluation's bandwidth by $h$. The retained proof uses $\\kappa$ for a fourth-moment bound, so these symbols identify different objects. This synthetic preview contains no numerical evidence."],
  ["limitations", "result-limitations", "Limitations", "These interface examples do not establish a scientific result or an error guarantee."],
  ["reproducibility", "fixture-reproducibility", "Reproducibility", "The preview uses deterministic synthetic records and does not contact a research service."],
];
const report = { ...records.P5, kind: "technical_report", method_identity: methodIdentity, title: "Donor-level estimation result", review_status: "not_independently_reviewed",
  body_md: "# Donor-level estimation\n\n" + reportSections.map(([, anchor, heading, text]) => `<a id="${anchor}"></a>\n\n## ${heading}\n\n${text}`).join("\n\n") + '\n\n<a id="references"></a>\n\n## References\n\nThis is an intentional synthetic fixture.',
  section_anchors: { ...Object.fromEntries(reportSections.map(([key, anchor]) => [key, anchor])), references: "references" },
  report_materials: [{ artifact_id: "proof", authored_path: "proof.md", media_type: "text/markdown", artifact_url: "/api/__notation-fixture__/proof", source_verified: true, label: "Retained proof appendix", _notation: snapshots.P3, generation_ref: refs.P3, notation_section: "proof" }] };

function Preview() {
  const [phase, setPhase] = useState("P1"); const [changed, setChanged] = useState(false); const [source, setSource] = useState(null); const [discussion, setDiscussion] = useState(null); const [saved, setSaved] = useState(0);
  const [theme, setTheme] = useState("light"); document.documentElement.dataset.theme = theme;
  const openSource = (ref) => setSource(ref);
  return <NotationProvider value={{ projectId: "notation-fixture", onSource: openSource, onDiscuss: setDiscussion, onSaved: () => setSaved(corrections.count) }}><main style={{ maxWidth: 1100, margin: "24px auto", padding: 16 }} data-reader-ready="true">
    <h1>Shared notation reading preview</h1><p className="note">Synthetic accounts only. Saved corrections are held in this page's memory.</p>
    <nav className="btnrow" aria-label="Synthetic phases">{["P1", "P2", "P3", "P4", "P5"].map((value) => <ActionButton key={value} action="details" aria-pressed={phase === value} onClick={() => setPhase(value)}>{value}</ActionButton>)}<ActionButton action="details" onClick={() => setTheme(theme === "light" ? "dark" : "light")}>Change theme</ActionButton></nav>
    <div className="btnrow"><ActionButton action="retry" onClick={() => setChanged((value) => !value)}>Publish simulated later study target</ActionButton><span className="note" role="status">{changed ? "Later study uses cell weighting. Earlier evaluation and report keep donor weighting." : "Original donor-weighted study"} · Corrections saved: {saved}</span></div>
    {phase === "P1" && <PhaseOneWorkspace project={{ project_id: "notation-fixture" }} basis={basis(changed ? changedStudy : records.P1)} onSource={openSource} />}
    {phase === "P2" && <MethodProposals proposals={[proposal]} comparisons={[]} methods={[]} cards={[]} onSource={openSource} />}
    {phase === "P3" && <><PhaseOverview phase="P3" decision={{ ...records.P3, conclusion: "The retained account states a conditional donor-level argument. Its fourth-moment bound $\\kappa$ is local to the proof." }} onSource={openSource} /><TheoryReading branch={refs.P3.branch} claimMaps={[theory]} falsificationLogs={[]} documents={[]} onSelect={() => {}} onSource={openSource} /></>}
    {phase === "P4" && <EmpiricalWorkbench branch={refs.P4.branch} summaries={[empirical]} onSource={openSource} />}
    {phase === "P5" && <section className="card" data-card-role="research"><div className="body"><TechnicalReportDocument document={report} onSource={openSource} /></div></section>}
    {source && <Dialog title="Exact synthetic source" onClose={() => setSource(null)}><ResearchDocument text={`This source retains its exact scientific definition for ${source.phase}.`} /><pre className="record">{JSON.stringify(source, null, 2)}</pre></Dialog>}
    {discussion && <Dialog title="Targeted explanation" onClose={() => setDiscussion(null)}><ResearchDocument text={discussion.statement} /><p>This synthetic explanation preserves the selected account, notation snapshot and entry. It does not run a model or adopt a definition.</p><pre className="record">{JSON.stringify(discussion, null, 2)}</pre></Dialog>}
  </main></NotationProvider>;
}
const previewRoot = import.meta.hot?.data.previewRoot || createRoot(document.getElementById("root"));
previewRoot.render(<Preview />);
if (import.meta.hot) {
  import.meta.hot.accept();
  import.meta.hot.dispose(data => { data.previewRoot = previewRoot; window.fetch = originalFetch; });
}
