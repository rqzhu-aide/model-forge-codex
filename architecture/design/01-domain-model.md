# Design 01: Domain Model

The objects Model Forge (Codex edition) manages. Record *shapes* are pinned
by the universal contract catalog (`model-forge-contracts`, ADR-007); this
document defines identity, relationships, and lifecycle.

The descriptions below include the implemented researcher workbench. P1 reading
and P5 report readiness were reconciled with catalog 1.23.0 on 2026-10-13.
Unimplemented parts of the original lifecycle and configuration model are
identified explicitly rather than treated as current behavior.

## 1. Identity conventions

- `project.<slug>.<hex>` — a research project.
- `method.<slug>` + integer version + `definition_sha256` — a method's
  stable identity (unchanged from the other editions).
- `branch` id: `trunk` or the selected method's stable ID. The trunk is everything
  before/independent of method proliferation (P1, P2, project-level state).
- `run.pN.<mode>.<hex>` — one phase run.
- `thread_key = (member, phase, branch_id)` — the logical conversation a
  specialist maintains (ADR-002). The lead uses one project-wide key.
  Rotation can replace a physical thread under a logical key; each run records
  the actual thread IDs used. Outside review uses a fresh isolated session.
- `generation.<hex>` — one published immutable generation of a formal
  record.
- `receipt.<hex>` — one publication receipt.

## 2. Core objects

### Project
Root container. Holds identity, creation metadata, project instructions,
member configuration, and branch stores. Older venue preferences remain historical metadata. Project instructions
contain the research question, direction, and constraints in one editable field
in P1. Older split question/instruction fields are combined when read. Each run
freezes the project brief in its basis; subsequent edits apply to new runs.
Versioned problem context retains researcher statements, their origin and exact
project or model scope. Explicit corrections identify the items or brief excerpts
they amend. Team interpretations remain proposals until adopted. Answers and
eligible continuation amendments retain exact question and response versions.
The original run basis stays immutable; report generations capture their own
authorized context additions. The current technical report has a separate record
family from historical manuscripts, and completion is distinct from independent review.
The workbench's
selected project, method, phase, and component are navigation state rather
than a single authoritative scientific active-phase pointer.

### Branch
A line of method development with phase stores and specialist thread
registrations. The selected method identity is stored in
`researcher/methods.json`. Selection can explicitly activate a proposed
identity through a researcher control record; it does not rewrite the P2
definition. A changed identity invalidates that selection. Retired P2 methods
remain blocked. Dedicated branch completion, retire/reactivate controls, and
automatic retirement-driven thread archiving remain original design goals.

### Team member configuration
Per member: `role`, `model`, `model_reasoning_effort`, `soul_sha256`
(content of the member's home `AGENTS.md`), skill pins
(`{name, sha256, origin}` per phase scope, DSH semantics), memory policy.
Stored in the member's `config.json`; changes are researcher acts and affect
subsequent turns without rewriting earlier briefs or outputs. The current
settings UI exposes model/provider, reasoning effort, instructions, and token
thresholds. Each actual turn, including corrections and rotation handoffs,
captures its submitted settings, instruction bytes and digest, and available
app-server acknowledgement in `runs/<run>/execution/<execution-id>/`.
Settings are captured when a turn obtains its member thread, so changes can
apply to subsequent turns in the same run. Earlier execution records remain
unchanged. Full skill-pin and memory-policy editing and capture remain
unimplemented; this is not a snapshot of every instruction the SDK discovers.

### Thread registration
Maps a logical thread key to its current physical thread ID and operational
metadata such as turn count and archive status. The orchestrator is the sole
writer; the Codex app-server executes the underlying conversation. The richer
timestamp/retirement registry in the initial plan is not a separate implemented
domain service.

### Run
One authorized execution of a phase's role stages against a pinned basis.
Fields: identity, phase, mode, branch_id, basis digests, thread keys used,
state (02-run-harness), attempt counters, findings history, timing, and
usage telemetry. The frozen basis includes exact records and available source
files, method identity, project question, catalog, and stage plan. A targeted
request also stores intent, target, and any selected assessment.

P4 question targets retain the exact inspected protocol generation and its
authored question/test/case/statement IDs. Current or committed historical
evaluations can be revisited. Their inspected records and tested theory are
saved separately from the new run's current scientific basis. The empirical
target is a harness control reference, not an additional scientific record
family or a new phase mode.

### Component assessment
A nonpublishing P3 run with intent `assessment` and terminal state `assessed`.
Its saved findings, evidence, options, and discussion refer to one exact theory
component generation. Follow-up discussion retains that version even after
theory changes. A separate repair request must use a valid current target.

### Situation brief
The exact markdown text sent to a member thread at a stage start,
assembled by the renderer per `SPEC-context-and-artifacts.md` §3 (fixed
sections, self-memory, binding upstream, addressed packets, instructed
opens, ambient mentions). Stored
per run, stage, and member. Briefs are
reconstructable by design (question verbatim + sealed upstream state +
boundary), and the stored copy is authoritative.

### Artifact types
Declared member outputs carry a type from `system_artifact_types.md`:
shared scientific record, T1 card (where declared, UI-only), T2p packet,
T2s summary (lead-authored), or T3m scientific material, including technical reports.
Titles and source
mentions provide navigation; T3w working files become retained evidence when
referenced. Phase-specific UI cards organize research questions rather than
requiring one artifact file per card. Delivery rules per consumer and type are in
`member-phase-matrix.md` and the pinned phase contract.

### Formal records and generations
Per phase, per branch, per record family (e.g. P3 `theory_record`, P4
`empirical_evidence_index`…): an immutable **generation** per publication,
with one atomic current-package pointer per phase identifying its complete
published set. Legacy family/current.json indexes remain readable. The P3
claim map projects the authoritative theory record rather than defining a
second independent scientific graph. Shapes are catalog-pinned.

### Publication receipt
One atomic publication's evidence: the generations written, their content
digests, the run id, the thread rollout digests, the catalog version pin,
and the authorizing run command. A prepared receipt becomes authoritative
only when its package is committed; the receipt alone is not publication.

## 3. Relationship model

```
project 1─* branch
project 1─4 member-config
project 1─* run
branch 1─* thread-registration
run *─* thread-registration        (which conversations produced it)
run 1─* situation-brief
run 1─0..1 receipt
branch 1─* generation              (per record family, per publication)
```

## 4. Dependencies

- P2 requires a published P1 basis (trunk).
- P2 publishes method definitions. Researcher selection activates a workspace
  for an existing definition; a new specification uses the P2 proposal mode.
- P3/P4 require published P1/P2 inputs and an active, aligned selected method.
  P3 revision requires current theory. P4 includes available theory but can
  start before P3, including a preliminary experiment with no theory record.
- Current P5 report assembly requires the exact published selected model and
  frozen problem context. Available P3/P4 packages and their explicit absence
  are frozen; missing support permits interim assembly. Complete status requires
  actual relevant numerical support and appropriate justification or qualification
  for the claims. Independent review requires the exact retained report.
  Readiness checks source availability and selected-method alignment; it does
  not certify scientific adequacy. Report work and its independent review stay
  within one method lineage. Historical manuscript runs keep their pinned requirements.
- Cross-branch reads are allowed only through published generations —
  never through another branch's thread context.

## 5. Change and downstream impact

- A new method version requires explicit reselection of its current identity.
  The existing branch retains its earlier generations; a version change does
  not automatically create a second branch or rewrite old work.
- Catalog version bump ⇒ runs pin the version they were authorized
  against; publication validates against the run's pinned version, never a
  moving target.
- Member configuration changes affect subsequent turns and do not rewrite
  previously stored briefs or outputs.
- A theory revision preserves earlier P4 results. The workbench flags changed
  theory or method bases and keeps earlier evaluations separately accessible.
  Applicability needs assessment; no automatic experiment rerun or pooling is
  implied. Numerical validation recomputes supported aggregates from recorded
  rows, not the original experimental program.
