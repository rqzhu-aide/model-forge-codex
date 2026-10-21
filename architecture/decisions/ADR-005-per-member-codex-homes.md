# ADR-005: Per-member CODEX_HOME

Status: accepted 2026-09-05

Amended 2026-09-10 for the native Windows runtime.

## Context

Codex roots all state (threads, memory pipeline, config, auth) at
`$CODEX_HOME`. A single shared home would blend all four members' automatic
memories into one summary and mix thread stores.

## Decision

Each member gets its own logical home under the project root
(`members/<role>/codex-home/`). On non-Windows systems this remains the
SDK process's CODEX_HOME.

On native Windows, the SDK process reuses the installed user's CODEX_HOME
(the launch environment's value, otherwise `~/.codex`). Codex 0.147 stores
sandbox setup under that home but provisions machine-wide sandbox users;
setting up each member independently would rotate the same users' passwords.
The bridge requires the shared sandbox to report ready and, for OpenAI,
requires the member and runtime account fingerprints to match. It does not
provision sandbox identities or copy their credentials.

Logical member homes, separate SQLite state (`<member-home>/state`), thread
registrations, role instructions, and scoped workspaces remain separate.
Runtime rollout files share the user's home. Automatic memory generation
and use are disabled in these Windows SDK processes. Project AGENTS discovery
and automatic skill instruction inclusion are disabled; the user's global
AGENTS guidance remains researcher-wide context, with its source and digest
recorded. The exact member soul is supplied as developer instructions (ADR-004).
Workspace-write and deny-all approval settings remain unchanged.

## Consequences

- Per-member souls and explicit thread/notebook continuity remain. On Windows,
  separate databases and thread identities do not imply physically isolated
  rollout storage or automatic native memory.
- Outside reviews and assessments retain fresh logical homes, databases,
  threads, and workspaces. On Windows they share native runtime storage and
  researcher-wide global guidance; this is not a claim of complete physical
  isolation from other runtime files.
- Cost: the bridge holds one app-server session per member (four per
  project) instead of one — accepted plumbing.
- Member homes are evidence (ADR-003); retention applies.
- The Windows runtime evidence (retained in the ignored local archive)
  records the failure, supported configuration, and live write acceptance.
