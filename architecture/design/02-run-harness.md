# Design 02 — Run Harness

How a phase run executes: states, stages, thread driving, correction,
cancellation, recovery.

Status: current run lifecycle, including progressive P4 in catalog 1.14.0.
Immediate artifact validation and bounded original-author repair are retained. The
verification record (retained in the ignored local archive)
describes the checks and their limits. The
[validation strategy](06-validation-strategy.md) distinguishes schema
guidance from enforced server checks; the
[storage contract](03-storage-and-authority.md) defines publication authority.

Catalog 1.26.0 adds `consequential_researcher_decisions_v1`. The Lead asks only
when a material research consequence also requires an unresolved researcher
preference or unavailable study fact. Scientific judgment, routine implementation
and failure reporting within the agreed goal belong to the team. Relevant choices
are summarized in the existing phase summary; empty attention output is valid.
New authored requests identify priority and choice versus study information, with
concise alternatives and advice where appropriate. Catalog-gated validation covers
owned attention outputs and nested P1/P2 attention; historical catalogs retain
their original requirements. The answer service resolves a selected option against
the exact published question and saves its text plus the user's note as one versioned
instruction. Edits enter future applicable frozen inputs, without modifying active
runs, published records or run state. Nonblocking unknowns do not manufacture pauses
or new questions. See the [decision interface](07-ui-contract.md).

Catalog 1.27.0's consequential-invitation revision separates scientific importance from a
blocking dependency. An unresolved preference or study fact can warrant a timely
invitation even while conditional work continues. The Lead explains the current
provisional scope and when input would change the next work; it does not defer
all meaningful steering until execution is impossible. Routine scientific work
stays with the team, empty attention remains valid, and P5 retains its editorial
boundary. The [implementation plan](../plans/consequential-invitations-2026-10-24.md)
connects this rule to the actual brief sources and live interaction checks.

## 1. Run states

```
requested → running → validating → published or assessed
               │          │
               │          └─ blocking findings → failed
               ▼
            cancelled

failed → researcher authorizes one correction → correcting → validating
```

- `requested`: command recorded, basis verified, run record persisted.
- `running`: role stages executing, including stage checks and bounded
  automatic mechanical repair before downstream work.
- `validating`: outputs validated against the run's pinned catalog version.
- `correcting`: researcher authorized the (single) correction attempt; the
  findings turn is being executed in the responsible member's thread.
- Terminal: `published`, `assessed`, `failed`, `cancelled`. `assessed` saves
  a separate assessment without publishing scientific records.

Catalog 1.12 adds capability-gated progressive Phase 4 execution. Its analyst
stage can contain several ordinary turns and managed, bounded experiments.
`stopping` means the host is confirming owned process and model-turn cleanup;
`awaiting_user` means no inference or experiment is running. Waiting is durable
and reserves the branch's P4 continuation without blocking other phases or an
ordinary service shutdown. It does not consume the correction attempt.

Each continuation atomically consumes the pending question and immutable answer
in the controller record, then schedules the interrupted member. Restart never
automatically repeats a batch. A consumed answer whose scheduling was interrupted
becomes a new visible checkpoint. Finishing with available evidence prohibits
further experiments and still passes through the remaining audit, lead and
publication checks. Old frozen contracts retain their prior execution semantics.

The [member-phase matrix](../member-phase-matrix.md#p4-empirical_evaluation-method-branch)
describes current scientific scope and responsibilities; the
[UI contract](07-ui-contract.md) defines its four researcher-facing cards.

Transitions use a run lock within the service process and append an event.
Blocking stage findings allow at most two automatic mechanical repair rounds
within that stage. Remaining blockers, or blockers found at final validation,
fail the run. They do not authorize the separate researcher correction.
There is no `correction_exhausted` state: the explicit correction bound remains
one attempt; a failed explicit correction requires a new run.

## 2. Stage plan

Role stages come from the pinned phase contract
(`contracts/phases/P*.json`, whose role order is pinned by the catalog
validator). Examples: P4 = `[analyst] → [theorist audit] → [lead]`; P1 =
`[lead, theorist, analyst in parallel] → [lead synthesis]`.
In the current catalog, every P2 mode is `[lead, theorist, analyst proposals] →
[theorist and analyst cross-audits] → [lead comparison]`: exactly one method
per proposing member, two proposal targets per specialist audit, and no fourth
method from reconciliation. Additional P2 directions remain lead-only during
proposal writing; the specialists later receive the lead's scientific proposal.

- **Parallel stages**: one initial turn per listed member thread, driven
  concurrently. Any mechanical repair remains with the original author;
  it does not rerun unaffected siblings or reveal their independent drafts.
- **Serial stages**: turns in order; each brief embeds the sealed upstream
  state including prior stages' outputs.
- The stage's member is resolved through the thread registry:
  `(member, phase, branch) → codex_thread_id`, creating the thread on first
  use with the member's home, model, and soul in place.
- Stage plans and catalogs are frozen per run. The project-wide lead is
  shared and serialized; assessment and outside-review turns instead use
  fresh isolated contexts.

## 3. Turn driving

For each stage:
1. Materialize the member workspace and exact frozen input references. Member
   home instructions remain applicable; the engine does not create a separate
   workspace `AGENTS.md` for every run.
2. Assemble the situation brief per `SPEC-context-and-artifacts.md` §3
   (fixed sections → self-memory → binding upstream → addressed packets →
   instructed opens → ambient mentions; delivery classes per
   `member-phase-matrix.md`). Write it to
   `runs/<run_id>/briefs/<stage>.<member>.md` and record the assembled
   variable-payload size in the run's events (advisory reporting only —
   no caps, D8).
3. Start the turn with the brief as input. The brief describes each owned
   output and its schema; the member writes those files. The SDK call does
   not configure a model-side structured-output schema for those files.
   The member can call read-only `validate_artifacts` while writing to obtain
   immediate findings on its own drafts and permitted sealed inputs.
4. Stream thread events → run heartbeats (activity feed + usage telemetry).
5. On completion, collect only each member's declared outputs into
   `runs/<run_id>/outputs/<stage>/`, retaining source files and per-member
   seals. Apply collection metadata/path adjustments before validation;
   validate the collected bytes that publication will use.
6. Check every applicable schema, reference and deterministic consistency
   rule for the completed stage before starting downstream work. Return
   blocking mechanical findings to the responsible authors within the bound
   in section 5, then recollect and recheck their scoped outputs.

## 4. Validation

Output schemas guide the member, while the server enforces validation of
collected files (06-validation-strategy): schema shape and required outputs,
catalog-specific consistency checks, and referenced source bytes. Scientific
specialist reviews remain explicit stages. Findings include
`code`/`json_pointer`/`object_id` and whether they block publication; only
blocking findings prevent commitment. These checks do not certify proof
truth or replay the original experiment.

The in-turn tool checks only the caller's declared outputs and its permitted
frozen inputs, including sealed prior-stage outputs. It never exposes current
peer drafts. Closed-stage validation can check all submitted outputs together.
Neither view requires a later stage's unproduced files; deferred checks remain
explicit. Final validation still checks the complete package before publication.

## 5. Mechanical repair and explicit correction

Before advancing a stage, the harness may run up to **two automatic mechanical
repair rounds**. The original owner receives exact blocking findings and the
affected output IDs. This is a follow-up to its producing work, not another
scientific review stage. The harness archives original briefs and output bytes,
logs each round, and preserves unaffected peer outputs. Changed candidates are
recollected and validated; downstream work receives only the accepted result.
Read-only tool calls during an existing turn do not spend additional rounds.
Unresolved blockers after the bound fail the run. Provider failures and
cancellation do not become automatic mechanical retry loops.

The repair brief includes the affected draft files, their pinned output schemas
and exact findings. It references the archived original brief for the frozen
sources and reading restrictions, including when the member thread is recreated.
It does not renew the original whole-stage authoring assignment. Each repair
records changed files, resolved, remaining and new findings, and whether the
permitted evidence changed. A second repair receives that prior result. When
the first repair leaves files, findings and evidence unchanged, automatic repair
ends before a second paid turn. Changed bytes with a persistent blocker remain
a changed attempt, not a scientific success or an unchanged failure.

After failure, the researcher sees the findings and may authorize **one**
explicit correction. This separate allowance does not reset or bypass a
stage's automatic repair cap:

- The orchestrator posts the machine-readable findings, exact failing
  locations, and researcher note to the responsible member. Ordinary
  scientific work can reuse its available persistent thread; isolated work
  retains its explicit frozen context instead of inheriting team memory.
- The correction may touch only the outputs named in the correction scope;
  the orchestrator diffs corrected bytes against pre-correction bytes
  (blast-radius check). Out-of-scope changes fail the attempt.
- Pass → re-enters `validating`. Fail → `failed`; start a fresh run.
- Changed upstream outputs cause affected downstream stages to rerun within
  the authorized correction. A historical run without its captured catalog
  and inputs cannot be corrected under a newer project pin.
- Correction shares the normal phase/branch launch lock. Its original
  publication base and selected method must still be current before any
  correction turn starts and before publication. If newer research has been
  accepted, the preview explains that a new revision is needed. Historical
  runs without a captured publication base also require a new run.

Draft checks and failed repairs do not change sealed historical scientific
records or current publication pointers. Automatic mechanical repair preserves
the producing member's authorship and the existing P1-P5 review responsibilities;
it does not authorize new scientific claims or a second UI writer.

An assessment request on a published theory component is a separate read-only
operation. It returns findings and options tied to the selected generation;
it never replaces the current theory or starts a repair. A subsequent
researcher-authorized repair is a new `p3.theory_revision` run through the
theorist, analyst audit, and lead, not this failed-output correction lane.

## 6. Cancellation

Cancellation cancels and awaits the selected run's task. Its active bridge
turn sends the interrupt and waits for terminal confirmation while retaining
the shared thread lock. Completed stages' thread IDs are not interruption
targets. This also covers a run waiting for the lead and a rotation handoff.
Partial stage outputs are retained under the run dir, never published.
If stopping cannot be confirmed, the run reports failure and that physical
thread cannot accept further work until terminal confirmation is available.

For managed P4 computation, interrupted attempts retain their identity and
available output paths. If computation finished before output retention was
interrupted, completed-process metadata and already retained artifacts survive
with provisional status. They do not become completed scientific results. A
researcher pause records the active attempt reference so the reader can identify
the work actually interrupted.

## 7. Readiness gates

Readiness follows the selected mode's required inputs and exact active
method identity, not the presence of any file in the preceding phase.
P2 needs current P1 on trunk. P3 and P4 need the selected active P2 method
and current P1 basis. Preliminary P4 proof-of-concept experiments may run
before theory exists or is complete; available aligned theory is supplied
and its limitations remain explicit. The pinned P4 contract treats theory
as optional for both empirical scopes. P5 needs current P1 and exact-method
P2, P3 and P4 packages; partial or negative scientific outcomes alone do
not block it. Reruns also freeze their compatible same-phase account. P5
permits a prior manuscript from the same stable method lineage where its
contract allows that; its P3/P4 support must match the selected method's
exact definition — the same stable method and mathematical-definition digest.
An editorial revision that leaves the digest unchanged keeps earlier P3/P4
work aligned. Packages authored against a changed definition, or whose method
identity cannot be established, remain historical evidence and are excluded
from new current inputs, with exclusion reasons saved in the basis.
Gate failures identify the missing or mismatched research input without
starting an agent. P3/P4/P5 run on the selected method branch.

A focused P4 follow-up verifies the selected protocol's exact publication and
authored IDs. Its inspected historical context is retained separately from
the new current basis and delivered to the existing analyst, audit, and lead
stages. Editing the instruction does not change that target. Source bytes
and selector associations are checked at preparation, delivery, and before
publication. The researcher still chooses preliminary or comprehensive scope.

## 8. Stall detection and recovery

- A confirmed provider-capacity interruption in a single-member sequential
  P1, P2, P3 or P5 scientific stage can be retried explicitly in the same run.
  Completed stages and the original failure receipt remain saved; the retry
  does not consume a scientific-correction attempt. The interrupted member
  receives the saved brief, with unchanged inputs, instructions and model
  settings. A changed research context, later thread work or publication, or
  damaged retained source requires inspection or a new run. Parallel-stage
  recovery is not implied. Progressive P4 retains its separate checks for
  pending computation, saved direction and remaining experiment budget.
- Repeating a failing artifact check with unchanged declared files, explicit
  supporting files and permitted evidence returns a stop diagnostic. Repeated
  unchanged rejected P4 requests and checkpoint-only calls use the same turn
  stop mechanism. The diagnostic is included in the tool response before the
  bridge waits for delivery confirmation and interrupts. This applies only to
  harness-owned tools and does not introduce another repair budget.
- P4 continuation compares the saved plan's exact parsed content, pending and
  recorded attempts, completion and decision requests. Checkpoint history and
  formatting-only plan saves do not count as progress. An initial idle turn plus
  two feedback turns leads to a researcher decision; a progressing batch resets
  inactivity before the next turn. The existing outer limit of forty planning
  and experiment turns remains in place.
- An unknown P4 operation outcome requires inspection of saved control state
  before further dispatch. Later results in the same turn cannot clear that
  uncertainty or authorize another mutation. The inspection question retains
  the original feedback and pending attempt reference. A new control call after
  explicit continuation can update the current feedback. A definite rejection
  concerns only the current request; it does not erase earlier pending work.
  Saved feedback supplies the next brief and progress reader. Infrastructure
  failures do not ask the author to rewrite scientific content.
- Activity events and reported turn failures remain visible. The earlier
  proposed ten-minute silence probe is not an implemented watchdog.
- On service restart, a run whose package already committed, or whose
  assessment result was already saved, recovers its completed state. A waiting
  progressive P4 keeps its saved question. An interrupted progressive P4 confirms
  cleanup and returns to a researcher checkpoint; if cleanup cannot be confirmed,
  it fails visibly. Other unfinished runs fail with `interrupted_by_restart`.
  No interrupted turn or experiment is automatically repeated. A later
  researcher-authorized operation can resume an
  available persistent scientific thread under the normal run rules.

## 9. Concurrency

- Runs on different branches may proceed concurrently.
- One active run per (phase, branch); a second request refuses with a
  legible "already active" view.
- The lead's project thread serializes: lead stages queue across branches.

## Phase 4 implementation workflow (catalog 1.25.0)

The analyst first states the target and chooses package reuse, package adaptation
or custom implementation. It delivers a callable model, synthetic generator,
example runner and README, then checks correctness and portability through
managed execution. The same fitting interface is used for selected actual data.
The analyst reports accuracy, computation, tuning and sensitivity when relevant,
with denominators, failures, uncertainty and unavailable criteria explicit.
The theorist audits method correspondence and interpretation; the lead owns the
numerical summary, headline exhibit references and research decisions. The
existing eight analyst outputs and fifteen total outputs remain unchanged.

Each Python or R batch declares its entrypoint, helper/configuration files and
shared dependencies. The host freezes those source bytes at queue time and runs
a separate work copy, then retains declared result paths and logs with the same
attempt and budget identity. Later helper edits cannot change a queued batch.
No environment or package installation is performed by managed evaluation.

Selected local inputs are immutable project records, then copied into the run's
frozen input directory with filename, role, mapping, size and digest. Member
briefs receive metadata only. Managed computation reads selected files through
a host manifest; the raw dataset is not staged into member context or default
code downloads. Published tables contain authored aggregate results. Each case
identifies its data source and replication unit. A synthetic example does not
establish actual-data applicability or causal benefit.

Portable downloads contain only declared, digest-verified sources from that
publication or its exact retained inputs. Missing or changed bytes disable the
bundle with a visible reason. Historical runs remain readable under their
frozen contracts; local-data intake is enabled only for revised P4 workflows.

### P5 reader-report publication

The captured `p5.reader_report.v1` capability requires new report candidates to
declare `section_anchors.references` after seven distinct scientific headings.
References remains a boundary, with no eighth scientific section or discussion
target. Retained reading and export use the report's explicit metadata, independent
of the current project catalog. Reports without it keep their original section
extraction. The final reproduction discussion stops before a declared bibliography.

The versioned assembly and revision objectives deliver the connected report and
separate proof-appendix rules. The v2 review packet adds the corresponding shared
directions only under the review run's captured capability, preserving existing
packet bytes and older frozen Lead briefs. Each run freezes its own exact page,
layout and appendix instructions. P5 explains retained science; local exposition
expansions preserve the retained proof route, while substantive new results,
experiments and uncertainty calculations remain upstream work.
