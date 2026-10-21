# Design 00: System Principles

Normative principles for Model Forge (Codex edition). Accepted architecture
decisions are in [decisions/](../decisions/).

Current principles apply to the researcher workbench and its pinned catalog.
The [binding specification](../SPEC-context-and-artifacts.md) and
[UI contract](07-ui-contract.md) describe current delivery and interaction.

## 1. Scientific objective

The system helps a researcher develop a model or algorithm for their problem,
with supplied data or a clearly stated synthetic setting. Its end product is a
technical report with appropriate mathematical justification, numerical analysis,
limitations, and reproducible sources. Implementation fidelity and empirical
honesty matter throughout. Every published artifact must answer: which exact
content, produced by which member's which thread activity, authorized by
whom, validated against which catalog version.

## 2. Actor boundaries

- **The researcher** directs: creates projects, authorizes phase runs,
  authorizes corrections, makes model lifecycle decisions, provides problem
  context, and directs report development. Run requests and researcher control records retain these acts;
  a universal sealed-command ledger is not implemented.
- **Team members** (research_lead, theorist, data_analyst, outside_reviewer)
  are Codex threads with researcher-configured instructions and models.
  Each turn captures submitted settings and the available execution
  acknowledgement. Complete skill pinning remains a design goal. They propose
  and produce; they never publish, never mutate formal records, and never
  talk to each other except through orchestrator-mediated artifacts.
- **The orchestrator** (this service) is the only writer of formal state.
  Member output becomes formal only through validation + publication by the
  orchestrator.
- **The Codex harness** is an execution engine only. It owns turn mechanics,
  compaction, sandboxing, and thread persistence. It has no knowledge of
  phases, publications, or authority — and must never gain any.

## 3. Invariants

1. **No publication without validation.** Every published generation has
   passed the checks applicable to its pinned catalog (06-validation-strategy).
   A successful check establishes the stated structural and numerical checks,
   not the correctness of a proof or the adequacy of an experiment. Older
   generations are not silently certified under a newer catalog.
2. **One active run per (phase, branch).** Parallel branches may run
   concurrently; the same phase on the same branch cannot run twice at once.
   Shared lead turns are serialized even across otherwise independent runs.
3. **Pinned basis.** Every run records the exact basis digests it was
   authorized against. Method alignment is checked before launch and against
   the frozen inputs before publication. Corrections also require their
   original publication base to remain current; commitment checks it again.
4. **Immutability of the published record.** Published generations are
   never mutated; correction produces new generations.
5. **Thread honesty.** A run record names the exact Codex thread ids whose
   activity produced its outputs. Publication records a rollout digest when
   exactly one retained rollout is available, and explicitly records absence
   otherwise.
6. **Researcher supremacy.** Agents never authorize runs, corrections,
   lifecycle transitions, or publication. Gates are human.
7. **Fail loud, never fake.** A failed stage fails the run legibly. No
   silent retries that change scientific content, no fabricated results,
   no agent self-reports treated as verification.
8. **Branch isolation.** Specialists receive the selected branch's frozen
   records and trunk basis, not another branch's working conversation.
   The project-wide lead is the deliberate exception: it coordinates methods
   through mediated artifacts. Outputs and source links retain branch identity.
9. **Research may loop.** P3 and P4 can inform each other. Preliminary P4
   does not require theory to exist or be complete. Scope remains an explicit
   choice for each run; no phase or mode launches automatically.
10. **Assessment does not imply change.** Taking another look saves
    a separate assessment and discussion against an exact component version.
    It does not publish a replacement theory or alter formal scientific status.
    A researcher can then authorize a reviewed repair separately.

## 4. Communication principles (scientific)

- Situation briefs open with the research question verbatim, present the
  sealed upstream state, and close with the execution boundary.
- Claims in any published synthesis link to a supporting record or are
  recorded as limitations (the lead's in-house scientific check).
- Labels shown to the researcher are research-meaningful, never
  programmer-facing.
- P2-P5 use four reading purposes: what was found, its scientific detail,
  issues and researcher decisions, and further work. P1 separates setting and
  findings and combines further work with history in its five-card reader.
  Producing members
  write clear explanations in existing artifacts, with evidence, uncertainty
  and decision consequences. Exact science remains accessible; no separate
  display writer or extra summary artifacts are required.

## 5. Storage principles

- Mutable JSON indexes use temp-then-rename writes. New generation files
  are written once before they become visible in a committed phase package.
- The journal is append-only and links publication receipts. The atomic
  current-package pointer determines publication authority (design/03).
- Member homes and thread stores live under the project data root;
  nothing scientific lives only inside Codex state without a sealed
  reference.

## 6. Conflict rules

- Run commands carry idempotency keys; replay returns the original run.
  The workbench supplies an expected method identity when selecting a method.
  This does not imply every configuration or control endpoint has a universal
  command-replay mechanism.
- Run transitions and shared member turns are protected by locks within the
  service process. Multi-process distributed coordination is not implemented.
- If Codex thread state and orchestrator state disagree, the orchestrator
  record wins for formality. After restart, a committed publication or saved
  assessment recovers its completed state. Progressive P4 returns to a durable
  researcher checkpoint once owned-work cleanup is confirmed; other interrupted
  work fails visibly. No work is automatically rerun or resumed.

## 7. Non-goals (Version 1)

- No multi-tenant accounts; one host OpenAI account (ADR-001).
- No Codex Cloud execution; local threads only.
- No Codex `spawn_agent` team orchestration; orchestration is ours.
- No legacy import from Research Hub / Method Hub / the other editions'
  data roots.
- No live multi-user editing; researcher interaction is command-shaped.
