# Executable phase contracts

## Sources

Catalog 1.7 uses P1 contract 3.2 and P2 contract 3.2. P1 has three independently
authored literature collections and one research basis. P2 has one proposal
per specialist, an optional lead contribution, two cross-audit
reports and one catalog assessment. These shared scientific records are
rendered directly in the UI and reused by declared consumers. Legacy T1/T2
rules apply only to historical P1/P2 pins and unchanged later-phase outputs.

Additional P2 instructions or ideas are delivered only to the lead. The lead
develops an actual idea or records no_method_proposed for general guidance,
which it applies during reconciliation. Specialists retain their independence
and audit actual proposals only. Deterministic specialist views omit P1
phase2_preparation and raw researcher_origin while preserving scientific text.

P2 stage declarations are mode-specific: each selected mode has exactly three
stages even though the aggregate lists both supplied and unsupplied plans.
Publication bindings permit deterministic extraction of source and method
records and compatibility views from the original authors' records. The
publisher never writes a new mathematical definition or scientific summary.

P1 lead reconciliation includes scientific_review and targeted entry_corrections
inside its research basis. The lead authors scientific changes; the publisher
applies them to effective current entries with exact original digest, preserved
identity/authorship and immutable history. Framework references, the UI and P2
resolve those same versions. No scientific follow-up turn is introduced.
New P1 records use schema 1.1.0, while historical 1.0.0 shapes and frozen catalog
pins remain readable. A role_stages.role_objectives map adds only the named
role's scientific emphasis to the common objective; it grants no extra access.

The prose files under `../phases/` define scientific meaning. The five files
under `phases/` are the reviewable executable contracts for P1 through P5.
`phases.json` is the generated complete registry.

`digest-contracts.json` separately defines every registered digest construction,
JSON payload or referenced byte stream, exclusion, and location. It includes the
exact raw command-request bytes and is not generated from phase prose.

For the role lifecycle, the registry separately defines
`run_manifest.role_plan_entry`, `prepared_role_context.prepared`,
`prepared_role_context.content`, `role_invocation_start.content`,
`role_invocation_closure.content`, and `run_submission.content`. Implementations
must use the registered payload and exclusions rather than infer them from field
names.

`traceability.json` is the machine-readable coverage registry for all system
invariants and acceptance scenarios. It binds invariant and research-workflow
requirements to test groups, scenario documents, phase contracts, and roadmap
milestones. It is validated against
`../schemas/traceability-registry.schema.json`.

An implementation does not parse Markdown at runtime. It loads the selected JSON
contract, validates it against `../schemas/phase-contract.schema.json`, and
requires the command and run manifest to freeze the same contract version and digest.

Rebuild the aggregate with:

```text
python architecture/tools/build_contract_registry.py
```

## User-choice materialization

A command selects one `mode_id` and supplies one `choice_values` object keyed by
the exact choice IDs declared for that mode. Each choice declares a `value_kind`.
The harness requires every mode-required choice, permits only its declared
optional choices, and validates every value before preparation. The manifest
copies this map exactly. It does not reinterpret a generic scope or method field.

## Run materialization

The selected phase and mode resolve to one exact ordered stage plan. The run
manifest freezes for every role step:

- `stage_id` and `execution_group_id`;
- serial or parallel execution;
- role and versioned profile;
- exact `input_ids` and `output_ids`;
- one unique `role_write_root`.

`handoff_required: true` closes the stage gate: every invocation in that stage
must have a successful `RoleInvocationClosure`, and every declared output must be
accepted before the next stage or submission. It requires a `Handoff` object only
when the stage `writes` list names an output whose declared kind is `handoff`.

Each contract-selected manifest input carries the corresponding
`contract_binding_id`, and each expected output carries its
`contract_output_id`. `schema_application` states whether the declared schema
validates one object or every item in a collection.

Shared `reads` apply to every role in a stage. If `role_reads` is present, it
replaces shared reads and declares one exact set for every stage role. A role may
read only declared formal inputs, immutable contexts prepared by the harness, or
outputs fixed by an earlier stage.

`prepared_contexts` describes an immutable input constructed during preparation
from declared formal inputs and user choices. Its source identities, mode scope,
content requirements, and digest are frozen before role work begins.

The manifest remains a sealed recipe. Immediately before execution, the harness
creates the matching `PreparedRoleContext` and `RoleInvocationStart`. It seals a
`RoleInvocationClosure` at termination. A later stage may use only successful
upstream closures and their exact accepted outputs. `RunSubmission` is created
only after the complete ordered role plan closes successfully, the final lead
closure exists, and every required candidate artifact is present.

## Publication materialization

`publication_bindings` is the only executable source of formal publication
targets. Each mode-scoped binding names contract output IDs, an `append`,
`upsert_each`, `replace`, or `bundle` operation, its cumulative collection or
current slot, prior-target policy, and any named bundle components. A declared
publisher transform may build an index or package deterministically, but
`may_create_scientific_content` is always `false`.

The run manifest materializes these bindings as an exact `publication_plan`
with run-local output IDs, exact target IDs or keyed-slot templates, expected
prior generations, and explicit prior input mappings for deterministic reducers.
An optional prior input is recorded as a frozen input or an explicit absence.
An unbound, multiply bound, mode-inapplicable, or stale
formal operation blocks publication. The publisher never infers a target from a
filename, output kind, or prose label.

`canonical_record_types` identifies current record types. Separate
`cumulative_object_types` identifies immutable objects that append without
occupying a current slot. These include literature sources, evidence items,
stable attention-item versions, and Phase 5 review-issue versions where the
phase declares them.

## Phase 5 review boundary

Phase 5 assembly requires the current method, theory, and empirical records to
match the exact selected method identity.

Review-revision may freeze an older manuscript only when it belongs to the same
stable method lineage. It never accepts a manuscript from another method. The
harness constructs `p5.review_packet` from the selected manuscript, reviewer-
visible supporting material, and reviewer-facing instructions.

The parallel review stage uses distinct frozen reads:

- the theorist receives the review packet, current manuscript, exact method,
  current theory, implementation record, and literature synthesis;
- the data analyst receives the review packet, current manuscript, exact method,
  current theory, current empirical index, synthesis, implementation record,
  and literature synthesis;
- the outside reviewer receives only `p5.review_packet`.

The research lead receives all three fixed reports only in the later revision
stage.

## Downstream effects

Each effect declares two independent operations:

- `alignment_effect` preserves or sets derived alignment;
- `attention_effect` records no attention, attention if scientifically
  identified, or required reassessment attention.

Preserving alignment may still record research attention. Every effect sets
`automatic_run` to `false`. The user decides whether to run or rerun any phase.

## Change control

Package validation confirms that the aggregate and split contracts are exactly
identical. The prose and executable contracts change together.

A change to phase meaning, authority, prepared context, role visibility, method
alignment, publication, or user control requires an architecture decision and
corresponding schema, example, and scenario changes. Any disagreement is a
contract failure, not an invitation for runtime inference.
