# System Artifact Types (canonical)

The harness's artifact vocabulary, reconciled with catalog 1.16.0 on 2026-10-11.
The pinned phase contracts declare actual required outputs and audiences.
Sizes are hard caps enforced at validation unless marked soft. Current delivery and
authority rules are in the [binding specification](SPEC-context-and-artifacts.md)
and [member-phase matrix](member-phase-matrix.md). A presentation type alone
grants neither scientific authority nor method activation.

The revised P5 end product is `technical_report`, with an authored Markdown
artifact, exact mathematical and numerical sources, completion requirements,
and its own immutable generation. `t3m_report` has an advisory source size rather
than a hard paper length quota. Historical `manuscript` records keep their own
family. Versioned problem context, researcher answers, and continuation records
retain origin, scope, explicit amendments, and exact response references; they
do not certify a scientific assumption or launch work when saved.

P1/P2 use shared scientific `record` outputs. Each literature
collection, research basis, proposal, audit and catalog assessment is authored
once and read directly by both the UI and relevant scientific consumers.
These records do not inherit the T1 size or audience restrictions, nor require
T1/T2p/T2s companion summaries. Exact mathematics remains in the authored
record. The [binding P1/P2 amendment](SPEC-context-and-artifacts.md#0a-direct-scientific-records-for-p1p2-2026-09-10-binding)
supersedes older P1/P2 examples; all phases use their pinned declared types.
Deterministic compatibility projections create no scientific
prose and grant no new authority.

Catalog 1.30.0 adds `notation_updates` to the five existing Lead account shapes,
gated by `project_notation_v1` and its required `research_presentation_v2`.
Notation is supporting scientific data, not another presentation tier, output
family or member stage. The harness freezes admitted `inputs/notation.json` and
`notation.md`, then generates and seals each Lead account's complete final pair.
The published account's `notation_snapshot` owns their exact paths and digests.
Its inherited entries retain original definition sources and scoped meanings.

The Markdown file is a generated reading view, not a mutable second authority.
There is no global latest registry. P1's historical component array and P4's
historical notation field remain readable but are not independently authored in
new-capability accounts. Source-bound correction requests use the existing
researcher-context store; dispositions remain in the Lead account that recorded
them. See [shared notation](shared-notation-plan.md) for scope and admission.

Additional P2 instructions or ideas have the Research Lead as their sole
recipient. Shared scientific fields remain directly reusable;
this does not grant every member access to raw researcher notes or method
origin. In the current contract, the lead, theorist and analyst each author one
independent method proposal. The earlier optional-lead/no-proposal behavior
belongs only to historical pinned workflows.

Catalog 1.6 attention items distinguish researcher decisions from team tasks.
Version 1.1.0 requires the target phase and context_markdown written by the
original author, including exact relevant mathematics, definitions, sources,
alternatives or assumptions, and what is needed. P1 setting decisions live
once in the research basis and display in P1's Issues and decisions card.
Team tasks display in the receiving phase and are inputs to its next user-started run.
Historical untyped 1.0.0 items stay readable without inferred classifications
or fabricated context. Explicit answers and team dispositions, not omission,
update cumulative attention state.

Catalog 1.7 P1 keeps the same four shared scientific records. The lead's basis
adds scoped review, exact framework synthesis and targeted content corrections
with original-entry digests. Applied corrections preserve original authorship
and history and record the lead as reviser. UI and later phases resolve the
same effective entry; the harness does not generate replacement scientific
prose. These fields create no additional artifact tier or member turn.

The four purpose cards are UI organization, not artifact types. Every phase
reads existing authored outputs into an overview, scientific evidence, issues
and decisions, and further work. Researcher-facing fields explain the question,
support, conditions, uncertainty and decision consequence. Exact definitions,
proofs, observations, code and source identities remain in their designated
scientific records. One artifact may support multiple cards through attributed
excerpts and exact source links, without a second writer or repeated full prose.

| Type | Size | Author | Audience | Rendered / injected | Purpose |
|---|---|---|---|---|---|
| **Shared scientific record** | Schema-specific; no general display-driven cap | Original producing member | UI and declared scientific consumers | Direct field rendering; inline or exact frozen-record reads per contract | Literature, proposals, audits, decisions, implementation, evidence and traceability, according to the phase's declared outputs |
| **AGENTS.md** (soul) | ~200 B | researcher (default templates) | the member, every turn | auto-injected by Codex | identity and stance |
| **T0 title** | one line (≤ 120 B) | method proposer (P2); lead may revise at P2 reconciliation | UI + all members | displayed as the method's name; used in mentions | the method's display title |
| **T1 card** | ≤ 2 KB | any member | **user-facing UI** | readable when the pinned workflow declares it; never a requirement inferred from card layout | historical or explicitly declared short human-readable capsule |
| **T2p packet** | ≤ 32 KB | any member | named roles, self when suitable, and researcher readers where declared | brief delivery follows the contract; substantive fields can supply readable UI views | handoffs, audits, diagnostics, claim maps, notebook and rotation continuity, with exact references to detailed support |
| **T2s summary** | ≤ 32 KB | **research_lead only** | lead's own synthesis and researcher readers | lead's later briefs; overview or detail according to phase | lead's evaluation of the phase result, support, uncertainty and next work; no universal score requirement |
| **T3m manuscript material** | 128 KB advisory per source; no hard P5 assembly byte cap | theorist, analyst, lead | P5 assembly; stage auditors | mention with an instruction to open the exact file when needed | structured paper-facing content. Ownership split: theorist = theory & proofs; analyst = numerical experiments & data analysis; lead = introduction, method framing, discussion, and other sections not owned by the others |
| **T3w working files** | unrestricted | any member | anyone, by path only | never mentioned systematically; internal name only | code, experiments, scratch, data — the member's free workflow |
| **T0 mention** (system-side) | ≤ 250 B | **the harness** (renderer), never a member | briefs + UI | the pointer mechanism | title + path + digest + size, referencing any T2/T3 artifact. (This replaces the earlier "digest-line pointer" idea — it is not an authored artifact, it is how the system *refers* to one.) |

## Rules

1. A member never authors T0 mentions; the renderer mints them when a T2/T3
   artifact is sealed. This is the system's addressing layer, not authored content.
2. T1 is human-facing; T2p addresses declared teammates and may also supply a
   researcher reader; T2s is the lead's synthesis. The declared audience controls
   member delivery, not whether scientific content can have a readable UI view.
3. T3m is referenced, never stuffed: briefs carry a mention + (when the
   stage audits it) an explicit instruction to open the file.
4. T3w has no generic content schema or size cap. Members work within
   their own writable workspace. Referenced proofs, implementations,
   manuscripts, data, and figures become retained source evidence with
   exact digests; later runs read frozen copies, not mutable workspace paths.
5. Companion packets follow the phase contract. A manuscript or evidence
   reader does not require an extra T1 artifact. The producing member writes
   clear explanatory fields in the existing output, preserving exact content.

## Scientific and researcher control records

Scientific record families are declared by the pinned phase catalog. New
publication makes one coherent phase package current atomically; neither
a display card nor an uncommitted receipt is a substitute for that package.
Artifact types describe how content is carried, not whether a conclusion
has been proved or a method has been activated.

An assessment is a separate schema-bound result in
`runs/<run_id>/assessment.json`: reasoning, limitations, evidence references,
suggested actions, and researcher discussion linked to an exact theory
component. Terminal state `assessed` grants no scientific publication or
mutation authority. It is not the lead's T2s verdict or an automatic repair.

Method selection and explicit proposal activation live in the harness's
researcher control store, `researcher/methods.json`, keyed to the published
P2 definition's exact identity. This record authorizes work on that identity
without rewriting its authored scientific definition. An informal title,
score, card, discussion message, or branch directory cannot supply it.
