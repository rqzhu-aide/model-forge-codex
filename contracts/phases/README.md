# Phase Contracts

This directory defines the scientific and operational contract for each phase of the research pipeline. Catalog 1.7 retains direct P1/P2 records and contextual attention, and adds P1 lead scientific review, targeted entry correction and mathematical framework synthesis within the existing four deliverables. Historical runs follow their frozen catalog snapshots.

The phase contracts cover these topics so that researchers, programmers, and test authors can compare them directly:

1. Purpose
2. User choices
3. Prerequisites
4. Frozen inputs
5. Role order
6. Run-local outputs
7. Machine validation
8. Scientific assessment boundary
9. Promotion rule
10. Formal current record
11. Invalidation effects
12. UI projection
13. Acceptance criteria

## How to use these contracts

Each prose phase contract defines scientific meaning. The matching executable contract under `../contracts/` defines deterministic choices, inputs, role plans, outputs, validators, publication rules, and UI sources. Schemas define persisted shapes, and acceptance tests prove that the implementation follows both representations.

For any proposed implementation:

- Start from the user choices and prerequisites.
- Prepare an immutable run basis from the frozen inputs.
- Execute only the stated roles and role order.
- Permit each role to write only inside its unique role root, then let the harness materialize verified shared outputs.
- Apply machine validation before promotion.
- Promote only through the mode-scoped source-to-target bindings named in the executable contract.
- Derive the Web UI from the formal current records, not from folder existence or free-form prose.
- Test every acceptance criterion, including failure and recovery behavior.

## Rules shared by every phase

- Only the user starts a run or rerun.
- A phase becoming available never starts it automatically.
- Current formal records are loaded by default.
- Historical records are loaded only when the user selects them or a phase contract explicitly requires a fixed historical object.
- The system freezes all selected inputs before role work begins.
- Agents write only within the active run workspace.
- Validation and promotion are system operations, not agent privileges.
- A failed, interrupted, or rejected run cannot replace a valid current record.
- Promotion is atomic. Readers see either the previous complete record or the new complete record.
- Scientific status is separate from authority status. A current record can report a negative, partial, or inconclusive result.
- The lead summarizes evidence and options, but does not choose the next phase or method for the user.
- Stable attention items are formal cumulative objects; run-local notes do not become unresolved project state by folder presence.

## Contextual decisions and team tasks (catalog 1.6)

New attention outputs use schema_version 1.1.0 and require kind
(`researcher_decision` or `research_task`), target_phase (P1-P5), and nonblank
context_markdown. The original producing member writes the exact relevant
formulation, defines symbols and assumptions or alternatives, names sources,
and explains the specific choice or work needed. The existing question remains
short and may contain mathematics. No classifier, additional summary writer,
or presentation repair is introduced.

A researcher decision belongs beside the scientific setting or result it
concerns. P1 setting clarifications appear only in research_basis.attention_items,
not in a duplicate list of bare questions. A team task belongs in the phase
that should perform the work. Its existence does not request a researcher
answer or authorize an automatic run. Current open tasks are frozen inputs
to subsequent runs of the receiving phase, with method scope when applicable.

Omitting an item on a later run never resolves it. Preserve stable identities
and append explicit answers or reasoned team dispositions. An answer to the
P1 setting changes shared instructions; additional P2 directions and answers
to typed P2 researcher decisions remain lead-only during P2. Legacy 1.0.0
items remain readable with their exact sources in
"Earlier open questions"; the UI must not infer their kind or invent context.
Collection outputs and embedded P1/P2 items require the new contextual schema.

## Phase map

| Phase | Scientific responsibility | Update behavior | Primary user decision enabled |
|---|---|---|---|
| [Phase 1](phase-1.md) | Establish the requested mathematical setting and literature landscape | Three independent collections and one current research basis; cumulative source history | Whether to modify the setting and what to ask P2 to develop |
| [Phase 2](phase-2.md) | Independently propose and cross-audit concrete methods | Two specialist proposals, optional supplied-method lead proposal, two audits and one comparison | Which exact method to select for theoretical or empirical work |
| [Phase 3](phase-3.md) | Establish the current theoretical account for one method | Replace the complete current theory record | Whether the theoretical claims and limitations justify further work |
| [Phase 4](phase-4.md) | Build the empirical evidence base for one method | Cumulative immutable evidence with atomically replaced current evidence index, empirical synthesis, implementation record, and phase decision | What the evidence supports and what should be examined next |
| [Phase 5](phase-5.md) | Assemble or revise the current manuscript | Replace the complete current manuscript | Whether to revise, return upstream, defer, or prepare for submission |

## What these contracts do not define

These files do not define JSON field syntax, database technology, queue implementation, UI styling, or agent prompt wording. Those belong in the domain schemas, harness specification, UI contract, and role instruction packages. Phase contracts define the required scientific behavior that those components must implement together.
