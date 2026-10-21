# Design 06: Validation Strategy

Status: validation boundaries originally reconciled with catalog 1.14.0;
the report-family size and scope description reflects catalog 1.23.0 on 2026-10-13.
Validation checks
record integrity and declared consistency; it does not certify scientific
truth. The [binding specification](../SPEC-context-and-artifacts.md) states
the publication and assessment boundaries.

## 1. Catalog pin

Every project pins a universal-catalog version (`catalog-pin.json`,
ADR-007). A run validates against the version pinned when it was
authorized — never a moving target. Catalog sync is a deliberate
researcher act.

New runs capture the actual catalog bytes, stage plan, exact scientific
basis, and available referenced source files. The harness checks the catalog manifest
at authorization and validates against the captured copy. Explicit adoption
archives an older project catalog without rewriting scientific generations.
A historical run without captured contracts and inputs cannot be corrected
under a newly adopted catalog; it requires a new run. Earlier validation
is not silently recertified under a newer catalog.

## 2. Layers

1. **Output guidance and collection**: each member receives its output
   schemas in the brief and writes files. The harness collects only that
   member's declared outputs and seals the collected bytes. It does not
   assume that SDK chat output has already enforced the file schemas.
2. **Contract validation**: the pinned catalog covers every declared output with
   its object, each-item collection, or JSONL row schema. Missing files,
   invalid JSON, schema failures, and source digest failures are findings.
3. **Deterministic scientific consistency**: checks cover selected method
   identity; theory IDs, dependencies and graph agreement; preservation of
   unrelated mathematics during targeted repair; planned empirical cases
   and replicates; applicable numerical aggregates; and referenced source
   bytes. Diagnostics are recomputed from recorded rows using supported
   arithmetic. Member scripts are not executed by validation, custom
   estimates may remain unverified, and experiments are not replayed.
   P5 additionally resolves central claims, support/counterevidence IDs,
   source artifacts, and manifest record/generation/digest references against
   its verified frozen P1 through P4 inputs. A prior manuscript cannot serve
   as its own supporting evidence. These are reference checks, not a claim
   that cited evidence logically proves the manuscript's conclusions.
4. **Scientific review**: specialist audits and lead synthesis are explicit
   stages. Independent P5 review receives the frozen manuscript packet in
   an isolated context. A successful review or schema check alone cannot
   publish; the entire package must pass its blocking checks and commit.

Initial assessment uses its separate schema and frozen evidence references.
It ends as `assessed`, never `published`, and cannot change scientific files
or formal status. P4 readiness requires the registered selected method and
P1/P2 inputs, with P3 included only when present. Partial theory or a negative
empirical result is not inherently a validation failure.

### 2a. When the same checks run

- **During authoring:** every member has the read-only `validate_artifacts`
  tool. It checks that member's declared drafts and permitted frozen inputs,
  including sealed prior-stage outputs. It does not read independent peers'
  current drafts or broaden P2/P5 role-specific input access. Findings identify
  the affected output and location while the author can still fix the file in
  its existing turn.
- **Before the next stage:** the harness validates collected outputs from the
  completed stage together, including applicable references and consistency
  checks. Missing files, invalid shapes and broken available references cannot
  silently pass to downstream authors. Blocking mechanical findings use the
  bounded original-author repair described below.
- **Before publication:** full package validation remains required, followed
  by the existing atomic commit. Passing a draft or stage check is not
  publication authority.

These views use the same pinned validator rules with different available
inputs. Neither draft nor stage validation demands future outputs. Checks that
cannot yet run are identified as deferred, not successful. Draft validation
does not modify authored bytes or scientific state; collected candidates are
checked after the normal collection adjustments. Previously sealed research
and its catalog pin are not recertified or rewritten by these checks.

P1 authors remain responsible for source mathematics and reading evidence.
The lead checks targeted scientific claims, directly corrects
affected entries with source evidence, and synthesizes frameworks in its normal
reconciliation turn. These model judgments are distinct from mechanical checks;
the harness applies exact authored corrections and preserves original versions.
P2 retains proposal
cross-audits, P3/P4 retain their specialist audits and lead assessments, and P5
retains independent manuscript review. Earlier mechanical feedback adds no
scientific review stage and cannot establish that an equation or proof is true.

### 2b. Mathematical display validation

The same authoring and stage checks parse authored mathematical fields with the
UI's KaTeX renderer. Malformed commands, unmatched display delimiters and doubled
command escapes produce findings with the artifact family, exact JSON pointer
and equation offset. Authors fix these in their existing turn. Sealed prerequisite
records are excluded from this authoring check. Published npm releases include
the built mathematics validator and use the existing shared Node runtime.
Source development can use shared frontend dependencies when that bundle is
absent. Neither path installs a private language runtime or local dependencies.

Member instructions require display math for major objectives, constraints and
comparisons. The UI centers display equations and retains horizontal scrolling
for long expressions. Conservative presentation recovery handles recognizable
uniformly doubled commands in older records without changing their stored bytes.
These checks establish renderability, not mathematical correctness.

Researcher-facing fields must be present where their schemas require them, but
mechanical checks do not certify that the prose is useful or scientifically
adequate. Existing authors, specialist reviewers and the lead check directness,
support and qualifications within their permitted inputs. Keyword, equation-
presence and text-similarity heuristics are not publication criteria; see
[ADR-009](../decisions/ADR-009-p2-explanation-quality.md).

## 3. Findings

### 3a. Artifact-type size checks (SPEC §7)

- T1 cards and T2p/T2s packets carry hard caps (2 KB / 32 KB): overage is
  a blocking finding routed as a correction (schema limits and byte checks).
- T3m scientific material carries an advisory 128 KB: overage is a
  non-blocking finding (visible to the lead and the researcher).
- Current P5 technical reports have no venue or fixed page-length requirement.
  Completion checks concern actual claim support and relevant numerical evidence.
  Historical manuscripts retain their pinned size and scope rules.
- P5 numerical support recognizes finite measurements in named metric maps and
  measurement columns, including estimates, errors, intervals and elapsed time.
  Metadata such as seeds, planned counts, versions, budgets and timeouts does not
  establish a numerical result. Failed, unperformed, invalidated and zero-completion
  rows remain ineligible. Exact model, source and applicability checks still apply.
  Figure dependencies resolve within the exact cited evidence index; a missing or
  ambiguous dependency remains a finding. These checks establish traceability,
  not scientific validity or independent review.
- The renderer reports each brief's assembled variable-payload size in the
  run's events — observability only, never a refusal (D8).

Findings are machine-readable: `{code, message, object_id, json_pointer,
blocks_publication}`. They drive repair and correction turns verbatim;
stage findings and attempts remain visible in the run audit.

Only blocking findings prevent publication. A stage receives at most two
automatic mechanical repair rounds, directed to the original owners of the
affected outputs. Original briefs and output bytes are archived, unaffected
peer outputs stay unchanged, and repaired candidates are checked again before
downstream starts. Repeated read-only checks inside a turn do not spend a
repair round. Exhausting the bound with unresolved blockers fails the run.

Repair briefs carry only the affected output contracts and findings, with the
original frozen context available by reference. Saved attempt results separate
changed files, resolved findings, remaining findings and newly exposed findings.
Identical files, findings and permitted evidence end automatic repair early;
changed content with a persistent blocker does not count as an unchanged attempt
or establish scientific progress. Repeated in-turn checks use the same declared
files and permitted evidence when deciding whether another check was unchanged.
P4 completion refusals preserve the draft validator's exact findings, and their
repeat check includes the draft artifacts rather than only the request fields.

Unavailable validation remains distinct from failed artifact validation. It
supplies a setup-specific correction hint and no finding that the underlying
science should be rewritten. A transport-successful response can still report
unavailable validation or a refused control request.

The existing one explicit failed-run correction remains researcher-authorized
and carries the researcher note and exact findings. It does not reset or
bypass the stage repair cap. It repairs the earliest affected stage, preserves
unrelated declared output bytes, and reruns affected downstream stages with
fresh inputs. Exceptions and cancellation produce visible terminal states;
they do not authorize unlimited retries. Scientific repair is a separate new run.

## 4. Test discipline for this service

- Automated tests validate catalog schemas, examples, declared output
  coverage, scientific invariants, and manifest integrity. Project creation
  copies the bundled pin; explicit adoption and new run authorization
  verify the offered or pinned manifest. No separate startup
  `validate_catalog.py` invocation is currently guaranteed.
- Golden-example discipline: any new record family added to the catalog
  lands only with valid examples and negative fixtures upstream first.
- Run-harness behavior is covered by scenario tests using a fake Codex
  bridge (no live model calls in CI): stage ordering, correction bounds,
  scope refusal, cancellation, failure visibility, and restart recovery.
  Strict-contract tests also execute complete P1 through P5 publication,
  P4 before P3, historical assessment discussion, immutable manuscript
  review, and retained method definitions in cumulative catalog updates.

The immediate-validation tests additionally exercise draft-tool ownership and
input isolation, deferred future outputs, stage reference failures before
downstream starts, original-author repair, the two-round cap, preserved
siblings and archived attempts, fresh downstream inputs, and the separate
explicit-correction allowance. The
verification record (retained in the ignored local archive)
records executed checks and the boundary between mechanical testing and
live-model scientific behavior.

The recovery regressions use real validators and controllers with scripted
members. They cover precise request fields, correction within the same turn,
unchanged versus changed failures, checkpoint-only inactivity, persisted requests
with failed responses, retained interruption evidence and no duplicate dispatch.
Local stdio tests exercise the installed SDK's result delivery, interruption,
usage collection and forwarding of unrelated tools without model inference.
These deterministic checks do not establish a completed live research exercise
or a general reduction in model cost.

## 5. Known failure classes (from the Hermes edition's production log)

- Schema-semantics misuse (e.g. heterogeneous values in a typed field):
  mitigated by exact contract guidance and focused correction briefs that retain
  access to the permitted frozen context.
- Provider stalls and rate limits remain operational failure modes.
  Activity and failures are visible; there is no guaranteed automatic
  reset-time resume (05 §4).
- Ordinary corrections can retain thread continuity, but a thread may be
  unavailable after restart. Frozen inputs and exact findings make context
  explicit; persistent threads do not guarantee scientific correctness.
