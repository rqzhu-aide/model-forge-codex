# Design 04 — Team, Souls, and Threads

The four members and how their identity, stance, and conversations are
provisioned on the Codex harness.

Status: current implementation, reconciled 2026-09-08. The
[binding specification](../SPEC-context-and-artifacts.md) governs context
delivery and the separate scientific and researcher control lanes.

## 1. The team

| Member | Scientific responsibility | Thread lifetime (ADR-002) |
|---|---|---|
| research_lead | Synthesis, contribution boundaries, decision options, in-house scientific check | One thread per project, spans phases and branches |
| theorist | Definitions, assumptions, proofs, validity | Per (phase, branch): trunk for P1/P2, per-method for P3 |
| data_analyst | Implementation fidelity, empirical design, reproducibility | Per (phase, branch): trunk for P1/P2 support, per-method for P4 |
| outside_reviewer | Independent manuscript review | Fresh isolated home and thread for each P5 review invocation |

The lead's shared project turns are serialized across branches. A component
assessment uses the theorist role in a fresh isolated context. Follow-up
discussion receives the original frozen assessment context and saved
messages; it does not reuse a scientific thread or publish a replacement.

## 2. Member home provisioning (ADR-005)

Each member gets `members/<role>/codex-home/` as its logical home, created by
the orchestrator with the contents below. It is also the runtime CODEX_HOME
except on native Windows, where [ADR-005](../decisions/ADR-005-per-member-codex-homes.md)
reuses the installed user's sandbox runtime and keeps separate member databases.

- `AGENTS.md`: the member's soul, editable through Team Settings. Its
  digest is stored in the current member configuration. Each actual turn
  retains the submitted instruction bytes and settings in its execution
  record, including corrections and handoffs. Complete skill and native
  instruction discovery capture remain unimplemented.
- `config.toml` — model, `model_reasoning_effort`, approval policy `never`
  for run turns and sandbox `workspace-write`. The SDK scopes a normal
  thread to that member's stable work root and sets each turn's stage cwd.
- Auth: Workspace's OpenAI Account panel can explicitly connect a shared
  host sign-in or a separate workbench device sign-in (ADR-001). The account
  service fills empty OpenAI member homes and preserves existing credentials.
  The saved connection also applies when future OpenAI members are provisioned;
  status reads never copy credentials. Separate member accounts are not required.
  Custom providers use a host environment key or a key in the shared provider
  settings file. Keys are never copied into member settings or research artifacts.
- Skills: `skill_pins` metadata can be stored in member configuration.
  Materializing pinned bodies, capturing every pin per run, and refusing
  drift remain intended capabilities, not current execution guarantees.

Assessment and outside-review homes copy the applicable configuration,
soul, and available auth, but no prior threads, notebooks, or native memory.
Their writable work root is isolated from scientific source files.
On Windows, these fresh logical homes and thread identities share runtime
rollout storage and researcher-wide global guidance. They do not provide
complete physical storage isolation from other runtime files.

An optional `data_root/providers.toml` is authoritative for the provider,
model, and reasoning effort of the members it names, across projects.
`MF_CODEX_PROVIDER_CONFIG` can select another path. An optional `[provider]`
table supplies shared defaults; `[members.<role>]` tables override model and
effort (which requires the shared default) or declare a complete provider
connection. An explicit member provider does not inherit another provider's
key or endpoint. Members absent from the file keep stored per-project
settings; without the file, stored settings apply to every member. The API and
each new turn resolve the same file, including corrections, isolated work, and
handoffs. Member home files retain the project's manual settings for use when
the shared file is removed or does not govern a member; they are not the
effective provider authority for governed members.
When the file selects OpenAI, the next turn can fill empty member auth homes
from an already connected account. This reuses the saved explicit connection;
it does not sign in, replace credentials, or select a different account.

## 3. Instruction layering per turn

1. Codex base instructions (harness-owned, intact).
2. Member home `AGENTS.md` (the soul — Codex global scope).
3. Any applicable workspace instructions supplied to Codex. The harness
   does not currently create a separate project/run `AGENTS.md` on each run.
4. The situation brief as the turn input.

Start and resume also explicitly supply the current captured member soul as
`developer_instructions`, so a settings edit reaches the next turn without
replacing the Codex base instructions. On non-Windows, native discovery remains enabled;
the execution record distinguishes submitted instructions from the source
metadata acknowledged by the app-server.
Native Windows execution disables project AGENTS discovery and automatic
skill instruction inclusion. The shared user's global AGENTS guidance
remains in addition to the member soul; its selected source and digest are
recorded. This platform exception does not change the frozen situation brief.

`model_instructions_file` is the documented escape hatch only if personas
fail to hold (ADR-004).

## 4. Situation briefs

Ordinary stage briefs carry the research question and researcher note
verbatim, the frozen selected method and applicable scientific inputs,
output ownership and schemas, and the execution boundary. Current-phase
revision context and sibling P3/P4 evidence are included when available;
P4 does not require theory to exist. Brief text is retained per run.
Output seals and frozen basis digests do not imply a complete digest-sealed
record of every model-visible instruction or every file actually read.

Assessment uses its exact target and saved discussion. Independent outside
review receives only the frozen readable manuscript and declared supplements,
with review instructions and its output schema. Neither uses the ordinary
scientific notebook/handoff recipe.

## 5. Communication between members

Members never message each other. Cross-member context flows only through
orchestrator-mediated, collected artifacts in briefs and exact file references.
Publication requires validation; a downstream stage may examine a same-run
candidate before final publication validation. The lead receives applicable
frozen branch summaries during an authorized run. Publication does not launch
an automatic lead turn or inject a background summary into its conversation.

## 6. Memory

Two independent layers (SPEC §5; design record 13, D10):

- **Codex native memory**: ordinary member homes retain the behavior
  configured by Codex on non-Windows. Native Windows processes explicitly
  disable native memory generation and use because their runtime home is shared.
  Otherwise, the harness does not guarantee that native memory
  extraction is enabled or that the stored `memory_policy` field enforces it.
  Memory is advisory context, never authority: anything a member
  "remembers" that matters must appear in a published record to be
  citable.
- **The notebook** (ours): one T2p-self file per (member × branch) —
  the member's explicit per-method working memory. When the member produces
  it, the harness retains it for that member's later briefs. This is the layer that
  makes "next time it runs, it remembers what it did" true without
  paying for an unbounded thread. Rotation handoffs remain the
  thread-level continuity device (SPEC §5).

Isolated assessments and outside reviews inherit neither layer. Assessment
continuity is explicitly recorded in its separate discussion document.

## 7. Presence routing

The researcher explicitly selects the run mode; the UI uses available
records to guide the choice and the engine checks its prerequisites. It
does not automatically launch review when ledger issues appear, escalate
preliminary P4 to comprehensive, or turn assessment into repair. Method
selection/activation binds the published P2 identity in
`researcher/methods.json`, independently of member memory or recommendations.
