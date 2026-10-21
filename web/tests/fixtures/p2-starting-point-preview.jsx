import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import MethodProposals from "../../src/components/MethodProposals";
import FurtherWorkCard from "../../src/components/FurtherWorkCard";
import { methodStartingPoint } from "../../src/methodSeed";

const reference = (family, version, run = "run.original") => ({ branch: "trunk", phase: "P2", family, generation_id: `${family}.${version}`, sha256: String(version).repeat(64), run_id: run, package_id: `package.${run}` });
const proposals = ["a", "b"].map((name, index) => ({ proposal_id: `proposal.${name}`, role: index ? "data_analyst" : "theorist", is_current_package: true,
  generation_ref: reference(index ? "empirical_proposal" : "theory_proposal", index + 1),
  method: { title: `Selected estimator ${name.toUpperCase()}`, identity: { stable_id: `method.${name}`, version: index + 1, definition_sha256: String(index + 1).repeat(64) }, summary: "A proposed estimating rule.", mathematical_definition: { canonical_definition: { target_or_estimand: "Estimate the population mean.", algorithm_or_update_rule: [{ operation: "Return the sample mean." }] } }, assumptions: ["The observations share a finite mean."], limitations: ["No variance bound has been established."] },
  proposed_evaluation_markdown: "Compare finite-sample error in a later evaluation.", data_requirements_markdown: "Independent scalar observations." }));
const methods = proposals.map((proposal) => ({ method_id: proposal.method.identity.stable_id, title: proposal.method.title, identity: proposal.method.identity, definition: proposal.method, status: "proposed", source_ref: reference("method_catalog", 4, "run.later.catalog") }));
const comparison = { generation_ref: reference("catalog_assessment", 1), overview_markdown: "Both retained candidates require further scientific checks.", method_dispositions: proposals.map((proposal) => ({ proposal_id: proposal.proposal_id, status: "retain", method_summary_markdown: "Compute the mean from the observed sample.", rationale: "A retained candidate with unresolved uncertainty." })) };
// Fixture endpoints never contact the backend or create research runs.
const originalFetch = window.fetch;
window.fetch = (input, options) => {
  const url = String(input);
  if (!url.startsWith("/api/v1/projects/project.p2.fixture/")) return originalFetch(input, options);
  const value = url.endsWith("/preparation") ? { instructions: url.includes("method.b") ? "Analyst seed direction" : "Theorist seed direction", revision: 1 }
    : { modes: [{ mode: "p2.full_catalog", ready: true, basis: { sha256: "fixture" } }] };
  return Promise.resolve(new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } }));
};
function Preview() {
  const [source, setSource] = useState(null);
  return <main className="content"><h1>Selected method starting point</h1><p className="note">Synthetic P2 reading fixture. No research work is executed.</p><MethodProposals projectId="project.p2.fixture" proposals={proposals} methods={methods} comparisons={[comparison]} onSource={setSource}
    furtherWork={(selection) => <FurtherWorkCard projectId="project.p2.fixture" phase="P2" branch={selection.methodId} methodId={selection.methodId} methodLabel={selection.method.title} suppliedMethod={methodStartingPoint(selection.method, selection.proposal, selection.catalogMethod)} onSource={setSource} onStarted={() => {}} history={<details className="research-details"><summary>History and original research sources</summary>{selection.modelHistory}</details>} />} />{source && <section className="card"><h2>Opened exact source</h2><pre className="record">{JSON.stringify(source, null, 2)}</pre></section>}</main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
