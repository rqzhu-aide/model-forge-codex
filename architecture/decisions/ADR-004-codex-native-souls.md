# ADR-004: Souls via Codex-native AGENTS.md

Status: accepted 2026-09-05

Amended 2026-09-10 to describe explicit soul delivery and the Windows runtime.

## Context

Each member has an editable soul (scientific stance). Codex offers two
channels: layered `AGENTS.md` files (global home scope + project scope) or
`model_instructions_file`, which *replaces* the harness's built-in
instructions wholesale and loses its tool-use tuning.

## Decision

Souls are stored in the member's logical home-level `AGENTS.md`. Start and
resume supply the captured exact contents as `developer_instructions`,
followed by the per-turn situation brief. Codex base instructions stay intact.
The harness does not currently generate a project/run workspace AGENTS file.

Non-Windows execution retains native instruction discovery. Under the
[native Windows exception](ADR-005-per-member-codex-homes.md), the runtime
uses the installed user's home. Its global AGENTS guidance remains shared
researcher context and its available source and digest are recorded; it is
separate from the explicitly supplied role soul. Project AGENTS discovery
and automatic skill instruction inclusion are disabled for those processes.

## Consequences

- Soul editing rewrites one file; exact submitted contents and their digest
  are recorded on runs. A complete seal of every SDK instruction remains
  outside the current guarantee.
- Persona strength is untested against Codex's tuned base instructions;
  if personas drift in practice, `model_instructions_file` is the
  documented escape hatch (revisit this ADR).
