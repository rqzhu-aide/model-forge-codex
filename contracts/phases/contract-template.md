# Phase N: Phase Name

This template is normative. A new phase contract must retain every section and resolve each bracketed item before implementation begins.

## 1. Purpose

State the scientific responsibility of the phase, the formal record it maintains, and the research decision it enables. Distinguish this responsibility from adjacent phases.

## 2. User choices

List every choice the user makes before launch:

- Run scope or mode
- Selected scientific object, if applicable
- Additional instructions
- Optional context
- Historical context, if deliberately selected

State explicitly which decisions remain with the user after completion. Availability must never imply automatic execution.

## 3. Prerequisites

List the formal current records and authority states required to prepare a run. Distinguish a structural prerequisite from a favorable scientific outcome. State which missing or outdated record blocks launch.

## 4. Frozen inputs

List every item copied or referenced in the immutable run basis. Include exact identities and digests where applicable. State that current formal records are selected by default and historical records require explicit user selection.

## 5. Role order

Define the role sequence, parallel groups, information visible to each role, and the handoff required between roles. State which role owns the primary scientific work, which role challenges it, and which role synthesizes the final record.

## 6. Run-local outputs

List required artifacts and structured records. All outputs must be written inside the active run workspace. Distinguish primary research artifacts, structured scientific records, role handoffs, and researcher-facing decision summaries.

## 7. Machine validation

Define checks that software can determine without scientific judgment:

- Schema and required-field checks
- Exact input and method identity checks
- File and reference integrity checks
- Scope and write-boundary checks
- Cross-record consistency checks
- Completeness conditions for promotion

Also state what validation cannot establish.

## 8. Scientific assessment boundary

Assign responsibility for assessing correctness, importance, assumptions, uncertainty, biological or substantive interpretation, and unresolved disagreement. Explain how partial, negative, contradictory, or inconclusive outcomes are represented without being treated as system failures.

## 9. Promotion rule

Define the atomic transition from validated run-local output to formal project records. State whether the phase appends, replaces, or performs both operations. State what happens to the previous current record and what happens if promotion fails.

## 10. Formal current record

List the exact objects downstream phases and the Web UI may treat as current. Keep primary artifacts, structured scientific records, and compact decision summaries distinct.

## 11. Invalidation effects

Define which upstream or sibling changes make the current record outdated, which changes only request research attention, and which changes have no effect. Define the downstream effects of a newly promoted record. No invalidation event may launch a rerun automatically.

## 12. UI projection

List the structured fields and user controls displayed in the phase tab. Separate:

- Authority and alignment
- Scientific outcome
- Research attention
- Available user actions

The UI must not infer these states from folder presence or arbitrary Markdown text.

## 13. Acceptance criteria

Write testable scenarios in Given, When, Then form. Cover at least:

- First successful run
- Rerun
- Optional historical context
- Invalid output
- Interrupted or failed promotion
- Relevant upstream change
- User control over all subsequent actions
