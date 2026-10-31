# Model Forge architecture

Model Forge helps researchers develop statistical models, machine learning
models, and algorithms. A Research Lead, Theorist, Data Analyst, and Outside
Reviewer produce structured research that the application presents as concise
cards and a technical report. The researcher chooses which phase to run.

The current source tree prepares application **0.9.3** with workflow catalog **1.30.2**;
already published packages are unchanged. Application releases,
project workflow adoption, and scientific publications are separate versions.
An existing project keeps its catalog and historical results until an explicit
update or new run. Application updates do not rewrite past research.

## Reading guide

| Document | Purpose |
| --- | --- |
| [Implementation status](implementation-status.md) | Current behavior and verification limits |
| [Research artifacts and cards](artifact-card-map.md) | Member outputs and the fields displayed in each phase |
| [UI contract](design/07-ui-contract.md) | Card order, action placement, reading position, and accessibility |
| [Context and artifacts](SPEC-context-and-artifacts.md) | Ownership, context delivery, exact sources, and history |
| [Artifact types](system_artifact_types.md) | Scientific, presentation, and operational records |
| [Member and phase matrix](member-phase-matrix.md) | Production and independent review responsibilities |
| [Researcher question language](../contracts/phases/researcher-question-language.md) | Scientific interpretation, mathematical precision and reader context across phases |
| [Research presentation](research-presentation.md) | Five authoring references, numerical display ownership, notation and consequential inquiries |
| [Shared notation and all-phase presentation](shared-notation-plan.md) | Implemented source design, scoped account snapshots, compatibility and verification limits |
| [Visual design](../design-system/model-forge/MASTER.md) | Blue research, navy system controls, orange researcher interaction |

The detailed design covers [principles](design/00-system-principles.md),
[domain objects](design/01-domain-model.md), [run orchestration](design/02-run-harness.md),
[storage](design/03-storage-and-authority.md), [team instructions](design/04-team-souls-and-threads.md),
[Codex integration](design/05-codex-bridge.md), and [validation](design/06-validation-strategy.md).
[Architecture decisions](decisions/README.md) explain enduring implementation choices.

## Phase design

1. **Phase 1 - Define and Explore:** Research Setting, Main Findings, Decisions
   to Discuss, Explore Individual Papers, and Additional Runs and History.
2. **Phase 2 - Propose Methods:** Proposed Methods, Select a Method to Explore,
   Decisions to Discuss, and Additional Runs and History.
3. **Phase 3 - Theory:** a method's theoretical account, claims and assumptions,
   detailed arguments and reviews, consequential decisions, and further work.
4. **Phase 4 - Numerical Eval:** Summary, Implementation and Code, Experiments
   and Results, Decisions to Discuss, and Additional Runs and History.
5. **Phase 5 - Report:** the technical report itself, section-level discussion
   and editable comments, and Next revision.

The Lead decides routine methodological and implementation choices and records
them concisely. Researcher questions require a material consequence and a missing
study fact or preference. Multiple-choice questions explain the affected point,
practical consequences, and recommendation. Nothing is preselected, unknown facts
remain unknown, and each item has one editable effective instruction.

Member briefs put the reader's task and field-specific writing duties before
execution constraints. Summaries lead with the scientific answer and its decisive
conditions; equations are interpreted in the supplied study context. The UI
distinguishes open questions, saved answers, unknown responses and actual pauses.
Consequences remain visible when a question is opened, while source history and
classifications stay in details. These presentation rules preserve scientific
meaning, answer ownership and the inputs already used by started work.

The executable [catalog](../contracts/catalog-pin.json), phase contracts, and
schemas govern new member outputs. Design prose explains those contracts; it
does not override them. Private run evidence, account information, exploratory
plans, and local screenshots are excluded from the release repository snapshot.

## Development and release

- [Contributor guide](../CONTRIBUTING.md) and [development setup](../docs/development.md)
- [Package preparation](npm-release.md)
- [Optional Windows desktop installation](local-windows-install.md)

Scientific validity requires review beyond schema checks or successful publication.
See the implementation status for the distinction between automated verification,
browser checks, and live model behavior.
