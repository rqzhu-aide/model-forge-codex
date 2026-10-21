# Design 03 — Storage and Authority

Where state lives and how publication becomes authoritative. Deliberately
DSH-edition weight (ADR-003): journal + receipts + sealed rollout digests,
not a content-addressed hash-chain store.

Amended 2026-09-09 to match the phase-package implementation in
[`records.py`](../../src/model_forge_codex/records.py), the run engine, and
explicit catalog adoption. Earlier descriptions of journal replay and
independent current slots are historical design intent.

The [artifact and card map](../artifact-card-map.md)
describes the implemented library, proposal, review-issue, and attention
continuity. Accumulated indexes are rebuilt from the run's frozen accepted
inputs; complete theory, manuscript, and evaluation accounts remain coherent
versioned replacements.

## 1. Data root

`~/.model-forge-codex/` (configurable). All scientific and operational
state lives under it. Nothing authoritative lives only inside Codex state
without a sealed reference (principle 3.5).

Application releases are separate from this research directory. The npm
launcher verifies and retains release snapshots under
`~/.model-forge-codex-app/releases/`; the Windows installer uses its selected
installation root. Neither location is a project-local language environment.
See [npm release delivery](../npm-release.md) and
[Windows installation](../local-windows-install.md) for launch and update details.

## 2. Layout

```
~/.model-forge-codex/
  projects/<project_id>/
    project.json
    members/<role>/
      config.json                       # member configuration
      codex-home/                       # logical member home; runtime exception in ADR-005
        AGENTS.md                       # the member's soul (ADR-004)
        … codex state (threads, memory, auth reference) …
    branches/<branch_id>/
      threads.json                      # persistent specialist registrations
      phases/<phase>/                   # trunk p1/p2; method p3/p4/p5
        <family>/generations/<generation_id>.json
        <family>/generations/<generation_id>.jsonl
        <family>/current.json           # legacy pointer, read when no package exists
        packages/<package_id>.json      # immutable prepared package metadata
        current-package.json            # atomic publication authority
    researcher/
      methods.json                      # exact selected identities and activation
      method-selections.jsonl           # selection history
      attention_resolutions.json
    runs/<run_id>/
      run.json                          # state machine record + counters + telemetry
      events.jsonl                      # run event log
      basis.json                        # exact references and available source copies
      inputs/…
      contracts/…                       # frozen catalog for this run
      stage-plan.json
      briefs/<stage>.<role>.md
      outputs/<stage>/…                 # collected files used for validation
        working/<role>/…               # retained source files and working material
        seals/<role>.json
        seal.json
      assessment.json                   # assessment result only, never a publication
      previous-assessment.json          # explicitly selected discussion context
      review-packet/…                   # frozen manuscript and supplements
      isolated/outside_reviewer/…       # fresh review home
      rollout-digests.json              # sealed at publication
    authority/
      journal.jsonl                     # append-only publication events
      receipts/<receipt_id>.json
    contracts/
      catalog-pin.json                  # pinned universal catalog version
      … synced catalog copy …
    catalog-history/…                  # earlier catalog copies after explicit adoption
```

Generation files use `.json` or `.jsonl`; the latter holds replicate rows.
The layout is illustrative, not a promise that every optional file exists.
On native Windows, member and isolated-job homes retain separate SQLite
state under `state/`, while SDK rollout files live in the installed user's
shared CODEX_HOME. This [platform exception](../decisions/ADR-005-per-member-codex-homes.md)
does not change the location or authority of published scientific records.

## 3. Write discipline

- Mutable JSON records use a temporary file in the same directory and rename.
  New immutable generation files are created exclusively before commitment.
- `journal.jsonl` contains append-only JSON events linking receipt digests.
  It is not a JCS hash chain. JSONL readers can report skipped malformed lines.
- Run updates and shared member turns are locked within one service process;
  events are appended per run. A multi-process transaction coordinator is not
  part of the current system.

## 4. Publication

Publication is atomic for one run's phase package:
1. Collected owned outputs are validated under the frozen run catalog.
2. Immutable generation files and a package manifest are written. The receipt
   and a `publication_prepared` journal event identify this proposed package.
3. One atomic replacement of `current-package.json` makes the complete package
   current. Before that replacement the entire prior package remains current.

Authorization separately captures a token for the destination phase's current
package, including legacy family pointers. This token is independent of the
scientific inputs retained after method filtering. Publication requires that
token still to match, checking before preparation and immediately before the
current pointer replacement. An old failed correction therefore cannot
replace a newer accepted package, even when the method identity is unchanged.
This check complements process-local run locks; it is not a distributed
compare-and-swap operation across multiple service processes.

Prepared metadata may remain after failure. Receipt readers count a package
as committed only when reachable from the current package's ancestry.
Assessments save their result under the run without entering this path.

The receipt binds: generation digests, run id, thread ids, rollout
digests, catalog pin, authorizing command.

## 5. Authority model

- `current-package.json` and its committed ancestry determine publication
  authority. Canonical aliases and their supporting graph, diagnostics, and
  provenance records come from the same package.
- The journal and receipts explain production and authorization. Full current
  state reconstruction from the journal is not implemented.
- Researcher activation is an exact-identity control record. It does not
  replace an authored P2 scientific generation or change its definition.
- There is no cross-project authority in Version 1.
- A saved response mirrored into problem context retains its exact answer
  revision, scope and audience. Run bases freeze that routing metadata;
  specialist briefs project the account before applying amendments, so a
  Lead-only response cannot become shared through its context mirror. An
  explicitly accepted continuation amendment uses its existing exact
  authorized context reference. Original answers and frozen history remain
  intact.

## 6. Integrity requirements

- Generation and source digests are SHA-256 over exact bytes. The implementation
  does not claim every event uses the catalog's canonical digest machinery.
- Rollout digests are computed over the Codex thread rollout files at
  publication time when the exact rollout is available; otherwise the receipt
  explicitly marks it unavailable. Review rollouts use the isolated review
  home on non-Windows and the shared runtime home on native Windows; lookup
  must use the actual runtime location and exact thread identity.
- Exact source reads report missing or mismatched bytes. Research views may
  show other valid records alongside a visible source error. Legacy records
  without an exact association are not assigned invented provenance.
- New catalog text uses LF and portable relative-path sorting for its manifest
  and snapshot. Existing project pins are retained until explicit adoption;
  adoption preserves old science and run snapshots. This is separate from
  scientific publication and does not recertify historical results.

## 7. Retention

- The current implementation retains run directories, findings history,
  generations, and earlier packages. Automated retention policy is not exposed.
- Earlier P4 evaluations remain readable with their own scope and sources.
  They are not automatically merged with the current evaluation.
- Thread archives and a dedicated retirement workflow remain a separate
  unimplemented part of the original lifecycle design.

## 8. Artifact types (SPEC alignment)

Declared output types follow `system_artifact_types.md` and the pinned phase
contract: scientific records, packets, summaries and manuscript materials.
T1 applies only when declared, not to every visual card. T3w working files live
in member workspaces; referenced files are retained with exact source digests.
T0 mentions are renderer-minted addressing entries, never stored as authored
records. Size caps (T1 2 KB,
T2p/T2s 32 KB hard; T3m 128 KB advisory) are validated at collection per
SPEC §7.
