// Intentional synthetic scientific accounts. No live project or provider data.
export const methodIdentity = { stable_id: "method.donor-mean", version: 1, definition_sha256: "d".repeat(64) };
export const reference = (phase, family, generation = "original") => ({ phase, family, branch: phase === "P1" || phase === "P2" ? "trunk" : "method.donor-mean", generation_id: `${phase}.${family}.${generation}`, sha256: (generation === "original" ? "a" : "b").repeat(64), run_id: `run.${phase}.${generation}`, package_id: `package.${phase}.${generation}` });
export const refs = { P1: reference("P1", "research_basis"), P2: reference("P2", "catalog_assessment"), proposal: reference("P2", "method_proposal"), P3: reference("P3", "complete_theory"), P4: reference("P4", "empirical_synthesis"), P5: reference("P5", "technical_report") };
const account = (ref) => ({ phase: ref.phase, branch: ref.branch, run_id: ref.run_id, family: ref.family, method_identity: ref.phase === "P1" ? undefined : methodIdentity });
const local = (ref, section) => ({ kind: "account", phase: ref.phase, branch: ref.branch, account_family: ref.family, run_id: ref.run_id, ...(section ? { section } : {}) });
const entry = (entry_id, symbol_latex, definition_markdown, meaning_markdown, scope, source) => ({ entry_id, quantity_key: entry_id, symbol_latex, definition_markdown, meaning_markdown, scope, status: "active", definition_ref: { ...source, entry_pointer: `/notation_updates/entries/${entry_id}` }, adoption_ref: source, ...(scope.kind === "account" ? { account_scope_ref: source } : {}), source_refs: [source] });
const core = [
  entry("donor_count", "n", "$n$ is the number of independently sampled donors.", "Donors are the independent sampling units; cells from one donor are not independent donor replicates.", { kind: "study" }, refs.P1),
  entry("donor_cell_count", "m_i", "$m_i$ is the number of observed cells from donor $i$.", "Cell count may differ between donors. The observation process is not assumed to be noninformative.", { kind: "study" }, refs.P1),
  entry("target", "\\mu_D", "$\\mu_D=\\mathbb E_i[\\mu_i]$, where $\\mu_i$ is donor $i$'s mean expression.", "The target gives each donor equal weight. Expression units have not been supplied.", { kind: "study" }, refs.P1),
];
const methodEntries = [entry("ridge_penalty", "\\lambda", "$\\lambda\\ge0$ is the penalty weight in the donor-level ridge criterion.", "This is a fitting choice; it is not the population target or a performance measure.", { kind: "method", method_identity: methodIdentity }, refs.P2)];
const theoryEntries = [entry("moment_bound", "\\kappa", "$\\mathbb E[|\\mu_i-\\mu_D|^4]\\le\\kappa$.", "This proof uses $\\kappa$ as a fourth-moment bound. Its units are expression units to the fourth power.", local(refs.P3, "proof"), refs.P3)];
const empiricalEntries = [entry("bandwidth", "\\kappa", "$\\kappa>0$ is the bandwidth used in the specified smoothing sensitivity experiment.", "This evaluation-local bandwidth differs from the proof's fourth-moment bound, despite sharing a symbol.", local(refs.P4), refs.P4)];
const reportEntries = [{ ...entry("report_bandwidth", "h", "$h=\\kappa_{\\mathrm{evaluation}}$ is the bandwidth in this report's main exposition.", "The retained proof continues to use $\\kappa$ for its fourth-moment bound.", local(refs.P5, "numerical_analysis"), refs.P5), source_symbol_mapping: { source_entry_ref: { snapshot_sha256: "34".repeat(32), entry_id: "bandwidth" }, source_symbol_latex: "\\kappa", explanation_markdown: "The main account writes $h$ for the bandwidth denoted by $\\kappa$ in the retained evaluation. This correspondence preserves the bandwidth's meaning; the proof-local $\\kappa$ is a different quantity." } }];
const byPhase = { P1: core, P2: [...core, ...methodEntries], P3: [...core, ...methodEntries, ...theoryEntries], P4: [...core, ...methodEntries, ...theoryEntries, ...empiricalEntries], P5: [...core, ...methodEntries, ...theoryEntries, ...empiricalEntries, ...reportEntries] };
export const snapshots = Object.fromEntries(Object.entries(byPhase).map(([phase, entries]) => [phase, { schema_version: "1.0.0", snapshot_sha256: phase.charCodeAt(1).toString(16).repeat(32), source_ref: refs[phase], account: account(refs[phase]), sources: Object.values(refs).filter((ref) => ref.phase <= phase), entries }]));
export const records = Object.fromEntries(Object.keys(byPhase).map((phase) => [phase, { phase, branch: refs[phase].branch, generation_ref: refs[phase], notation_snapshot: { path: "notation.json", sha256: snapshots[phase].snapshot_sha256 }, _notation: snapshots[phase] }]));
const changedSource = reference("P1", "research_basis", "changed-target");
export const changedStudy = { ...records.P1, generation_ref: changedSource, notation_snapshot: { ...records.P1.notation_snapshot, sha256: "c".repeat(64) }, _notation: { ...snapshots.P1, snapshot_sha256: "c".repeat(64), source_ref: changedSource, account: account(changedSource), entries: core.map((item) => item.quantity_key === "target" ? entry("target_cell", "\\mu_C", "$\\mu_C=\\mathbb E_i[m_i\\mu_i]/\\mathbb E_i[m_i]$.", "This later target weights donors by their cell counts. It is a scientific target change, not an editorial renaming.", { kind: "study" }, changedSource) : item) } };
export const fixtureNotationViews = [...Object.values(snapshots), changedStudy._notation];

// Mirror correction ownership for the browser preview without a live service.
export function createCorrectionFixture() {
  let revision = 1;
  const items = new Map();
  const ordered = value => value && typeof value === "object" ? Array.isArray(value) ? value.map(ordered) : Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value;
  const fail = (message, status) => { const error = new Error(message); error.status = status; throw error; };
  const resolve = target => {
    const view = fixtureNotationViews.find(snapshot => snapshot.snapshot_sha256 === target?.snapshot_sha256
      && ["phase", "branch", "family", "generation_id"].every(key => snapshot.source_ref[key] === target[key])
      && snapshot.source_ref.sha256 === (target.content_sha256 || target.sha256));
    const entry = view?.entries.find(entry => entry.entry_id === target.entry_id && target.object_id === entry.entry_id);
    if (!entry) fail("The exact synthetic definition is unavailable.", 422);
    return { owner: JSON.stringify(ordered([entry.quantity_key, entry.scope, entry.scope.kind === "account" ? entry.account_scope_ref || entry.adoption_ref : null])), source: { ...structuredClone(target), notation_scope: structuredClone(entry.scope) } };
  };
  const load = target => ({ item: structuredClone(items.get(resolve(target).owner) || null), context_revision: revision, disposition: null });
  return {
    get count() { return items.size; },
    get items() { return structuredClone([...items.values()]); },
    load,
    save({ target, statement, expected_revision }) {
      if (expected_revision !== revision) fail("Saved context changed. Review the latest saved context before saving.", 409);
      const { owner, source } = resolve(target);
      const previous = items.get(owner);
      const prior = previous && Object.fromEntries(Object.entries(previous).filter(([key]) => key !== "history"));
      revision++;
      items.set(owner, { item_id: previous?.item_id || `context.notation.synthetic.${items.size + 1}`, revision: (previous?.revision || 0) + 1,
        statement, topic: "notation_correction", status: "confirmed", scope: { kind: "project" }, source_refs: [source],
        history: previous ? [...previous.history, prior] : [] });
      return load(target);
    },
  };
}
