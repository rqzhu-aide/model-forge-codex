# Coherent example record set

The valid example inventory is listed in catalog-index.json. Its central connected record set
describes one fictional statistical method and one user-launched Phase 4
preliminary run. Focused examples cover deterministic digests, method identity,
role context, cancellation, action descriptions, remote delegation, control
commands, and one independent two-event replay vector. They test system
representation and behavior, not the truth of the fictional scientific claim.

The paired literature-findings and research-basis examples use P1 schema 1.1.0.
They demonstrate exact framework fields, an original-entry digest, a targeted
lead correction and scoped review without claiming new source verification.
The matching *-legacy examples preserve the prior 1.0.0 shapes. P1 negative
examples under invalid/ reject missing reading extent/review/math, stale-shaped
correction targets, identity mutation, empty changes and unsupported certification
statuses; semantic tests separately verify reference resolution and actual digests.

Five files - `theory-record.example.json`, `empirical-protocol.example.json`,
`manuscript-package.example.json`, `review-finding.example.json`, and
`review-report.example.json` - are standalone record examples for the Phase 3,
Phase 4, and Phase 5 record schemas. They describe their own fictional method in
their own identity namespace and are not part of the connected Phase 4
transaction below.

## Phase 4 research transaction

Read the main transaction in this order:

1. `run-command.example.json` records the user's exact authorization.
2. `run-manifest.example.json` binds that command to the split Phase 4 contract,
   frozen inputs, one profile artifact per role, unique role write roots, expected
   outputs, and six exact publication bindings. It remains a recipe and does not
   claim later role context, output, or completion.
3. `role-profile.example.json` gives the fully instantiated data-analyst profile.
   The other role profiles are frozen manifest artifacts, but their internal
   profile content is not claimed to be validated by this example set.
4. `prepared-role-context.example.json`, `role-invocation-start.example.json`,
   `role-context-snapshot.example.json`,
   `role-invocation-closure.example.json`,
   `role-invocation-downstream-start.example.json`, and
   `run-submission.example.json` show the realized execution lifecycle from one
   prepared role through accepted downstream use and complete submission.
5. `handoff.example.json`, `statement.example.json`, `scientific-record.example.json`,
   `evidence.example.json`, `attention-item.example.json`, and
   `decision-record.example.json` show the communication, scientific content,
   formal attention, and lead decision produced around the run.
6. The six `authority-event*.example.json` files are the complete committed event
   range. They publish four current record generations, index one evidence item,
   and publish one immutable attention-item version.
7. The five Phase 4 `record-state*.example.json` files replay every changed record or
   evidence item at the final event root. `current-index.example.json` selects
   the four current formal records.
8. `publication-receipt.example.json` binds the exact submission and accounts for
   every committed event, formal record change, cumulative evidence or attention
   object, projection digest, and replacement current index.
9. `run-state.example.json` records the separate controlled-run lifecycle from
   creation through immutable submission and atomic publication.

The command, manifest, prepared-context, invocation, closure, submission,
authority-event, run-state, immutable-object, projection, current-index,
publication-receipt, and operational-audit hashes are calculated from their
registered contracts. Hashes inside illustrative artifact pointers represent
external content and are not repository-file hashes; raw request pointers hash
the exact referenced bytes.

## Digest and method-identity vectors

`digest-vectors.example.json` fixes the RFC 8785 bytes and SHA-256 values for
Unicode property ordering, string escaping, and safe integers. Its rejected
vectors prove that the bundled Python reference fails closed for unsupported
binary64 values and integers outside the interoperable safe range.

`method-exposition-revision.example.json` applies one declared editorial patch to
`method.example.json`. Validation reconstructs the successor method generation
and proves that the canonical mathematical payload, method version, and
`definition_sha256` remain unchanged while the artifact and whole-record digests
change.

## Role context and isolation

`prepared-role-context.example.json` freezes the realized pre-execution context.
`role-invocation-start.example.json` binds that context to the copied manifest
role plan, exact inputs and output contracts, capabilities, write root, and
trusted local Hermes executor. `role-context-snapshot.example.json` closes the complete
capacity and broker-access account. `role-invocation-closure.example.json` binds
the successful analyst outcome and accepted outputs; the downstream theorist
start consumes those exact accepted artifacts. `run-submission.example.json`
binds the complete ordered successful closure chain and all required candidate
artifacts without claiming deterministic model output.

## Independent multi-event replay

The replay vector uses two authority events for one newly published theory
generation. The first establishes formal current publication with alignment
unassessed. The second changes only alignment to exact and binds the
intermediate state digest. The final record state and current index must carry
forward publication, position, and attention from the first event while taking
alignment from the second. Its receipt categorizes publication and state-only
events separately and accounts for both exactly once.

## Supporting research objects

- `method.example.json` is a formal Phase 2 method generation with exact method
  identity and research-run lineage.
- `literature-source.example.json` shows cumulative Phase 1 source provenance.
- `review-issue.example.json` shows one run-local Phase 5 issue version before
  lead consolidation and formal publication.

The phase contracts define how every phase publishes lead-consolidated attention
items. Phase 5 separately publishes lead-consolidated review-issue versions and
builds a deterministic current ledger from the prior ledger plus those formal
versions.

## User actions, cancellation, and delegated control

The five `action-*.example.json` files cover the closed action families for
starting or cancelling a run, and retiring, reactivating, or activating a method,
a formal generation. An action descriptor reports current eligibility and the
exact command fields needed next. It is not authorization.

`run-cancellation-command.example.json` binds an idempotent cancellation request
to one exact run and expected run head. `run-state-cancellation-requested.example.json`
shows the resulting nonterminal state while the harness closes the submission
gate. Cancellation cannot begin after immutable submission.

- `method-lifecycle-command.example.json` retires one exact active method without
  changing its mathematics or starting a research run.
  generation without deleting its immutable bytes or restoring an older version.
- `delegation-grant.example.json` gives one remote operator bounded project,
  action, target, and time scope.
- `delegation-revocation.example.json` revokes that exact grant through its
  append-only revocation handle.
- `command-error.example.json` and
  `command-error-delegation-not-active.example.json` give Web and remote clients
  the same stable failure envelope for ordinary and delegated failures.

Lifecycle commands freeze the full current-index and event-journal
head. The receipt schema has separate source branches for a research run, method
lifecycle command.

## Operational command audit

The five `command-attempt-audit-*.example.json` records form one independent
project-scoped hash chain. They cover accepted run start, accepted method
lifecycle, accepted cancellation, and a malformed
unauthenticated request. The malformed record points to
`raw-command-request-malformed.txt` and hashes its exact bytes. Accepted events
bind the exact durable RunState event or publication receipt by stable ID and
digest; rejected events embed the complete stable `CommandError`.

## Rejected fixtures

The `invalid/` directory contains sixteen near-valid objects that must be
rejected:

- `action-descriptor-cross-family.invalid.json`;
- `authority-replay-existing-evidence-reset.invalid.json`;
- `authority-event-alignment-missing-prior-state.invalid.json`;
- `authority-event-cross-family.invalid.json`;
- `authority-event-evidence-reclassification-missing-prior-state.invalid.json`;
- `decision-auto-action.invalid.json`;
- `method-lifecycle-malformed-digest.invalid.json`;
- `method-lifecycle-no-op.invalid.json`;
- `publication-receipt-research-run-withdraw.invalid.json`;
- `record-state-old-method-included.invalid.json`;
- `run-cancellation-submitted.invalid.json`;
- `run-manifest-current-only-history.invalid.json`;
- `run-state-cancellation-after-submission.invalid.json`;
- `scientific-record-mutable-position.invalid.json`.

Passing package validation establishes representation, provenance, authority, and
workflow consistency. It does not establish scientific truth.


## Ordered P4 workflow and portable example

`implementation-record.example.json` is honestly unavailable. Its new
`reproduction` fields do not invent source files or execution. The separate
`implementation-record-portable.example.json` points to real retained bytes in
`p4-workflow-support/`: standalone model, separate generator/truth, ordinary
runner, configuration and README. The runner uses the same fit interface for
mapped supplied CSV data and omits unknown truth/error for that application.

`p4-result-exhibits.example.json` links a concrete analytic CSV and SVG. Both
are explicitly illustrative reference values, not observed performance.
Figures name their exact underlying table. The progressive and empirical
protocol examples declare synthetic/check source identities and independent
dataset versus deterministic-check replication. Their retained generator/truth
source is not a claim that a reference solver or experiment ran. Concrete
estimation, prediction, uncertainty, computation and tuning/robustness table
columns and figure choices appear in the P4 prose contract.

`p4-lead-synthesis.example.json` explicitly marks its mathematical recap
unavailable because the structural tapered-quantile fixture does not retain a
complete definition. It does not invent that definition. The separate
`p4-lead-synthesis-portable.example.json` recaps the retained illustrative
constant-mean model with defined notation and its fitting criterion, and routes
the existing analytic reference exhibits to Performance. Neither example claims
observed performance. Both use explicit canonical topic accounts; the portable
example shows that no tuning parameter means not applicable and an unperformed
robustness study means unassessed.
