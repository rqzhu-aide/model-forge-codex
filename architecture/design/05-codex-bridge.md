# Design 05 — Codex Bridge

The boundary between Model Forge and Codex execution. Members produce
candidates; only the harness's validated publication commit grants scientific
authority. Assessment results and researcher activation remain separate
control records. Status: implementation baseline reconciled 2026-09-10,
with the artifact-validation tool implemented 2026-09-12. The
verification record (retained in the ignored local archive)
covers the installed SDK transport and scripted member turns.

## 1. Client shape

- **Library**: official `openai-codex` Python SDK, `AsyncCodex` (ADR-006).
  The bridge owns production SDK interaction.
- **Executable**: SDK clients receive the shared Codex executable selected by
  the same resolver used for account checks and managed experiments. A shared
  installation's model support may differ from the CLI bundled with the SDK;
  the requested model still requires its own connection probe.
- **Process model**: clients are created lazily per member home and provider
  configuration. Changing provider uses a separate client without closing
  another run's active session. Members retain separate logical thread state;
  the native Windows runtime exception is described below. Automatic
  reconnection and application-level retry/backpressure scheduling are not
  implemented guarantees.
- **Isolated jobs**: assessments and outside reviews also use SDK turns,
  with fresh logical homes, databases, workspaces, and threads. On Windows,
  runtime rollout storage and researcher-wide global guidance are shared;
  this is not complete physical storage isolation.
  `codex exec --json --output-schema` remains
  an alternative capability, not the current job path.

## 2. Mapping

| Model Forge concept | Codex mechanism |
|---|---|
| thread_key `(member, phase, branch)` | app-server thread, id recorded at creation |
| stage execution | SDK `thread.turn(brief_text, cwd=stage_workspace)` |
| heartbeat | thread item/event stream → run activity feed |
| stage output | declared workspace files, collected by ownership; chat text is not a formal output |
| draft validation | read-only `validate_artifacts` dynamic tool bound to the current member and stage |
| cancellation | turn interrupt |
| mechanical repair | at most two original-author follow-up rounds per stage before downstream starts |
| explicit correction | one researcher-authorized failed-run correction, then renewed affected downstream stages |
| future authorized work after restart | persisted thread ID and member home supplied to SDK resume |
| usage telemetry | completed-turn usage; cumulative thread totals are converted to run-spend deltas |
| execution evidence | per-turn submitted settings/instructions and available acknowledgement, retained briefs, output seals, and available rollout digest |

## 3. Configuration applied for each turn

- Start and resume explicitly submit model, reasoning effort, provider
  definition, and captured member instructions. Turn start also explicitly
  supplies model, effort, workspace-write sandbox, and deny-all approval mode.
  Corrections and handoff turns follow this path. Thread settings alone did
  not preserve the write policy when changing the turn working directory in
  the first live P1 trial.
- A narrow typed adapter retains the app-server start/resume response, which
  the SDK convenience method otherwise discards. Execution records distinguish
  submitted configuration from acknowledged model/provider/effort; simulated
  tests identify their acknowledgement as simulated. The adapter depends on
  installed SDK internals and needs checking when that package changes.
- Captured member `AGENTS.md` is supplied as `developer_instructions` without
  replacing Codex base instructions. Non-Windows native instruction discovery
  remains enabled. Its available source metadata is recorded, but the harness does
  not claim to seal all SDK-discovered instructions or skills.
- `sandbox=workspace-write`, with the member's stable work root as thread
  cwd and each stage workspace as turn cwd. Isolated jobs use their own
  private work root. Resume reapplies sandbox, cwd, and approval settings.
- Executable scratch paths use `data_root/work/<home-digest>/<run-digest>/<stage>`.
  The home and run components are 24 hexadecimal characters. This avoids
  nesting the full project/run names into Windows process working directories.
  The same resolver supplies normal, isolated, correction, and diagnostic
  workspaces. Handoffs run in a short stage subdirectory and are copied into
  their existing archived location. Authentication homes, formal outputs,
  and historical records retain their existing paths; execution receipts
  retain the actual workspace and work root.
- SDK `approval_mode=deny_all`; the generated TOML uses
  `approval_policy=never`. A denied operation fails rather than prompting
  for an interactive approval inside the member turn.
- On non-Windows systems, CODEX_HOME is the ordinary member home or fresh
  isolated job home. Native Windows processes reuse the launch environment's
  CODEX_HOME, falling back to `~/.codex`, so they use the existing native
  sandbox setup without reprovisioning machine-wide sandbox identities.
  Each logical home supplies a separate `sqlite_home=<member-home>/state`.
  Thread registrations and scoped workspaces remain separate; rollouts live
  in the shared runtime home. No sandbox or approval policy is weakened.
- Before a shared Windows client starts model work, the bridge requires native
  sandbox readiness and checks matching member/runtime OpenAI account
  fingerprints for OpenAI turns. A missing setup or account mismatch fails
  visibly rather than launching a turn that cannot write its outputs.
- Shared Windows processes disable `features.memories`, memory generation
  and use, project AGENTS discovery (`project_doc_max_bytes=0`), and automatic
  skill instruction inclusion. The user's global `AGENTS.override.md` or
  `AGENTS.md` remains researcher-wide guidance. Execution metadata records
  its selected path and digest, logical and runtime homes, and the shared
  rollout/separate database arrangement. See [ADR-005](../decisions/ADR-005-per-member-codex-homes.md).
- Output schemas are included in the brief; the current SDK call does not
  enforce a structured final chat response as the scientific artifact.
- The optional shared `providers.toml` governs the members it names: their
  stored provider, model, and effort settings yield to the file; other members
  keep their stored settings. The API and each turn use the same resolver;
  file errors block execution instead of falling back to a different provider.
  A file can specify a custom key directly or name a host environment variable.
  Members may inherit the optional shared default or define their own complete
  connection. The bridge injects only the selected member's credential into its
  process environment. A changed credential uses a fresh client without
  interrupting existing turns.
- Public execution metadata excludes authentication files, environment
  values, and endpoint userinfo/query credentials. Shared file credentials
  never enter member configuration, prompts, or public execution receipts.

### Artifact checks during a turn

`validate_artifacts` is a read-only SDK dynamic tool available to every member,
independent of provider. Its callback is bound to the active run, stage and
member; the model cannot select a different owner, project or validation scope.
It checks the caller's declared draft files and permitted sealed inputs using
the same pinned schema, reference and deterministic consistency rules as
publication. It reports findings and deferred checks without writing files,
running research scripts, publishing, or evaluating scientific correctness.
Independent peers' drafts and inputs excluded by the phase's role-specific
delivery rules remain unavailable through the tool.

Members may call it repeatedly in an ordinary turn. A call does not start a
second model or consume an automatic repair round. After submission, the engine
performs the closed-stage check and owns the two-round mechanical repair bound;
the bridge merely executes the scoped original-author follow-up. This does not
change the separate once-per-run researcher correction authorization.

Unchanged failing checks return a recovery diagnostic requesting an end to the
current turn. The bridge waits for the matching dynamic-tool `item/completed`
notification before interrupting, then collects terminal confirmation and
reported usage. The same ordering applies to an accepted P4 stop request or a
repeated unchanged P4 request. The dispatcher attaches its feedback before
serializing the response; the completion observer only confirms delivery and
initiates stopping. Unrelated tools retain their original SDK handlers.

The interrupt acknowledgement and exact-turn terminal result can arrive in
either order. The bridge requests interruption concurrently and lets the
terminal collector confirm stopping; a late or rejected interrupt reply cannot
invalidate an already completed or interrupted turn. If the event stream fails
or no terminal result arrives within the stop deadline, the thread remains
quarantined and queued experiments do not start. SDK protocol regression tests
cover both event orders and failed terminal confirmation.

Dynamic-tool declarations are fixed at thread creation. The thread's tool
availability marker covers artifact validation as well as provider retrieval.
A retained thread lacking the required tool declaration is renewed before the
next turn, preserving its recorded history and the normal context rules.

### Actionable control feedback

Tool responses retain successful shapes, validation statuses and readable
errors. Tool-call errors add `operation`, `code`, `json_pointer`, `hint` and
`execution_state`. Protocol and completion refusals retain the validator's
blocking findings and their exact object IDs and field pointers. Non-object
arguments are rejected before the bound controller callback. Calls remain bound
to the exact active thread and turn, and late results cannot return a stale
success. Responses and saved feedback pass through execution redaction.

`accepted: false` with `execution_state: "not_accepted"` means this request was
definitely refused before persistence. Earlier work may still be pending.
Failures after a possible state change use `execution_state: "unknown"` and
omit `accepted`; absence of acceptance is not permission to retry. Inspect the
saved controller request and attempt ledger first. Validation infrastructure
failures have an explicit setup hint and preserve the scientific artifacts.
An uncertain result remains decisive if another tool result arrives before the
turn stops; a later accepted response cannot replace its recovery diagnostic.

The transport envelope's `success` reports whether the tool exchange returned
normally. A delivered report can still contain `accepted: false` or validation
status `unavailable`. Neither transport completion nor a validation pass grants
publication authority.

### Web research with Kimi Code

The official Kimi Code endpoint (`https://api.kimi.com/coding/v1`) uses
`search_web` and `read_web_page`, registered as SDK dynamic tools. The
bridge calls Kimi's `/search` and `/fetch` services with the same captured
member credential. Native Responses web search is disabled for this endpoint;
other providers retain their native search configuration. This adds retrieval
tools without changing member roles, artifact contracts or publication authority.

Results preserve source titles, URLs, snippets and available extracted text.
Reading extent and truncation are explicit; the page reader supports offsets.
A page read is remote text extraction, not a local PDF download or a guarantee
of complete extraction. Retrieval failures return errors to the author and
appear in run activity. Tool results remain source material, not instructions.
Credentials stay in the transport and never enter tool arguments or receipts.

SDK 0.147 requires a narrow raw `thread/start` dynamic-tool declaration and
the generic `item/tool/call` callback. Registration, resumed-thread persistence
and result delivery were verified against its installed runtime. Declarations
are fixed at thread creation, so changing the retrieval tool set requires a
new thread. These SDK internals must be rechecked on SDK upgrades.

### Provider connection probe

**Test connection** drives one bounded exchange through the same client and
credential path as a real member turn. The service resolves the member's
effective settings — the saved `providers.toml` plus stored member
configuration, or an unsaved editor draft — builds a throwaway uncached
client, starts a new thread on an isolated probe home under
`data_root/probes/`, asks the model for exactly one call to a dynamic echo
tool (`provider_probe`) bound only to the probe turn, submits the tool result,
and requires a final response. The exchange is bounded at 45 seconds; the
probe home and workspace are deleted on success, failure, and timeout. Probes
never touch research threads, run history, or project documents.

The result reports the ordered stage checks — configuration, connection,
model response, tool exchange, final response — as ok, partial, or failed.
Failures are classified (invalid configuration, authentication, model
unavailable, endpoint protocol, tool call, timeout, rate limit, unknown) with
credential material redacted and upstream detail truncated; provider detail is
surfaced only for unclassified failures. The result names the tested settings
scope (saved or unsaved draft) and is marked simulated under the fake bridge.
Probe behavior is verified against SDK-seam fakes and the fake bridge.
Actual provider/model combinations require their own connection tests.

## 4. Failure semantics

- **Native startup checks**: a failed sandboxed command/write check stops the
  stage before research dispatch. Retain a bounded, redacted command diagnostic
  with exit status and the failed marker or cleanup condition so an operator can
  investigate the actual failure. A failed check never supplies a scientific
  finding, triggers an automatic paid retry, or relaxes the sandbox.
- **Provider failure or rate limit**: returned SDK failures become visible
  run failures. Automatic pause-until-reset and retry scheduling remain
  intended capabilities; the service does not silently resume paid work.
- **Harness crash**: restart reconciliation recovers an already committed
  publication or saved assessment; other interrupted runs become failed.
  Active stage labels also become terminal. No in-flight turn is reissued
  automatically. A later researcher-authorized run can resume a retained
  ordinary thread using its ID and home.
- **Compaction events** are recorded on the run (provenance note: context
  was compressed at this point).
- **Missing rollout evidence**: publication records explicit unavailability
  instead of substituting a thread ID for a content digest. SDK completion
  does not establish proof correctness or successful scientific publication.

## 5. Verified capability basis

Current SDK parameter shapes are checked against the pinned shared package.
Deterministic bridge and engine tests verify integration
behavior; they do not substitute for a paid live-provider acceptance run.
Provider limitations are documented in [ADR-008](../decisions/ADR-008-responses-shim.md).
Successful connection and tool checks do not establish scientific validity,
general token-cost or speed improvements, or support for every provider.

## 6. What the bridge never does

P4 capacity recovery recognizes the provider's exact capacity message, including
its known remote-compaction wrapper. An older generic failure receipt requires
confirmation that the exact latest provider turn stopped with that capacity
error before retry. The retry retains frozen inputs, completed experiments and
the remaining budget. Other compaction failures do not qualify for this path.

- Never writes formal state directly (orchestrator-only).
- Never lets a member thread call publication, correction-authorization,
  or lifecycle tools — members get no MCP route to authority.
- Never uses Codex `spawn_agent` for team orchestration.
