# Consistent presentation and shared project notation

Status: implemented source design for catalog 1.30.0, 28 October 2026. The audit
below records the earlier catalog 1.29.1 delivery/display gaps. The current source
implements neutral all-phase presentation and scoped notation snapshots,
explanation, correction requests and report delivery through the existing stages.
Existing project catalogs require explicit adoption; this is not a published
package or a claim that production model outputs already comply.

The design was revised after independent Claude Opus 5.5 xhigh review of the plan
and workflow context, and a Sol 6.1 xhigh source-boundary check. Implementation
checks, fresh guidance probes and pending review are distinguished in the
[evidence section](#implementation-evidence-and-remaining-verification).

## Intended researcher experience

The same scientific object should have the same meaning and notation whenever
the researcher meets it again. A short **Notation** link should explain the
symbols used in the account being read. The researcher should not need to manage
notation files, resolve routine naming choices or reread a large glossary.

The Lead establishes shared study notation during Phase 1 synthesis. Subsequent
members receive it with their scientific inputs, use it when writing, and define
necessary additions in their ordinary artifacts. The Lead reconciles those
additions during the existing synthesis stage. The harness retains the result
as structured, source-linked data and generates a readable `notation.md` file.

Later additions become part of the durable project notation under their method
or account scope and can be reused by subsequent work that admits those sources.
They do not overwrite Phase 1's study definitions. Every paper, candidate and
proof need not use one global alphabet.

## What the catalog 1.29.1 audit found

| Preference | State at the 1.29.1 audit | Implemented direction in 1.30.0 |
| --- | --- | --- |
| Mathematical formulation with scientific interpretation | Present in shared writing guidance and P1-P5 objectives | Preserved with source-bound notation instructions |
| Descriptive method names | P2 schema and both proposal routes name the actual framework | Neutral guidance carries the same name into later accounts without renaming history |
| Full measure names; precise definitions | Detailed rules reach P4; P5 has related statistical-writing guidance | Neutral v2 references reach relevant authors, discussions and review routes |
| Mathematical symbols only in notation | P4 guidance/display and a separate P1 setting lookup | One source-backed notation mechanism and shared lookup component |
| Computational cost beside results | Explicit in P4; other routes have their own instructions | Neutral resource/units guidance preserves phase computation permissions |
| Concise, consequential, nonduplicate inquiries | Already delivered across eligible phases | Existing filtering, optionality, answer ownership and P5 exceptions retained |
| Reused notation across phases | Local definitions, without a shared frozen view | Scoped complete incoming/final views retained with the scientific accounts |

The earlier delivery gap was explicit in
[`presentation_references.py`](../src/model_forge_codex/presentation_references.py):
v1 routed scientific references to P4 and inquiry to other ordinary phases.
V2 now routes neutral references across relevant authors and discussions; P4
field names and numerical duties live in its phase objectives. Frozen v1 runs
retain their exact earlier reference bytes and routing.

Existing source material for notation is already available:

- P1's historical `research_setting.component_interpretations` in
  [`research-basis.schema.json`](../contracts/schemas/research-basis.schema.json).
- P2: named mathematical objects, tuning parameters and defining assumptions in
  [`method.schema.json`](../contracts/schemas/method.schema.json).
- P3: exact claims, assumptions, arguments and theory sources.
- P4's historical independently authored `decision_summary.notation_markdown`.
- P5: the retained report and its declared scientific materials.

The new mechanism uses explicit scientific definitions and retained complete
views. It does not parse historical prose or legacy glossaries into an invented
core. Historical fields remain readable; new-capability authors do not create
another competing glossary.

## 1. Align the five presentation references

Keep the existing five references. Put neutral writing principles in them and
move phase-specific field names, output duties and execution permissions into
the corresponding phase objectives. Do not repeat a full style manual in every
brief or create a sixth general presentation category.

The common rules are:

1. Explain the target or finding and its scientific meaning; introduce essential
   mathematics in the account, rather than sending the reader to a table first.
2. Use descriptive framework/estimator/algorithm names and only supported
   modifiers. Keep source-provided titles and historical identities intact.
3. Write performance measures in full and identify the actual loss, averaging
   unit and uncertainty. Never infer a definition from an ambiguous error label.
4. Reserve notation for mathematical symbols used substantively in the account.
   Performance-measure labels and abbreviations stay beside results even when
   typeset mathematically. Do not invent symbols to admit ordinary glossary
   entries. A substantive population risk functional remains a model quantity.
5. Describe computational cost by its actual resource, units and measured
   operations. Elapsed time, processor time and memory are different quantities.
6. Keep evidence strength, scientific ownership and phase permissions unchanged.
7. Retain the existing concise inquiry rules, with routine scientific and naming
   choices owned by the team.

Full terms in display labels do not change programming identifiers, cited paper
titles, quoted source text or protected mathematical tokens.

### Delivery matrix

| Invocation | Presentation guidance | Notation duty |
| --- | --- | --- |
| P1 discovery members | Explanation, evidence, inquiry | Reuse existing study notation on reruns; preserve each paper's original notation |
| P1 Lead synthesis | Same plus summary | Establish or revise the shared study core |
| P2 proposers and specialist audits | Explanation, evidence, inquiry; comparison guidance when applicable | Use the shared core; define candidate-specific additions in existing method artifacts |
| P2 Lead reconciliation | Same plus summary and comparison | Adopt scoped additions and mappings without rewriting sealed original proposals |
| P3 Theorist and Analyst | Explanation, evidence, relevant display rules, inquiry | Use the exact selected-method snapshot; define proof-local symbols locally |
| P3 Lead | Same plus summary | Adopt recurring theory notation and retain local exceptions |
| P4 Analyst and Theorist | Explanation, evidence, tables/figures, inquiry | Use the method/theory snapshot; define necessary evaluation symbols |
| P4 Lead | All five | Synthesize the result and notation changes together |
| P5 assembly and revision Lead | Neutral explanation, evidence, summary and display rules; existing editorial inquiry limits | Freeze notation for the report and proof appendix |
| P5 specialist reviewers | Neutral presentation checks in their existing review instructions | Check the submitted report and declared sources; report discrepancies |
| Independent reviewer | Neutral editorial instructions and submitted materials only | See the report's notation, not hidden or newer project context |
| Targeted explanation, advice and model discussion | Relevant explanation/evidence rules and inquiry where already permitted | Use the selected source's notation and applicable saved answers |
| Report-section discussion | Neutral explanation/evidence rules only | Use the selected report/section snapshot; no new upstream elicitation |

This matrix grants no new output, computation, pause or publication authority.
The separate outside-review and report-section paths are handled explicitly.
`research_presentation_v2` gates this matrix; retained catalogs keep v1 routing.
Notation creation and consumption are separately gated by `project_notation_v1`.
Catalog validation rejects that capability without presentation v2. The immutable
P5 packet carries the four neutral editorial references once for reviewers and
the revision Lead; only the Lead retains its existing editorial inquiry guide.
A source-code upgrade alone must not change the briefs of a frozen v1 run.

## 2. One readable file, versioned scientific sources

Use a small structured `notation_updates` section in each existing Lead output:

| Phase | Existing Lead output |
| --- | --- |
| P1 | Research basis |
| P2 | Catalog assessment/reconciliation |
| P3 | Complete theory account |
| P4 | Empirical synthesis |
| P5 | Technical report candidate/revision |

Other members continue to define symbols in their existing scientific fields.
They identify proposed additions by exact field/source references, rather than
copying the entire notation table into a new companion artifact.

An adopted entry needs only:

| Field | Purpose |
| --- | --- |
| Stable quantity key | Track the same object without relying on its printed symbol |
| Symbol in LaTeX | The notation used in the new account |
| Mathematical definition | Identify the actual object, not merely its name |
| Scientific meaning | Connect it to the problem, including units/domain when relevant |
| Scope | Shared study, exact method/candidate, or exact account/section |
| Exact source reference | Locate the definition and the Lead's adoption |

An optional source-symbol mapping explains a genuine notational translation.
Each update names its exact incoming notation/source references. Entry changes
name their earlier entry/reference explicitly. A clarification
must preserve the object, conditions and source; a change of mathematical
meaning is handled as a scientific revision, not a renamed row.

The executable [update schema](../contracts/schemas/notation-updates.schema.json)
uses `incoming_sources`, `entries`, `retirements` and
`correction_dispositions`. Each array may be empty. A source is either an exact
admitted committed generation and JSON Pointer, or a declared current-run
`output_id` and field pointer. The harness binds current-run references to their
producing stage and field digest and verifies them against committed outputs on
later reads. It generates the account's `notation_snapshot` pointer and matching
files; the model does not author another complete table.

Publish adopted updates in the same immutable phase package as their scientific
account. Retain its generated complete notation view alongside it. The package
remains the authority; the Markdown file is a readable view, not an editable
second authority. The existing package pointer identifies the current account
and its notation without another global pointer or entry-history graph.

Illustrative generated files, relative to a project's existing data directory:

```text
runs/<run_id>/inputs/
  notation.json              # Complete admitted source views, preserving scopes
  notation.md                # Matching readable snapshot delivered to members
runs/<run_id>/outputs/<lead_stage>/
  notation.json              # Final account view, including adopted additions
  notation.md                # Generated from that exact final view
branches/<branch>/phases/<phase>/
  <existing family>/generations/<generation>.json
                            # Includes the Lead's adopted notation updates
```

Do not add a mutable global registry, database, new agent stage or transaction
system. A project-wide `current.md` cache is unnecessary for the first release.
The durable files are the retained account views and exact run snapshots.
Members receive only their permitted snapshot through existing delivery paths;
do not link a project-wide latest file from their briefs. This is an input-routing
rule, not a claim that workspace-write provides operating-system read isolation.

The generated final files are retained supporting artifacts declared in the
existing Lead publication, not additional model-authored scientific outputs.
Their bytes and source references must agree with the adopted update section.
The account's lookup uses its frozen incoming view plus its own committed
additions. It cannot use the incoming view alone, which would omit symbols first
introduced in that account. In P5, generate and seal the candidate's final view
with its submitted materials before review; revision produces a correspondingly
versioned candidate view.

Generate complete views from the already complete incoming source views and the
Lead's small additions or explicit mappings. Preserve each inherited entry's
definition reference, rather than making every inheriting phase its new author.
Omission from additions does not delete an incoming entry. A declared retirement
affects the new account's active view; historical sources remain available. No
reconstruction of a project-wide per-entry ancestry graph is needed.

For new-capability records, P1's lookup and P4's notation window become views of
this structure. Models must not independently author both a shared table and a
second per-card glossary. Retain old fields and readers for historical records;
never infer a notation table by parsing old prose or silently remove old rows.

## 3. Scope and consistency rules

The same quantity in the same scope reuses its adopted symbol. Different objects
must not be collapsed just because they share a letter. The target, estimator,
realized estimate, fitted parameter and uncertainty remain distinguishable.

- **Shared study:** observations, population, time origin, target and other
  genuinely common objects. Phase 1 owns this core.
- **Exact method/candidate:** parameters, objectives, fitted functions and
  method-specific quantities. Independent P2 candidates may use the same letter
  for different objects, with explicit candidate scope. Method scope uses stable
  method identity plus definition digest, matching scientific alignment. An
  editorial version can retain it; a changed definition cannot inherit it by
  matching title or branch alone. P2 reconciliation, including supplied-method
  proposal runs, owns canonical method notation. Independent candidate
  definitions remain sealed.
- **Source-local:** a paper's notation, a theorem's auxiliary variable or a
  proof's dummy index. P3 and P4 Leads own additions in their respective account
  scopes, which later permitted runs can reuse. P5 owns report exposition and
  explicit mappings. None silently changes an upstream definition.

Generated account-local entries also retain `account_scope_ref`, the exact
initial adoption reference. Inheritance preserves this anchor; an explicit
clarification names the earlier entry and carries the same anchor forward.
Unrelated accounts using the same quantity key therefore remain distinct, while
repeated views of one adopted definition share a correction owner. This uses the
retained source account, not a new registry or an entry-ancestry traversal.

The same durable file can contain the P1 study core, P2 method definitions and
reusable P3/P4 additions with their sources. A later Lead need not rerun P1 simply
to introduce a useful quantity. Replacing a canonical study or method definition,
however, belongs to its existing scientific revision route and requires support
that route is permitted to receive. Do not introduce a backward source-admission
path merely to promote a notation entry.

Bind shared definitions to exact retained setting/goal fields and relevant
accepted context revisions. Reuse generation, digest and field references; a
new global study-version identifier is unnecessary. These establish provenance,
not semantic equivalence. A newer P1 source must not reinterpret an unchanged
method or old results. A scientifically different target gets a new quantity
identity through scientific revision, while the earlier definition remains
available to interpret earlier evidence.

Population, conditioning, support, units, time horizon and denominator are part
of meaning when they affect interpretation. Unknown values remain unknown.
Do not turn a notation row into an assertion of identification, positivity,
independence or scientific validity.

A scientific cost variable such as \(C_t\), when it belongs to the model, can
belong in notation. A glossary entry called computational cost does not. Likewise,
an actual mathematical parameter \(\sigma^2\) is distinct from a table header
called empirical standard deviation.

Preserve original literature notation and canonical method/proof equations.
If exposition translates a source symbol, show its exact correspondence when
needed. Never perform a global text substitution in equations, code, citations,
proofs or stored records. A transformation such as \(Z=\log X\) is not an alias
for \(X\).

### What the Lead resolves without asking the researcher

Routine spelling, a clearer unused symbol and consistent dummy indices in newly
authored exposition are team work. Retained theorem-local indices need no
normalization. For example, using \(n\) for donors and \(m_i\) for cells from donor \(i\)
does not itself require researcher input.

By contrast, the distinction between

\[
\mu_D=\mathbb E[\mu_i],\qquad
\mu_C=\frac{\mathbb E[m_i\mu_i]}{\mathbb E[m_i]}
\]

changes donor-weighted versus cell-weighted interpretation under the stated
sampling setup. If the intended population is unsettled, use the existing
consequential-question mechanism, with mathematical alternatives and scientific
consequences. Do not disguise that target choice as a notation preference.

## 4. Member and Lead lifecycle

1. **Prepare:** resolve notation from the scientific records actually admitted
   to the run after method alignment and audience filtering. Keep distinct source
   views and deduplicate identical definition references, not matching symbols
   or prose. Freeze exact bytes,
   scope and source references at authorization.
2. **Deliver:** include a short instruction and the relevant notation text in
   ordinary member briefs. Shared study entries and the selected method's entries
   are mandatory context; the complete permitted frozen file remains available.
   Independent review receives only the submitted report's notation/materials;
   selected-source discussion receives that source's final view. Do not send an
   unfrozen path as the only delivery mechanism or bypass those exclusions.
3. **Produce:** a member follows the snapshot and defines additions at first use
   in its normal artifact. Existing notation cannot be reinterpreted silently.
   Within the run, later authorized stages can read these sealed source-local
   definitions before final Lead adoption.
4. **Audit:** existing specialist checks examine notation against mathematical
   type, meaning and scope. A string comparison cannot establish equivalence.
5. **Synthesize:** the Lead accepts additions in its owned scope, preserves
   necessary local meanings, and states mappings for the new account. It does
   not rewrite another member's sealed mathematics or upstream definitions.
   A consequential conflict uses the existing scientific correction route.
6. **Publish:** notation updates and science become visible through one existing
   phase-package commit. Failed, cancelled or uncommitted work cannot update the
   project view.
7. **Reuse:** subsequent work receives a new frozen view. Older work, retries,
   historical discussions and reports continue to use their own source versions.

Additional directions and answers with restricted audiences must not leak into
the shared notation through their raw text or an unapproved interpretation.
Only material already permitted for shared scientific publication can supply a
shared entry. P2 independent proposers do not receive sibling drafts early.
P2 currently admits P1/P2 sources, so later P3/P4 notation does not automatically
enter a new P2 proposal brief. This limit must be explicit in developer guidance;
"shared across the project" does not override phase or audience exclusions.

## 5. Concurrent work and changed definitions

Keep existing phase-package and method freshness checks. P3 and P4 may publish
truthful accounts from different frozen sources. A concurrent notation update
alone must not invalidate completed work. No cross-phase notation publication
gate, project-wide lock or entry-level conflicting-head system is required.

A later synthesis receives complete views of the scientific sources it actually
admits. Independent P3/P4 additions both survive. Identical inherited definition
references can be deduplicated; different source-local meanings stay distinct,
even when they share a symbol. No timestamp or phase-number winner is chosen.
The consuming Lead reconciles symbols needed for its exposition and cites the
specific source entries it maps. Source accounts stay unchanged.

Check each newly assembled account for internally inconsistent bindings. Scope
ownership, reference integrity and duplicate explicit keys are mechanically
checkable; mathematical equivalence is not. Existing specialist review must
assess meaning. A source-qualified disagreement does not itself block a valid
account. A contradiction within its own claimed formulation follows the existing
scientific correction path, not a new project-wide publication rule.

Reconciliation needing sources published after authorization requires a new
ordinary run. Existing repairs retain their frozen evidence. Complete final
views preserve prior adopted entries through reruns without replaying per-entry
ancestry. Check source references using existing committed-source validation;
a digest is an identity check, not proof of semantic correctness.

When a true target, constraint, population or calculation changes, the scientific
record changes through the existing goal/method revision workflow. New notation
then cites that revised source. Neither a lookup edit nor a Lead mapping can
make old theory or numerical evidence support the changed method.
Verify the existing goal-revision behavior for a changed target with an unchanged
method digest. If it does not distinguish the affected evidence, fix that
scientific compatibility path. Use existing authored dependencies and context
change notices where applicable. The UI must identify which definition an account
used and distinguish an explicitly changed target from a mere new source
generation. Do not infer scientific obsolescence from different hashes or pair
the latest study core with earlier numerical results silently.

## 6. Researcher-facing behavior

Keep existing cards. Use one shared Notation dialog, reached where the researcher
needs it. An opened scientific account always uses its retained final notation
view. Use selected-method notation only when no specific account is being read;
never fall back to today's project definitions for historical material. Use a
compact shared/method/local scope label if needed.
Essential symbols still receive a short definition in the surrounding prose.
Show account additions first, then the selected method and shared core; collapse
other admitted source scopes. Do not mechanically guess symbol relevance from
prose or require members to author another complete glossary.

- P1: reuse the Research Setting lookup; establish the shared study core.
- P2: place the lookup beside the selected method formulation. A comparison may
  show shared entries plus clearly separated candidate-specific entries.
- P3: link from the theoretical account; keep proof-local definitions near proofs.
- P4: reuse the existing Summary/Experiments triggers and one dialog.
- P5: bind the lookup to the exact report's retained notation, including its
  appendix. Use existing section/material references to distinguish main-text
  exposition and retained proofs. If P3 uses \(\kappa\) for a moment bound and P4
  uses it for bandwidth, P5 may map a symbol in its own exposition; the proof's
  lookup still resolves to the canonical P3 meaning. Include mappings in review
  materials and offline HTML. Preserve the existing permission for checked proof
  exposition, with unchanged theorem meaning and canonical source. The main
  report remains self-contained under its run-specific
  reading-scope instructions and compact reading budget; the table is not a way
  to move essential exposition out of it.

Corrections use the existing researcher-context store with a notation-correction
topic and an exact notation-entry source reference. One effective
context item owns the correction for that quantity and scoped definition; each
saved revision retains the exact source being corrected. Repeated phase links
reopen this owner, with its existing revision/history behavior. This is an
implemented resolver/API path; arbitrary notation rows are not passed to the
ordinary issue-answer endpoint.

A row can open targeted explanation through the existing assessment machinery,
with a new validated notation-entry target bound to the same exact final view.
It has no publication authority. Saving a correction records a request for
future work, not an immediate adopted definition. Report-section comments stay
report-local unless separately adopted for future scientific work. Do not
manufacture a researcher question to create a correction owner, add a second
editor elsewhere, or introduce a notation-specific counter. Existing applicable
input counts include this effective item once, excluding display mirrors.
An adopted update cites the exact saved correction revision it addresses; the UI
must not infer adoption from similar wording or from a completed run. Any later
edited correction remains distinct from that earlier adopted revision.

For each correction actually considered, the published Lead account records
whether it was adopted, kept unchanged with a short reason, or referred to the
existing scientific revision/discussion route. Omission means no recorded
disposition, not rejection or adoption. A request changing the mathematical
object cannot be adopted as a notation-only edit. The notation-specific context
filter applies source admission to the correction and its excerpt. A P4 source
must not enter P2 simply because it was
commented on. An independently saved researcher instruction may still have its
authorized future destination without importing that source. Reuse existing
input counts and state behavior; disposition creates no new counter.

Source dialogs retain their heading/close control, keyboard operation, focus
return, scroll position and exact citation identity. Polling must not close the
lookup, change its source version or reset its reading position. Old records with
no shared snapshot keep their original definitions; do not invent a current one.
If newer work publishes, offer an explicit way to open it while retaining the
current dialog's source, focus and scroll until the reader chooses to switch.

## 7. Special routes and compatibility

- **First P1 run:** no adopted notation exists yet. Discovery members define
  local terms; the Lead establishes the first core. Empty notation is legitimate
  if the setting has no useful mathematical symbols.
- **P1 rerun:** reuse the existing core. A changed scientific meaning requires
  an explicit source revision and impact on downstream work.
- **Methods supplied by the researcher:** retain the supplied text and notation;
  record interpretation/mapping separately, without replacing original content.
- **P5 independent review:** relevant notation must be in the submitted report
  or declared materials. Hidden project context must not repair an incomplete
  report for the reviewer.
- **Report-section discussion:** use the selected section/report's exact
  notation, never the current project's latest table. Discussion remains unable
  to publish updates.
- **Continuations and repairs:** retain captured notation. Existing context
  amendments do not implicitly gain authority to replace notation or reinterpret
  completed stages. Any future notation-amendment support must explicitly define
  its permitted scope; it is not required for this implementation.
- **Existing projects:** new capability requires explicit catalog adoption.
  Older projects without a shared core keep their historical local definitions.
  P2 can add method notation without inventing a P1 core. The next P1 Lead may
  establish the core from admitted explicit definitions. Do not run an unrequested
  migration or guessing pass over historical prose.
- **Offline reports:** embed exact section-scoped notation and mappings as
  anchored HTML content, readable without an API or modal script. Use the existing
  accessible math rendering and verify text alternatives in the export.
  Implementation bundles include relevant mathematical documentation only when
  part of their declared delivery. There is no existing general project-export
  feature to rely on.

## 8. Implemented hooks and validation boundaries

1. **Neutral presentation rules and routing.** The five reference files are
   neutral. `presentation_references.py` selects them from the producing catalog;
   `runs.py` and `p5_review_packet.py` handle ordinary and special routes. Phase
   objectives retain their own fields, scientific responsibilities and permissions.
2. **Notation contracts.** The existing Lead schemas carry optional historical
   fields and capability-required `notation_updates` for new work. Catalog
   validation rejects notation without v2. Current examples demonstrate source-
   backed study definitions or empty additions; explicitly legacy examples remain
   unchanged. No model stage was added.
3. **Frozen resolution and publication.** `notation.py` resolves complete views
   after scientific input alignment, freezes run inputs and generates each
   account's final view before sealing. Existing package publication makes science
   and notation visible together. Same-run definitions retain exact output-field
   references, and scope checks distinguish study, method and account ownership.
   There is no cross-phase notation freshness gate.
   An explicitly retired entry is not reactivated by a stale consumer's copy;
   each source retains its own historical active view. Definition references
   select scientific fields, and canonical shape checks send malformed updates
   through ordinary repair before generated retention.
4. **Shared lookup and report delivery.** `SharedNotation.jsx` and
   `sharedNotation.js` provide common lookup, grouping and source navigation at
   the existing P1-P5 reading locations. P5 captures the report's notation among
   submitted materials, and offline HTML embeds its retained notation and
   correspondences. Browser verification remains separate from implementation.
5. **Exact-source correction and explanation.** `notation_interactions.py`,
   the notation service endpoints and existing assessment machinery provide
   validated row targets, one editable source-bound context owner and exact
   revision dispositions. Correction text remains subject to scientific source
   admission. A saved request has no publication authority.
   An adopted disposition requires an actual update or retirement in the Lead's
   owned scope. Explicitly accepted continuation revisions are checked against
   the run's retained notation and used by retention and validation together.
6. **Compatibility and verification.** Deterministic tests exercise routing,
   source identity, scoped inheritance, corrections, publication and report
   delivery. Fresh before/after writing excerpts exist. The full regression,
   browser and independent implementation reviews have their own results; no
   complete production research run is implied by these checks.

Key source hooks are
[`runs.py`](../src/model_forge_codex/runs.py) (`compute_basis`, cumulative input
freezing, `_classify_upstream`, `_render_brief`, `_publish`),
[`records.py`](../src/model_forge_codex/records.py) (`publish_package`),
[`alignment.py`](../src/model_forge_codex/alignment.py),
[`notation.py`](../src/model_forge_codex/notation.py),
[`notation_interactions.py`](../src/model_forge_codex/notation_interactions.py),
[`problem_context.py`](../src/model_forge_codex/problem_context.py),
[`technical_reports.py`](../src/model_forge_codex/technical_reports.py),
[`migration.py`](../src/model_forge_codex/migration.py), and
[`research_sources.py`](../src/model_forge_codex/research_sources.py).

UI hooks are `PhaseOneWorkspace.jsx`/`LiteratureWorkspace.jsx`,
`MethodProposals.jsx`, `PhaseReading.jsx`, `EmpiricalQuestion.jsx`/
`EmpiricalWorkbench.jsx`, `TechnicalReportReading.jsx`, and
`SharedNotation.jsx`. The [context specification](SPEC-context-and-artifacts.md),
[member matrix](member-phase-matrix.md), [artifact/card map](artifact-card-map.md),
[artifact types](system_artifact_types.md) and [presentation reference](research-presentation.md)
record this capability without changing the existing card or output inventory.

## 9. Acceptance cases

The following remain acceptance requirements, not a claim that every case has
passed a fresh production run. Tests must inspect behavior, not only sentences
in a prompt:

1. P1 creates a source-backed core and P2 receives those exact bytes.
2. P2 candidates share study symbols but retain distinct local parameters; their
   independent proposals and IDs are unchanged by reconciliation.
3. Concurrent P3/P4 additions both publish in their own scopes. A symbol collision
   alone rejects neither account; P5 receives both and explicitly reconciles the
   meanings needed for its exposition. An out-of-scope canonical edit is rejected.
4. Target, estimator and estimate stay distinct; transformed variables are not
   accepted as aliases. Unknown units remain unknown.
5. Literature/proof-local symbols survive; no global text replacement occurs.
6. Failed publication leaves both science and notation unchanged.
7. A retry and a historical discussion keep the original snapshot after later
   notation updates. A new method does not inherit incompatible old definitions.
8. Lead-only input is not exposed in specialist context or shared notation.
9. A report and its offline export use the report's retained notation; independent
   review receives no hidden project context.
10. All relevant routes use full measure names and descriptive method titles,
    keep computational cost outside notation, and preserve precise definitions.
11. The shared dialog works by keyboard, at narrow widths and zoom, through
    nested source navigation and polling, without resetting reading position.
12. A correction is saved once, editable and counted once. Publication may record
    adopted, unchanged with reason, or referred for scientific revision. Omission
    is not a disposition; a later edited answer does not inherit an older outcome.
13. A P1 rerun supplying only additions retains earlier entries in its complete
    generated view. Source-qualified differences remain available to later
    synthesis without a traversal-order winner. Orphan files contribute none.
14. A symbol introduced during synthesis appears in that published account's
    final lookup after later project changes, including report review and export.
15. Change the target from donor-weighted to cell-weighted while leaving method
    bytes unchanged. Earlier evidence keeps its original definition; P5 cannot
    silently present it as evidence for the revised target. A mere editorial
    generation change must not trigger the same scientific claim.
16. Carry a main-text/proof symbol collision through report assembly, review,
    revision and offline HTML. Each lookup retains the correct source-local
    meaning and any explicit translation, without rewriting canonical evidence.
17. A P4-linked correction and its excerpt are excluded from P2 unless an existing
    authorized source-admission route permits them. A target-changing correction
    follows scientific revision, not notation-only adoption.
18. Notation capability requires presentation v2. Old v1 briefs remain unchanged;
    new P2 with old P1 does not fabricate a shared core. Delivery contains only
    admitted snapshots, without claiming broader filesystem read isolation.

Paired probes should include the same statistical and unfamiliar-domain contexts
before/after, with symbol collisions, a true changed target, unknown units,
an ambiguous metric, local proof notation and an old-report case. Judge scientific
meaning before consistency and concision. Then inspect full phase outputs; a
small writing probe cannot establish production reliability.

## Implementation evidence and remaining verification

Deterministic coverage is retained in
[`test_notation_contracts.py`](../tests/test_notation_contracts.py),
[`test_presentation_references.py`](../tests/test_presentation_references.py),
[`test_notation_lifecycle.py`](../tests/test_notation_lifecycle.py),
[`test_notation_run_integration.py`](../tests/test_notation_run_integration.py),
[`test_notation_interactions.py`](../tests/test_notation_interactions.py),
[`test_p5_review_packet.py`](../tests/test_p5_review_packet.py),
[`test_technical_reports.py`](../tests/test_technical_reports.py) and
[`shared-notation.test.mjs`](../web/tests/shared-notation.test.mjs).
The catalog manifest is refreshed with the repository tool. Targeted checks have
passed during implementation; the final broad-suite result is recorded separately
and is not inferred from these source links.

The fresh guidance probe used two isolated collaboration agents running
`gpt-6.1-sol` at xhigh reasoning, each started without inherited conversation
history. Both read the same synthetic task and distinct before/after guidance;
this was fresh authoring, not a provider-bridge phase run. The files retain one
[shared synthetic task](../.tmp/shared-notation-probes/common.md),
[before guidance](../.tmp/shared-notation-probes/before-guidance.md),
[after guidance](../.tmp/shared-notation-probes/after-guidance.md),
[before output](../.tmp/shared-notation-probes/before-output.md) and
[after output](../.tmp/shared-notation-probes/after-output.md), with the
[meaning-first evaluation and limits](../.tmp/shared-notation-probes/evaluation.md).
Both outputs retain
the principal evidence limits. In this case, the after excerpt distinguishes the
observed response from the population target, uses a more specific method title
and gives the formula behind mean signed error. This supports those bounded
observations, not a general writing-quality or production-reliability claim.
The probe is a short synthetic authoring task, not an executed P1-P5 workflow or
an evaluation of every structured output field. These local probe files are
ignored evidence and are not distributed with the application.
The task itself specifies several desired distinctions, so this is a bounded
compatibility check rather than a causal evaluation of guidance alone. Both
outputs remain dense, and the after inquiry repeats some target-change context.

The [implementation validation record](../.tmp/shared-notation-implementation-review/README.md)
records independent Sol 6.1 xhigh checks, two genuine Claude Opus 5.5 xhigh review
rounds, the resulting repairs and browser evidence. The combined backend suite
passed 304 checks; the final retirement refinement also passed focused lifecycle
and integration checks. All 883 frontend tests and production/runtime builds
passed. Browser checks covered all five entry points, exact proof/report views,
saved-answer editing, keyboard return, retained scroll position, narrow layout,
light/dark themes and accessible mathematics. A clean final proof-window check
had no console errors. Catalog manifest verification returned no findings.

This is focused backend validation, not a complete backend-suite pass. No fresh
complete production research run or automatic existing-project migration is
claimed. The earlier plan reviews below remain evidence about the plan, not
substitute implementation validation.

## Reader acceptance for this implementation

- **Reading purpose, P1:** understand the setting, target and genuinely shared symbols.
- **Reading purpose, P2:** distinguish candidate constructions and their exact definitions.
- **Reading purpose, P3:** interpret claims, conditions and proof-local meanings.
- **Reading purpose, P4:** interpret implementation, numerical evidence and measured resources.
- **Reading purpose, P5:** understand the complete report, its appendix and source correspondences.
  Notation supports these tasks rather than adding another required reading card.
- **Finding-first fields:** the instructions require a finding, request or
  recommendation first. A fresh after-probe example is: “Only a conditional
  argument is available under independent donors and finite fourth moments; a
  complete proof has not been checked.” This checks a synthetic excerpt, not
  compliance of every field in complete phase outputs.
- **Truthful state:** the implementation distinguishes saved feedback, Lead adoption
  and the version used in a particular account. No new optional/waiting status
  may be inferred from notation prose.
- **Optional versus waiting:** existing run/request state supplies that label;
  a notation correction is a saved request for future work and cannot pause or
  launch research by itself.
- **Precision:** preserve definitions, populations, conditioning, thresholds,
  units, denominators and evidence strength. Numbers remain source-owned.
- **Identifiers:** stable quantity and version identities stay in structured
  references; the reader sees mathematical symbols and scientific meanings.
- **Scientific meaning:** source/scope checks and meaning-first probe review
  preserve definitions, donor versus cell weighting, conditional theory,
  converged-attempt denominators, unknown units and proof-local symbols. Definitions
  retain their canonical source authority.
  Naming consistency cannot replace a changed target, proof, method or experiment.
- **Paired probe:** the same synthetic task was run with before/after guidance;
  the exact files and bounded assessment are linked above. Additional contexts,
  complete structured phase outputs and production behavior remain outside that
  probe's coverage. Browser and independent-review outcomes remain separate.

## Plan review history and limits

Earlier Sol 6.1 xhigh reviews covered all-phase guidance, storage/run architecture
and scientific reading behavior. A subsequent genuine Claude Opus 5.5 xhigh audit
reviewed the full proposed plan and five-phase workflow context, without source
code or private project records. A separate Sol 6.1 xhigh source check tested the
review's implementation assumptions.

The combined review removed unnecessary entry-ancestry machinery and cross-phase
notation publication blocking. It clarified scope ownership, changed-target
compatibility, report/proof locality, correction outcomes and input admission.
Complete retained account views preserve later Lead additions and historical
reading without a global mutable authority.

Not every suggestion was adopted: content hashes do not establish scientific
equivalence; a new source generation alone does not imply a changed target; and
moving a file outside a work directory does not prove read isolation. Do not add
an abbreviation blacklist or another approval stage. Existing context-change
notices and source references should be reused rather than replaced.

Those were plan reviews. Current implementation evidence is recorded separately
above. Structural checks establish source resolution, scope and delivery within
their fixtures; scientific adequacy and reader usefulness still need review of
full outputs and the remaining interaction evidence.
