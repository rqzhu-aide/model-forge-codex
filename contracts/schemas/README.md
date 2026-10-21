# Machine-readable schemas

## Purpose

These JSON Schema Draft 2020-12 files define the persisted shapes of the
architecture. The prose specifications define scientific meaning. An
implementation must satisfy both.

A schema-valid object is structurally eligible for semantic validation. It is
not automatically scientifically correct, aligned, current, or publishable.

## Schema inventory

The inventory includes shared scientific records for catalog 1.5 P1/P2.
Historical schemas remain available for previously pinned runs. Catalog 1.7
requires P1 literature-findings and research-basis version 1.1.0 for new output,
while accepting the prior 1.0.0 shapes for historical reading. New collections
require reading_extent; the basis adds scientific_review, targeted
entry_corrections and exact frameworks, variants, relationships and algorithm
families. Correction targets bind original versions; support references bind
the effective final entries. Structural eligibility is not scientific certification.

| Schema | Object |
|---|---|
| `literature-findings.schema.json` | One member's source-linked P1 collection, with exact mathematics and directly displayed explanation |
| `research-basis.schema.json` | P1 setting, P2 preparation, mathematical framework landscape, scoped review and lead-authored entry corrections |
| `method-proposal.schema.json` | One P2 proposal with the original structured method, data requirements and proposed evaluation |
| `lead-proposal.schema.json` | One P2 lead method proposal or an explicit no-proposal response for general instructions |
| `proposal-audit.schema.json` | One specialist audit containing a separately identified assessment per target proposal |
| `catalog-assessment.schema.json` | The lead's proposal comparison and retain/exclude dispositions without copied method definitions |
| `common-definitions.schema.json` | Shared IDs, exact method identity, states, artifact pointers, alignment, attention, and outcome definitions |
| `digest-contract-registry.schema.json` | Exact payload, exclusion, digest-location, and hash construction registry |
| `digest-vectors.schema.json` | Cross-language accepted and fail-closed RFC 8785 vectors |
| `method-exposition-revision.schema.json` | Exposition-only method-identity regression vector |
| `traceability-registry.schema.json` | Exact links among invariants, research-workflow requirements, tests, scenarios, phase contracts, and milestones |
| `run-command.schema.json` | Authenticated user authorization for one run |
| `run-cancellation-command.schema.json` | Authenticated idempotent request to close one run's submission gate before immutable submission |
| `control-command.schema.json` | Strict union of non-run control commands |
| `method-lifecycle-command.schema.json` | User authorization to retire or reactivate one exact method |
| `delegation-grant.schema.json` | User-issued remote-operator authority bounded by project, action, target, and time |
| `delegation-revocation.schema.json` | Append-only revocation of one exact delegation grant and handle |
| `action-descriptor.schema.json` | Typed backend eligibility and command-construction data for one researcher action |
| `command-error.schema.json` | Stable researcher-facing command failure envelope shared by Web and remote clients |
| `compact-view.schema.json` | Layer-3 compact decision view: short decision-oriented markdown summary of a scientific record, referenced via stamped output:// representation pointers |
| `command-attempt-audit-event.schema.json` | Tamper-evident operational record of an accepted or rejected command attempt, exact raw request, authorization checks, outcome, and durable effect |
| `run-manifest.schema.json` | Immutable prepared run basis and sealed role-plan recipe, without future execution evidence |
| `prepared-role-context.schema.json` | Immutable pre-execution context materialized from the manifest recipe and declared broker capabilities |
| `role-invocation-start.schema.json` | Exact prepared context, executor, inputs, output contracts, capabilities, and copied manifest role plan at process start |
| `role-invocation-closure.schema.json` | Immutable terminal role outcome, final context ledger, accepted outputs, and handoffs |
| `run-submission.schema.json` | Complete ordered successful role-closure chain and exact candidate artifacts submitted for validation |
| `run-state.schema.json` | Run lifecycle projection and append-only lifecycle events |
| `role-profile.schema.json` | Versioned stance, instruction, output contract, memory, skills, knowledge, tools, and stage scope |
| `role-context-snapshot.schema.json` | Deterministic role context, capacity accounting, capability scope, and on-demand read ledger |
| `method.schema.json` | Immutable method generation with research-run or lifecycle-command lineage |
| `literature-source.schema.json` | Immutable cumulative literature identity and search provenance |
| `scientific-record.schema.json` | Immutable run-local candidate or formal scientific generation |
| `theory-record.schema.json` | Complete Phase 3 theory account with a readable primary artifact, explicit assumptions, statement-level support and status, dependencies, empirical implications, limitations, and revision provenance |
| `empirical-protocol.schema.json` | Prespecified Phase 4 protocol whose preliminary or comprehensive scope is independent of chronology and whose deviations are append-only |
| `manuscript-package.schema.json` | Complete Phase 5 manuscript package with a readable primary artifact and a P1 through P4 claim-support index |
| `statement.schema.json` | Immutable addressable scientific statement generation |
| `evidence.schema.json` | Immutable evidence item and creation-time exact-method applicability |
| `attention-item.schema.json` | Immutable version of a research question or defect requiring attention |
| `handoff.schema.json` | Immutable run-local communication between roles |
| `decision-record.schema.json` | Immutable lead synthesis for a user decision |
| `review-finding.schema.json` | Open evidence-grounded finding raised by a frozen Phase 5 parallel review, without a lead disposition |
| `review-report.schema.json` | Bounded outside-review report with prioritized open findings and an explicit novelty-search boundary |
| `review-issue.schema.json` | Immutable Phase 5 review issue and disposition generation |
| `publication-receipt.schema.json` | Atomic proof of one research-run or control-command transaction |
| `authority-event.schema.json` | Append-only change to derived publication, position, alignment, attention, or eligibility state |
| `record-state.schema.json` | Rebuildable current state for a record generation or evidence item |
| `current-index.schema.json` | Rebuildable mapping from each logical current slot to one formal generation |
| `phase-contract.schema.json` | Executable Phase 1 to Phase 5 behavior, prepared contexts, roles, validation, and publication |
| `validation-attempt.schema.json` | Immutable record of one validation pass with complete structured findings, policy version, and conformance decision |
| `output-transformation-record.schema.json` | Immutable record of one mechanical transformation with source and result digests and confirmation that no scientific artifact changed |
| `output-correction-command.schema.json` | Authenticated user authorization to correct a specified role output without repeating completed scientific work |
| `run-submission-attempt.schema.json` | Immutable submission-attempt record for correction re-entry, extending the base run-submission row without rewriting it |

## Immutable research objects and derived current state

Content generations preserve the scientific state at creation. Depending on the
object, this includes `authority_at_creation`, `alignment_at_creation`,
`research_attention_at_creation`, and `applicability_at_creation`. These fields
never change after the object is sealed.

Later publication, supersession, method change, attention,
invalidation, or evidence reclassification creates an append-only
`AuthorityEvent`. `RecordState` folds the ordered events into current publication
state, record position, alignment, research attention, and evidence eligibility.
`CurrentIndex` identifies current formal slots and cites the `source_event_ids`
that support each slot.

Deleting and rebuilding derived projections from the same event journal must
produce the same digests. A formal generation must remain byte-identical while
its derived current state changes.

## Independent state dimensions

Do not reintroduce one generic `status` field.

- Creation authority states how the immutable bytes were created.
- Derived publication state records whether the object is run-local, submitted,
  validated, formal, or invalid.
- Derived record position records current, historical, or none.
- Derived alignment records exact, compatible, unassessed, outdated, or not
  applicable.
- Research attention records unresolved work and severity.
- Scientific outcome records what the phase established.
- Evidence eligibility records whether a P4 item may enter the exact-method
  current evidence index.

These dimensions are independent. A generation may remain current in position,
be outdated in alignment after a method change, retain its earlier scientific
outcome, and carry new research attention through derived state.

## Method version and Phase 5 target rules

`method_identity.version` is a positive integer.

- Each calculation-defining change increments it by exactly one and changes the
  definition digest.
- A prose-only or bibliographic revision leaves the identity unchanged, but creates new artifact and whole-record digests when it is published as a new generation.
- Retirement or reactivation creates a lifecycle-only replacement generation. It
  preserves the exact method identity, definition, and scientific content while
  naming the predecessor generation and authorizing control command.
- Withdrawal is not a lifecycle transition and cannot be reversed through method
  reactivation.
- A changed mathematical-definition digest can never be compatible.
- A P3 replacement reassesses the complete theory for the new identity.
- Selected-method P4 results are recomputed for the new identity and receive new
  evidence IDs.
- Phase 5 assembly requires the exact current method, theory, and empirical
  basis.
- Phase 5 review-revision may freeze an older manuscript only within the same
  stable method lineage. This selects the document to revise and does not relax
  the exact-current basis required for the revised manuscript.

JSON Schema checks local shape. A semantic validator checks transitions and
cross-object identities.

## Run object separation

The run objects have different mutation rules.

- `RunCommand` is one user authorization for scientific work. It binds the exact phase contract and mode, then records phase-specific inputs in `choice_values` without duplicating them as generic scope or method fields.
- `RunCancellationCommand` closes the submission gate for one exact nonterminal
  run. It is not a formal-record control transaction.
- `MethodLifecycleCommand` and `FormalGenerationWithdrawalCommand` are user
  authorizations for formal state changes without a research run.
- `DelegationGrant` and `DelegationRevocation` define bounded remote-operator
  authority. Authorization is checked when a command is accepted and again
  before an irreversible commit.
- `ActionDescriptor` reports eligibility and constructs a typed command, but is
  never authorization itself. `CommandError` gives Web and remote clients the
  same stable failure representation.
- `CommandAttemptAuditEvent` records every accepted or rejected command attempt
  in a separate tamper-evident operational journal. It records exact request
  bytes, authorization checks, stable errors, and digest-bound durable effects
  without changing scientific authority.
- `RunManifest` is sealed after preparation.
- `PreparedRoleContext` and `RoleInvocationStart` record the realized context,
  executor, capabilities, and exact role basis immediately before execution.
- `RoleInvocationClosure` records one terminal role result and the exact outputs
  accepted by the harness.
- `RunSubmission` binds the complete ordered successful closure chain, final
  lead closure, and every candidate artifact sent to validation.
- `RunState` records lifecycle events and their current projection.
- `PublicationReceipt.source` distinguishes a research run, method lifecycle
  command. A research-run receipt binds the
  exact `RunSubmission` ID and digest. Every receipt identifies the committed
  event range, event-root digest, projection digests, and current-index
  generation, and carries its own verified content digest.

This separation supports reproducibility, optimistic concurrency, and crash
recovery. The original launch command authorizes preparation, execution,
validation, and publication when all declared checks pass. No second generic
approval state is inserted.

## Reproducible role execution

A role profile freezes exact `applicable_stage_ids` and immutable artifact
pointers for its stance, instruction, output contract, skills, tools, and
knowledge resources.

The run manifest freezes for each role step:

- `stage_id` and `execution_group_id`;
- serial or parallel execution;
- role and profile input;
- exact `input_ids` and `output_ids`;
- one unique `role_write_root` within the run root.

A phase contract may declare a harness-prepared immutable context. The Phase 5
`p5.review_packet` is one such object and becomes a frozen manifest input of kind
`prepared_context`. In a stage with `role_reads`, those role-specific read sets
replace a shared read set. The outside reviewer receives only
`p5.review_packet`; the theorist and data analyst receive their declared internal
sets.

Each role execution also seals a `RoleContextSnapshot`. It records deterministic
packing order, byte and token budgets, all included artifacts, capability-broker
scope, preference-memory identity, and every on-demand artifact read. An
overflow is explicit and cannot be hidden by silent truncation.

Immediately before execution, `PreparedRoleContext` fixes the materialized
context and `RoleInvocationStart` copies the matching manifest role-plan entry.
The start record also binds the trusted local Hermes executor profile, the
installed Hermes executable identity and version, and the project-state
snapshot. After execution, `RoleInvocationClosure` fixes the final
access-ledger head, terminal status, accepted outputs, and handoffs. Downstream
roles can read only successful upstream closures and their exact accepted
artifacts. `RunSubmission` is created only after the full selected role plan
closes successfully and the final lead closure supplies every required output.

## Downstream effects

Each executable phase effect represents alignment and research attention
separately:

- `alignment_effect` preserves or sets derived alignment;
- `attention_effect` records no item, an item if scientifically identified, or a
  required reassessment item;
- `automatic_run` is always `false`.

Preserving alignment does not prevent a phase from recording useful research
attention. No effect may launch another phase.

## Required semantic validators

JSON Schema cannot establish all cross-object invariants. The implementation
must also provide named validators for at least:

- registry-bound RFC 8785 serialization, numeric-domain rejection, and digest verification;
- complete machine-readable traceability from every invariant to requirements,
  tests, and acceptance scenarios;
- exact command-to-manifest binding and resource-policy no-broadening;
- cancellation, control-command, delegation, idempotency, authorization, and
  optimistic-concurrency checks at acceptance and irreversible commit;
- typed action-family isolation and stable command-error construction;
- operational-audit sequence and root continuity, exact raw-request byte binding,
  command, target, requester, and delegation agreement, complete `CommandError`
  embedding, and durable-effect ID and digest linkage;
- exact receipt-source discrimination for research runs and control commands;
- exact publication bindings from validated role outputs to formal targets, with
  deterministic publishers prohibited from creating scientific content;
- stable-ID uniqueness and reference resolution;
- immutable creation fields and rejection of mutable current-state fields in
  content generations;
- authority-event sequence continuity, root-digest chaining, and deterministic
  record-state reconstruction;
- agreement among record-state, current-index, event IDs, and publication
  receipt;
- exact canonical method-definition hashing, exposition-only identity preservation, and calculation-changing version advancement;
- prohibition on compatible alignment for a changed definition digest;
- run-state transition legality and agreement with the last lifecycle event;
- equality among manifest phase, mode, contract version, contract digest, run ID,
  and write root;
- exact stage order, execution groups, role-specific reads, frozen profiles,
  declared outputs, and unique role write roots;
- stage-compatible profiles and immutable output-contract, skill, tool, and
  knowledge-resource digests;
- prepared-context sources, mode scope, and immutable materialization;
- exact manifest-role-plan copying into invocation starts and supported executor
  binding verification;
- prepared-context continuity through invocation start and final context snapshot;
- invocation-start to terminal-closure continuity, accepted output and handoff
  verification, and exact successful upstream closure binding;
- complete ordered submission closure coverage, final lead closure, required
  candidate artifacts, RunState submission binding, and pre-submission
  cancellation exclusion;
- deterministic context packing, declared capacity, capability-broker isolation,
  closed reviewer metadata, and complete on-demand read accounting;
- selected-history agreement with the user command;
- expected target generation and optimistic-concurrency checks;
- one current generation per logical slot;
- evidence-ID immutability and exact-method eligibility;
- compact summary agreement with structured statements and evidence;
- Phase 5 exact-basis readiness, same-stable-method manuscript targeting, and
  outside-reviewer isolation;
- separate downstream alignment and attention effects with no automatic run;
- atomic publication, receipt reconstruction, and recovery by event replay.

Each validator returns a stable code, object location, violated contract rule,
and smallest correction. It must not claim to prove scientific truth.

## Examples

The sibling `../examples/` directory contains 62 valid examples covering every
persisted object schema except `common-definitions`, `phase-contract`, and the
two registry schemas. The five split phase contracts instantiate
`phase-contract`; `contracts/digest-contracts.json` and
`contracts/traceability.json` instantiate the registry schemas.

Sixteen targeted invalid fixtures test explicit user control, cancellation,
typed action-family isolation, malformed digests, current-only history isolation,
lifecycle preconditions, prior-state binding, event-family
isolation, the immutable-generation boundary, and exclusion of older-method
evidence from exact current state.

Run `python architecture/tools/validate_package.py` from the repository root to
check the complete package.

## Schema evolution

- Every object declares `schema_version`.
- Representation migration and scientific revision are separate operations.
- A representation-only migration cannot change a method definition digest or
  scientific outcome.
- A schema change that alters persisted meaning requires an architecture
  decision, updated examples, updated scenarios, and a migration rule.
- Unknown scientific semantics are rejected rather than guessed from prose.


## P4 workflow templates in catalog 1.25

The two protocol schemas agree on implementation route, source definitions and
case source/replication fields. Source amendments are prospective. The exact
artifact-pointer schema is unchanged: retained-file metadata is its sibling in
`{kind, artifact}`, never an extra pointer property. The implementation record
adds portable reproduction files, dependencies/invocation/runtime identity and
explicit availability. Analyst actual-data disposition is final, not a mutation
of the original protocol. Lead headline IDs select same-evaluation exhibits.
These requirements belong to the newly adopted P4 contract; historical frozen
catalogs remain valid under their producing schemas.

Catalog 1.25.1 requires the Lead's concise `method_formulation_markdown` and
adds optional exact `coverage.exhibit_ids`. The existing coverage rows compose
five canonical experiment topics, plus actual data when supplied, with explicit
unassessed or inapplicable reasons. Summary and code accounts contain no
quantitative tables/figures; `headline_exhibit_ids` orders those exhibits within
Experiments and Results. Historical schemas, records and topic labels retain
their original meaning.
