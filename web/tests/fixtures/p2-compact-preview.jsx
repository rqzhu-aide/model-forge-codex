import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import MethodProposals from "../../src/components/MethodProposals";
import { Dialog, ResearchDocument } from "../../src/components/Shared";
import { sourceEntry } from "../../src/researchContent";

// All scientific content and identities below are illustrative fixture records.
// This page uses local state only and cannot save instructions or start work.
const ref = (family, name, run = "run.current") => ({ branch: "trunk", phase: "P2", family, generation_id: name, sha256: "a".repeat(64), run_id: run, package_id: `package.${run}` });
const current = { proposal_id: "proposal.current", role: "theorist", generation_ref: ref("theory_proposal", "proposal.current"),
  method: { title: "Constrained ridge estimator", identity: { stable_id: "method.current", version: 2, definition_sha256: "b".repeat(64) },
    summary: "Estimate a coefficient vector from observed responses and predictors using a constrained squared-error criterion.",
    scientific_question: "How does a sum constraint change the fitted coefficient vector?",
    mathematical_definition: { canonical_definition: {
      target_or_estimand: { symbol: "\\beta", definition: "The fitted coefficient vector for the supplied design and responses." },
      input_information: { symbol: "X,y", definition: "Observed $X\\in\\mathbb R^{n\\times p}$ and $y\\in\\mathbb R^n$." },
      objective_or_estimating_equation: { definition: "$$\\widehat\\beta=\\arg\\min_{\\beta\\in C}\\left\\{\\frac{\\|y-X\\beta\\|_2^2}{2n}+\\frac{\\lambda}{2}\\|\\beta\\|_2^2\\right\\}.$$" },
      constraints_and_normalization: [{ definition: "$$C=\\{\\beta\\in\\mathbb R^p:\\mathbf1^\\top\\beta=0,\\;\\beta_j\\ge-1\\}.$$" }],
      algorithm_or_update_rule: [{ order: 1, operation: "Solve the constrained quadratic problem." }, { order: 2, operation: "Return the fitted coefficients and fitted responses." }],
      tuning_definition: [{ symbol: "\\lambda", admissible_values: "$\\lambda>0$", selection_rule: "Fix the penalty before the illustrative evaluation." }],
      calculation_defining_assumptions: [{ statement: "The supplied design and responses are finite; the constraint set is nonempty.", mathematical_role: "Makes the proposed optimization well defined." }],
      custom_output_definition: { prediction: "Return $x_{\\rm new}^\\top\\widehat\\beta$ for a supplied new predictor." },
    }, computational_consequences: ["The quadratic solve grows with the number of predictors."] },
    assumptions: ["The supplied design and responses are observed."], limitations: ["This illustration makes no statistical coverage claim."],
    literature_provenance: [{ citation_id: "fixture.reference", relation: "benchmark", contribution: "Illustrative source association retained for testing." }] },
  computational_profile: { per_iteration_markdown: "A dense gradient costs $O(np)$.", memory_markdown: "Store the $n\\times p$ design.", scaling_markdown: "Dense storage grows with both dimensions." },
  data_requirements_markdown: "Observed response and design rows.", proposed_evaluation_markdown: "Evaluate constraint satisfaction in a later study." };
const earlier = { ...current, proposal_id: "proposal.earlier", is_current_package: false, generation_ref: ref("theory_proposal", "proposal.earlier", "run.earlier"), method: { ...current.method, title: "Earlier unconstrained ridge estimator", identity: { ...current.method.identity, version: 1, definition_sha256: "c".repeat(64) }, summary: "The earlier authored summary uses a positive penalty and returns fitted coefficients.", mathematical_definition: { canonical_definition: { objective_or_estimating_equation: { definition: "$$\\widehat\\beta=(X^\\top X+n\\lambda I)^{-1}X^\\top y.$$" }, tuning_definition: [{ symbol: "\\lambda", selection_rule: "The complete earlier penalty rule stays in the record." }] } } } };
const methods = [{ method_id: "method.current", title: current.method.title, identity: current.method.identity, definition: current.method, status: "proposed", source_ref: ref("method_catalog", "catalog.current") },
  { method_id: "method.catalog-only", title: "Catalog-only mean estimator", identity: { stable_id: "method.catalog-only", version: 1, definition_sha256: "d".repeat(64) }, status: "active", source_ref: ref("method_catalog", "catalog.only"), definition: { summary: "Return the sample mean from finite observed scalar values.\n$$\\widehat\\mu=n^{-1}\\sum_{i=1}^{n}Y_i.$$", mathematical_definition: { canonical_definition: { target_or_estimand: "The population mean when that quantity exists." } }, limitations: ["No uncertainty estimate was preserved in this legacy catalog record."] } }];
const comparison = { generation_ref: ref("catalog_assessment", "assessment.current"), catalog_pin: { catalog_version: "1.24.0", catalog_manifest_sha256: "e".repeat(64) }, overview_markdown: "The constrained candidate and catalog-only mean estimator answer different questions. Neither has a completed evaluation in this fixture.", comparison_markdown: "The complete original comparison remains available in the shared history.", method_dispositions: [{ proposal_id: current.proposal_id, status: "retain", method_summary_markdown: "For observed responses $y$ and design $X$, fit coefficients by solving\n$$\\widehat\\beta=\\arg\\min_{\\beta\\in C}\\left\\{\\frac{\\|y-X\\beta\\|_2^2}{2n}+\\frac{\\lambda}{2}\\|\\beta\\|_2^2\\right\\},\\qquad C=\\{\\beta:\\mathbf1^\\top\\beta=0,\\;\\beta_j\\ge-1\\}. $$\nReturn $\\widehat\\beta$ and predictions $x_{\\rm new}^\\top\\widehat\\beta$. This needs finite observed inputs, a nonempty constraint set and a fixed $\\lambda>0$. It proposes an estimator and makes no checked coverage claim.", rationale: "The constraint changes the eligible coefficients; its scientific suitability remains unresolved." }] };
const oldComparison = { generation_ref: ref("catalog_assessment", "assessment.earlier", "run.earlier"), is_current_package: false, catalog_pin: { catalog_version: "1.23.4", catalog_manifest_sha256: "f".repeat(64) }, comparison_markdown: "Earlier original comparison.", method_dispositions: [{ proposal_id: earlier.proposal_id, status: "retain", method_summary_markdown: "Full historical procedural account begins here.\n\n" + "Every original procedural qualification stays available. ".repeat(30) + "\n\nFull historical procedural account ends here.", rationale: "Earlier authored assessment." }] };
const records = [current, earlier, comparison, oldComparison, ...methods.map(method => ({ ...method.definition, generation_ref: method.source_ref }))];
function Preview() {
  const [source, setSource] = useState(null); const [reading, setReading] = useState({}); const [pick, setPick] = useState(""); const [opened, setOpened] = useState("");
  const original = source && records.find(record => record.generation_ref.generation_id === source.generation_id);
  return <main className="content"><h1>Compact P2 reader fixture</h1><p className="note">Synthetic records. All controls operate locally; no research or saved instructions are created.</p>
    <button type="button" className="btn" onClick={() => { document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; }}>Toggle theme</button>
    <MethodProposals methods={methods} proposals={[current, earlier]} comparisons={[comparison, oldComparison]} literatureSources={[{ source_id: "fixture.reference", title: "Illustrative reference", identifiers: [{ kind: "url", value: "https://example.org/source" }] }]} initialPick={pick} onPick={setPick} reading={reading} onReadingChange={patch => setReading(saved => ({ ...saved, ...patch }))} onSource={setSource} onContinue={(method, phase) => setOpened(`${phase} · ${method.method_id} · version ${method.identity.version}`)}
      issues={context => <section className="card" data-card-role="attention"><div className="card-heading"><h2>Decisions to Discuss</h2></div><div className="body"><p>{context.method.title}: no unanswered fixture questions.</p></div></section>}
      furtherWork={context => <details className="card further-work" data-card-role="action"><summary className="card-heading"><h2>Additional Runs and History</h2></summary><div className="body"><p>Illustrative additional work for {context.method.title}.</p><details className="research-details" data-reading-anchor="research-history"><summary>History and original research sources</summary>{context.modelHistory}</details></div></details>} />
    {opened && <p role="status">Locally opened {opened}. No run was started.</p>}
    {source && <Dialog title="Exact fixture source" onClose={() => setSource(null)} returnFocus={() => document.querySelector('[data-reading-anchor="p2-selected-model"]')}><ResearchDocument text={sourceEntry(original, source.entry_pointer)} /><pre className="record">{JSON.stringify(source, null, 2)}</pre></Dialog>}
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
