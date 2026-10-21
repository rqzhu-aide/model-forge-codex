# SPEC: Context & Artifact Delivery (normative)

This is the binding specification for how information moves through the
harness. Implementation (brief renderer, validators, UI) conforms to this
file. The type system is
defined in `architecture/system_artifact_types.md` and incorporated here
by reference. When this spec and code disagree, the code is wrong.

Status: current specification. P1 reader and P5 report descriptions were reconciled
with catalog 1.23.0 on 2026-10-13; earlier binding decisions retain their dates.
Current per-phase detail is in the [member-phase matrix](member-phase-matrix.md)
and the executable [phase contracts](../contracts/contracts/phases).
The sections below retain the dates of earlier binding decisions where useful;
the current contracts declare each stage's actual outputs and consumers.

## Model development and researcher dialogue amendment, 2026-10-11

For catalogs declaring `researcher_dialogue_v1`, versioned problem context and
explicitly scoped researcher answers govern applicable future work. Original
briefs and answers remain retained. Confirmed amendments name the item or brief
excerpt they replace; unamended instructions still apply. Origin distinguishes
researcher reports, inspected evidence, proposed assumptions, and unknowns.
P2 additional directions remain lead-only unless explicitly saved as shared context.

Every phase provides discussion without publication. Navigation and Save do not
launch science. Eligible serial single-member scientific stages can wait for an
exact response; parallel proposals and independent reviewers retain their existing
workflow. Continue uses the authorized frozen basis plus exact adopted additions,
skips completed stages, and survives restarts. Unrelated changes need an explicit
frozen-basis choice or a new request. Model or scientific scope changes require new work.

For `p5.technical_report.v1`, the technical report replaces manuscript as the
current end product. Actual relevant numerical support is required for completion;
missing support permits an interim report. Mathematical routes depend on the
claims, and relevant comparisons require an authored reason. Exact report records
retain applicable expectations and their evaluated versions. Independent review
receives exact report bytes, declared supplements, and inspectable scientific
support, without private team accounts. Offline exports embed local mathematics,
fonts, figures, source identities, completion gaps, and exact-byte review status.
Historical manuscripts retain their original families and semantics.

These rules supersede manuscript end-product and unscoped-answer descriptions
below only for projects that explicitly adopt the revised catalog. The
[implementation status](implementation-status.md) records the current boundaries.

## Researcher-facing delivery across phases

P1 uses Research Setting, Main Findings, Decisions to Discuss, Explore Individual
Papers, and Additional Runs and History, in that order. P2 separates Proposed
Methods from Select a Method to Explore, followed by decisions and further work.
P3 presents the theoretical account, scientific evidence, decisions, and further
work. P4 separates Summary, Implementation and Code, Experiments and Results,
Decisions to Discuss, and Additional Runs and History. P5 directly displays the
report with section discussions, followed by Next revision. These are reading positions,
not new artifact types or a requirement to manufacture per-card summaries.
The [UI contract](design/07-ui-contract.md) defines current action placement,
phase-specific content and shared visual meaning.

Members write explanatory fields in their existing scientific outputs during
the producing stage. Answer the research question first, then state supporting
evidence, conditions, uncertainty and the consequence for the next decision.
Detailed reasoning belongs in its designated scientific record; other sections
use a brief attributed recap and exact references. Keep qualifications beside
the claims they limit. Reviewers assess explanatory adequacy within their
permitted read sets, alongside scientific fidelity. No additional display
writer, semantic keyword gate, or presentation-only member turn is introduced.

Researcher answers and saved further-work instructions are separate control
records. Editing them does not rewrite published science or start work.
Explain more uses the exact source version in an isolated discussion and
confers no publication or repair authority.

## 0a. Direct scientific records for P1/P2 (2026-09-10, binding)

The current P1/P2 contracts supersede the earlier tier and summary rules below.
Historical pinned runs retain their original contracts. P3-P5 also use shared
scientific records alongside their declared packets and manuscript materials;
their exact output inventory comes from the pinned phase contract.

- P1 establishes the requested mathematical setting and literature landscape.
  Investigation of a particular method, including a researcher-supplied method,
  belongs in P2. Each discovery member authors one literature collection; the
  lead then authors one research basis. These are four substantive outputs.
  No separate UI cards, decision, phase summary or teammate paraphrase is
  required.
- Literature entries contain source identity, exact mathematical formulation,
  necessary assumptions, explanation, relevance, limitations and evidence
  locations. The research basis contains the setting, P2 preparation with an
  optional attributed supplied method, and cross-paper landscape organization.
  Source references resolve to attributed current entries. P1 lead corrections
  are explicit, source-grounded revisions under section 0d; original submissions
  remain available in history.
- P1 prioritizes relevant research and substantive developments in more recent
  years, including current-year work through the recorded run date. This is a
  search priority, without a fixed year cutoff. Discovery follows keywords,
  references and citing papers around recent work, retaining relevant older
  classical and foundational results for definitions, methods or comparisons.
  Use reliable sources, prioritizing primary research papers and authoritative
  publication sources; identify preprints and publication status accurately.
  The existing library does not
  replace an updated search, and ordinary cumulative retention still applies.
  Authors verify publication/revision dates and record actual search dates,
  reading extent, recent coverage and remaining date/access limits in existing
  fields. Missing dates or inaccessible sources do not justify claims of
  exhaustive or current coverage. This search priority adds no artifact,
  publication gate, method-proposal stage or separate summary writer.
- P2 retains independent proposal, cross-audit and reconciliation stages. The
  lead, theorist and analyst each propose exactly one actual method in every
  P2 mode. The lead prioritizes alignment with the researcher's objective,
  instructions and supplied idea; the theorist emphasizes mathematical
  structure, assumptions and guarantees; the analyst emphasizes estimation,
  data requirements and practical computation. These are complementary
  emphases, not permission to omit other required parts of a complete proposal.
  Each specialist audits the other specialist and the lead proposal in one
  report with two separately named targets. The lead writes one comparison
  and catalog disposition for all three, without adding a fourth method or
  silently rewriting their definitions. Six substantive outputs are required.
- The single additional-P2-input field is optional and goes only to the lead.
  An absent supplied idea does not remove the lead's proposal obligation.
  There is no separate classifier or extra writing stage. Historical pins
  retain their original optional-lead and no-proposal behavior. Specialists share
  the research setting and literature, but deterministic input views omit P1
  `phase2_preparation` and raw `researcher_origin`. After their own proposals
  close, they receive the exact lead scientific proposal for cross-audit.
  Project-wide instructions remain shared; the additional P2 field and its
  original source are delivered only to the lead.
- The UI can save additional P2 instructions in the project researcher store
  (`researcher/p2_preparation.json`). This mutable user-authored draft is not a
  published scientific record or part of the shared research setting. Loading
  it does not alter P1 artifacts or frozen run inputs. Run preparation passes
  the visible text through the existing lead-only run instruction field, which
  freezes on submission. Saving the draft does not start a run. The UI shows a
  mathematical preview directly from that same text.
- The same authoritative scientific fields serve the UI, later members and
  later phases. They are `record` outputs, not T1 display cards or T2p
  paraphrases. No 2 KB card cap, 600-character mathematics cap or blanket
  UI-only prohibition applies. Relevant exact records or sections may be
  opened from the frozen basis; do not send every member all project history.
- Authors write exact mathematics and explanatory prose during the ordinary
  producing stage. No toy examples, second display writer or automatic
  presentation-repair stage is required. Structural validation cannot certify
  scientific correctness or fabricate unavailable source content.
- The P1 UI renders the requested setting and main findings, literature tabs,
  issues and decisions, and further literature work. P2 preparation
  appears in the P2 UI as "Notes from Phase 1", directly
  from the lead's research basis, alongside additional P2 instructions and run
  controls. Setting amendments remain visibly distinct from the published
  formulation until a later authored basis incorporates them. Run preparation
  delivers current amendments and resolved-question answers to their intended
  consumers. Saving an answer is not merely hiding an item.
- Deterministic publication preserves authored content, applies the lead's
  explicit P1 corrections and builds established compatibility slots for older
  readers. It does not invent scientific prose,
  overwrite historical generations, select a method or automatically run P2.

The exact field and role inventory is in the
[artifact and card map](artifact-card-map.md)
and executable P1/P2 contracts. Remaining T1/T2p/T2s rules below apply when the
pinned contract declares those types; they do not add companion outputs or
require duplicate authoring.

## 0d. P1 scientific review and framework synthesis (2026-09-12, binding)

Catalog 1.7 requires literature-findings and research-basis schema version
1.1.0 for newly authored P1 outputs. Frozen older catalog pins and their
historical 1.0.0 records remain readable; adopting a catalog does not rewrite
published research or retrospectively claim that it was reviewed.

Keep three independent discovery invocations and one lead reconciliation.
Each role receives the common objective plus its own role_objectives entry:
the lead emphasizes formulations and research traditions, the theorist exact
mathematical statements and validity conditions, and the analyst existing
algorithms, information requirements, computational demands and reported
empirical evidence. These are overlapping emphases, not paper quotas. Every
paper entry states reading_extent and distinguishes reported from checked claims.

The lead has scientific authority to make targeted content corrections to
any collected or retained current paper entry within ordinary reconciliation.
It authors entry_corrections and scoped scientific_review inside the existing
research basis. No return-to-author scientific turn, separate review artifact,
or extra synthesis round is required. The independent discovery records remain
immutable. A correction binds the original role, family, run, entry and exact
digest; it preserves entry/source identities and changes only declared content
fields. Publication records original authorship and lead revision provenance,
and applies the authored changes deterministically. Existing bounded mechanical
repair remains separate and cannot certify scientific truth.

The landscape contains exact mathematical frameworks, variants, relationships
and existing algorithm families, with assumptions, explanations, scoped support
status, limitations and entry references. Relationships state their mathematical
reasoning and conditions; terminology alone does not establish equivalence.
The lead records actual source checks and unresolved disagreement without a
global proof-certification claim. Empty comparison arrays are valid when the
available evidence does not support a comparison. A source disposition controls
retention, not scientific agreement.

The synthesis brief supplies a deterministic entry index and selected-entry
retrieval instead of all three collection bodies. The index grants no access
to current peer drafts during discovery and generates no scientific summary.
Framework support references resolve to the final effective entry snapshot.
The UI and P2 consume those same current entries; immutable originals remain
accessible as history. Lead corrections do not add a paper or assessment count.
The setting and lead-only additional P2 instruction surfaces remain unchanged.

The October 13 P1 reader supersedes the earlier four-card presentation and
Setting/Frameworks/Papers/Coverage tabs. It reads existing authored fields and
researcher controls directly:

- Research Setting shows concise study and interpreted-goal paragraphs, with
  notation on demand and project instructions in the header.
- Main Findings shows the cited thematic synthesis and selected relevant
  approaches, with full mathematics and conditions on demand.
- Decisions to Discuss owns consequential researcher questions and responses.
- Explore Individual Papers retains search, selection, exact citations,
  mathematics and attributed assessments, including correction provenance.
- Additional Runs and History combines saved run instructions, explicit work
  controls, team tasks, search boundaries, scientific review and earlier accounts.

A supporting-entry or citation link opens the exact member assessment/version.
Return restores the originating reader position. The [UI contract](design/07-ui-contract.md#2-interaction-rules)
owns the single current brief, goal-action and whole-basis source locations.
Earlier accounts and exact source details remain secondary disclosures.
This organization adds no scientific artifact, summary author or model stage.

## 0b. Contextual researcher decisions and team tasks (2026-09-10, binding)

Every newly authored attention item uses schema_version 1.1.0 and declares
kind (`researcher_decision` or `research_task`), target_phase (P1-P5), and
nonblank context_markdown. Its original author supplies the exact relevant
mathematical formulation, defined notation, alternatives or assumptions,
source references, and the precise choice or work needed during the ordinary
artifact-producing stage. Nonmathematical work still needs scientific context;
mathematics must never be invented to satisfy a display field. The UI renders
the original Markdown and LaTeX directly, including notation in the question.

P1 setting clarifications are stored once in research_basis.attention_items
as researcher_decision targeted to P1. They appear in Issues and decisions,
with an explicit indication when researcher input is needed. Each question
retains its mathematical context, source links and latest researcher answer.
Saving displays the answer beside its question, with an Edit response action;
answers do not move into a separate saved-clarifications disclosure.
Edits preserve the original question
and source and retain earlier answers in the researcher store. Only the latest
answer enters subsequent runs; already frozen run inputs remain unchanged.
The bare clarification_questions array is retired for new outputs. Answers
amend the shared setting for subsequent runs. The separate P2 instructions
field and raw method origin remain lead-only. Answers to typed researcher
decisions targeted to P2 likewise go only to the lead during P2; specialist
views omit those raw answer records while retaining shared P1 setting answers.

Method development, proof and simulation requests are team research_task items
assigned to the corresponding phase. They appear there as follow-up work and
enter the next user-started run as frozen context, respecting method scope.
They are not requests for the user to solve or mark addressed. Literature gaps
remain in the landscape or coverage rather than becoming generic requests.

Attention is cumulative: omission is not resolution. Preserve stable identities
until explicit researcher answers or reasoned team dispositions supersede them.
Historical untyped 1.0.0 records remain readable under a collapsed "Earlier open
questions" disclosure with exact source links. Neither migration nor rendering
classifies legacy prose or supplies missing scientific context. The P1 page
orders the overview, scientific reader, issues and decisions, and further work,
as specified in section 0d. P2 shows
"Notes from Phase 1", rendering the lead-authored
`phase2_preparation.instructions_markdown` directly from the current research
basis. The additional P2 instruction field and method-development run controls
also belong in P2. This placement adds no artifact or synthesis stage and does
not change lead-only instruction routing or specialist independence.
There is no generic setting-amendment text box below the setting;
additional instructions or ideas use the P2 instruction field. The explicit
project-instruction editor and older amendment history remain accessible.
No second writer or additional scientific run is needed to display correctly
authored records.

During artifact validation, authored LaTeX must be checked with the same math
parser used by the UI. Errors identify the artifact and exact field while the
author can correct its own draft. Main objectives, constraints and comparisons
use centered display mathematics; long equations use appropriate aligned lines.
These checks validate presentation syntax, not mathematical truth. Rendering
can recover unambiguous over-escaped commands in older records without changing
their sealed contents or source digests.

## 0c. Immediate artifact checks and mechanical repair (2026-09-12, binding)

Each member can call the read-only `validate_artifacts` tool repeatedly
during its existing producing turn. It applies the pinned publication
validator's schema, reference and deterministic consistency rules to that
member's declared drafts and permitted sealed inputs. It does not expose
another member's current-stage drafts, require future-stage outputs, write
files, publish, or assess scientific correctness. Checks needing unavailable
later outputs are deferred explicitly, not reported as successful checks.
P2 independence and the P5 outside review's restricted input set still apply.

Before a downstream stage starts, the harness validates the completed stage's
collected outputs and their applicable references together. Blocking
mechanical findings return to the original output owners for up to two
automatic repair rounds per stage. Findings, briefs and original output
bytes are retained; only the named owned outputs may change, and unaffected
peer outputs remain unchanged. Each repaired candidate is collected and
checked again before it becomes input to the next stage. Repeated tool calls
inside one turn do not consume another repair round.

Unresolved findings after this bound fail the run. The existing single
researcher-authorized correction after failure remains a separate action;
it does not reset or bypass the automatic repair bound. If it changes an
earlier stage, affected downstream work uses fresh corrected inputs. Final
package validation and atomic publication remain required. Existing sealed
historical records, their catalog pins and current publication pointers are
unchanged by draft checks or failed repairs.

This changes the timing of mechanical feedback, not scientific authorship
or phase roles. There is no additional model review stage, UI summary writer,
automatic scientific revision, or assertion that schema-valid mathematics
is correct. Tool availability is recorded on SDK threads; a retained thread
without the required declaration is renewed before use.

## 0. Researcher workbench boundaries (binding)

- Scientific work and assessment discussion have different authority.
  `intent=assessment` uses the separate `p3.assessment` contract and saves
  `runs/<run_id>/assessment.json`, with terminal state `assessed`. It does
  not publish or edit theory, proofs, methods, implementation, or formal
  scientific status. Follow-up discussion uses the original assessment's
  frozen target, context, and conversation even after current theory changes.
- An explicit repair uses ordinary P3 theory revision. Its target binds
  branch, canonical theory family, generation, digest, producing run, and
  component ID. A stale repair target is refused. The selected component
  and dependent claims may change; unrelated existing mathematical content
  is preserved. The brief states the scope and includes any selected assessment.
- P3 and P4 require published P1/P2 inputs and an explicitly selected active
  method. P4 may run before P3; preliminary and comprehensive are requested
  scopes, not chronological gates. Existing theory is included when available,
  with absent theory reported honestly. P5 assembly requires P3 and P4 records.
- P4 feasibility checks verify implementation with a small controlled example,
  meaningful baseline and measured cost. Detailed evaluations begin with a
  prioritized plan tied to the researcher's intended benefit, including relevant
  performance, cost, tuning, sensitivity and assumption questions. Progressive
  execution saves the protocol before computation, runs bounded comparisons,
  inspects results and time, and records prospective plan amendments. Severe
  scientific issues and material choices pause for researcher direction; no
  role changes the mathematical method or starts P2/P3 automatically. Finish
  with available evidence stops further computation but retains theorist audit,
  lead review and publication checks. Negative and unperformed work remain
  explicit. Numerical agreement is not proof of a theoretical statement.
- A method title, card, score, or folder does not activate a method. P2
  supplies its published definition; researcher selection and activation are
  recorded in `researcher/methods.json` for the exact
  `(stable_id, version, definition_sha256)`. Activating a proposed identity
  does not rewrite the authored P2 record. A changed identity requires a new
  selection; retired methods cannot run. Readable legacy `method_changes`
  may supply the existing definition after explicit catalog adoption.
- Scientific publication prepares immutable generations and a receipt, then
  atomically commits one `current-package.json` per phase. Only that commit
  grants current authority. A prepared receipt or manifest alone is not a
  successful publication. Legacy family `current.json` pointers remain
  readable. Exact generation or digest failures never fall back to other bytes.

The [implementation status](implementation-status.md) documents current
behavior and verification limits. Historical implementation plans do not override
this specification or the current phase contracts.

## 1. Artifact types (binding, subject to the P1/P2 amendment above)

| Type | Cap | Author | Audience | Delivery |
|---|---|---|---|---|
| AGENTS.md (soul) | ~200 B | researcher | the member, every turn | auto-injected (Codex) |
| T0 title | ≤ 120 B, one line | method proposer (P2); lead may revise at P2 reconcile | UI + all members | displayed; used in mentions |
| T1 card | ≤ 2 KB (hard) | any member | **user-facing UI only** | never enters any brief |
| T2p packet | ≤ 32 KB (hard) | any member | named roles, or self | inline to named consumers |
| T2s summary | ≤ 32 KB (hard) | research_lead only | lead + researcher readers; downstream phases per §4a | inline where §4a says so; mention otherwise |
| T3m manuscript material | ≤ 128 KB advisory per source material; P5 assembly uncapped (D4) | theorist / analyst / lead | P5, stage auditors | mention only; opened on instruction (I\*) |
| T3w working files | none | any member | anyone, by path | never delivered systematically |
| T0 mention | ≤ 250 B | harness renderer (never a member) | briefs + UI | the addressing layer: title + path + digest + size |

Manuscript-material ownership split: theorist = theory & proofs;
analyst = numerical experiments & data analysis; lead = introduction,
method framing, discussion, and unowned sections.

## 2. Lifecycle (binding)

1. **Authored hot.** Every summary is written in the producing turn or the
   stage's final turn — never reconstructed later by another member.
2. **Sealed.** Collected formal outputs have per-role seals and recorded
   digests; scientific updates create new generations and one complete
   phase package. Scratch work remains mutable within its member workspace.
3. **Asymmetry.** A member's summaries are never injected into that
   member's own briefs. The author's continuity devices are the thread,
   the rotation handoff, and the notebook.
4. **Addressed means inline.** A T2p names its audience at authoring time;
   the renderer inlines it only for those members.
5. **Companion outputs follow the phase contract.** A T3m may be accompanied
   by a declared T2p handoff linking its detailed source. It does not require
   a separate T1 artifact merely because the UI displays its content in a card.
6. **T1 never enters a brief.** UI copy is not a source of truth for the
   team.

## 3. Brief assembly algorithm (binding)

For member m, stage s, branch b, the renderer assembles in order,
reporting the advisory stage payload size (§4):

1. Fixed sections: workspace mechanics · research question (verbatim) ·
   researcher instructions (verbatim) · stage objective · context ·
   output dir · own output schemas · isolation rule · execution boundary.
   Additional P2 instructions follow the lead-only recipient rule in §0a;
   they are not part of a specialist's shared fixed instructions.
2. Self-memory: notebook (I) · rotation handoff (I, once, post-rotation).
3. Binding upstream: frozen P1/P2 trunk inputs, the exact selected method,
   and applicable current-phase and sibling P3/P4 evidence on b. Decision
   conclusions and T2s use their delivery rules (§4a); canonical scientific
   records and referenced source files are opened from verified snapshots.
4. Addressed packets: T2p packets naming m, from prior stages/phases (I).
5. Instructed opens: T3m mentions with I\* instruction where s is an
   audit/implementation/integration stage per the delivery matrix.
6. Ambient mentions: T0 mentions for the remaining frozen records on b (M).
   Any cross-branch context is mention-only (D7); the current resolver does
   not automatically enumerate other method branches.
7. Never: T1 cards, T3w paths (unless a binding reference), others'
   notebooks, others' rotation handoffs.

Assessment and independent manuscript review use their explicit isolated
briefs instead of the ordinary self-memory recipe. Outside review receives
only the exact frozen readable manuscript and declared supplements, plus
its review instructions and output schema. It receives no internal verdicts,
attention queue, specialist audit, notebook, or earlier review conversation.

## 4. Stage budgets (advisory only — D8)

No hard caps, nothing demoted or truncated: the renderer reports the
assembled variable-payload size on every brief (surfaced in the run's
events) and lets the run proceed. Advisory reference points from the
2026-09-06 exercise: discovery/proposal payloads ran 3–30 KB,
reconciliation payloads 40–96 KB.

## 4a. T2s downstream delivery (D6, phase-dependent)

Inline when the next phase must *operationalize* the verdict:
P1 T2s → P2 members (I); available P3 T2s → P4 analyst (I); P4 T2s → P5 lead (I —
T2s is the lead's own synthesis tool, the sanctioned exception to the
asymmetry principle). Mention otherwise: P2 T2s → P3 (M; the P2 decision
record carries the binding content); any T2s → internal reviewers (M);
never to outside_reviewer (N, independence).

## 4b. Per-turn token ceiling (D9)

None by default. Mid-turn abort-and-rotate remains the D9 intention, not a
delivered spending guarantee. The current member setting
`max_turn_input_tokens` checks reported thread input usage after a completed
turn and may rotate before the next turn. The retained event name
`member.rotated_midturn` is historical; its message states that rotation
occurred after the turn. It does not enforce a hard per-turn cost limit.

## 5. Thread & session rules (binding)

- Persistent specialist work uses one thread per (member, phase, branch).
  The lead uses one shared project thread, whose turns are serialized across
  branches. Each assessment turn and independent outside review uses a fresh
  isolated home and thread. Assessment continuity comes from its saved
  discussion, not a reused scientific thread.
- Rotation at `auto_compact_tokens`; handoff written by the departing
  thread for its successor; handoff file consumed once, then archived.
- Optional usage threshold: current member setting with the limits in §4b.
- Codex native memory follows member-home configuration on non-Windows;
  native Windows execution disables native memory because runtime storage is
  shared. The [team contract](design/04-team-souls-and-threads.md#6-memory)
  records this platform boundary. Per-method memory is the notebook
  (per member × branch, D1). Isolated assessment and outside-review homes
  inherit no scientific notebook, rotation handoff, or earlier native memory.

## 6. UI contract (binding)

- Authored method titles label methods. Shared scientific fields supply the
  phase-specific reading cards described above; a UI card is not an artifact tier.
- T1 outputs, where declared, remain UI-only. T2s and other authored summaries
  can support the visible overview; they are not universally hidden behind a
  read-more control. Current P2 does not require a numerical scoring matrix.
- Scientific outcomes render from their authored records and remain distinct
  from successful execution. Missing results are unassessed, not favorable.
- Technical reports, historical manuscript materials, implementation accounts, figures and tables have
  readable views with exact source access. Code and other retained files remain
  inspectable without turning the main workspace into a file inventory.
- P3 graph previews and component actions resolve to the canonical theory
  generation. Assessment discussion and scientific repair are separate actions.
- P4 presents protocol questions, cases, figures and diagnostics with their
  producing-run sources. Recorded values, uncertainty, units and failed or
  unperformed observations remain accessible even when a plot is shown.
  Previous evaluations remain distinguishable and use their own sources.
- P5 shows actual claim-to-evidence links and exact reviewed-draft identity.
  TeX source is labeled as source; its existence does not imply a rendered PDF.

## 7. Validation (binding)

- Hard caps (T1, T2p, T2s): declared schema limits and artifact byte checks;
  overage is a validation finding routed as a correction.
- T3m: 128 KB advisory per source material → finding, no hard fail. Current P5
  technical reports have no venue or fixed page-length requirement; their
  completion depends on actual claim support and relevant numerical evidence.
  Historical manuscripts retain the size and scope rules of their pinned catalog.
- T0 mention minted by the renderer at seal time; never authored.
- Every stage's outputs, audiences, and the I/I\*/M/N rules for that stage
  are declared in the phase contract (contracts package increment, D12).
- The pinned catalog validates every declared output using its object, item, or
  JSONL shape, then checks identity, scientific references, graph consistency,
  applicable numerical aggregates, and source digests. This does not certify
  a proof or replay the original experiment. Old catalogs are not silently
  recertified; initial assessment requires explicit adoption of its contract.
