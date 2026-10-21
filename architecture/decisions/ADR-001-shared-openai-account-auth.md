# ADR-001: Shared OpenAI account authentication

Status: accepted 2026-09-05

Amended 2026-09-09 to expose account connection in Workspace, as requested
by the researcher. The shared-account model remains unchanged.

## Context

Team members need model access. Options: one shared ChatGPT/OpenAI account
on the host vs per-user accounts vs API-key billing. Codex supports ChatGPT
sign-in (`codex login`, portable auto-refreshing `auth.json`) and API keys.

## Decision

One shared OpenAI account can serve all four members. Workspace's OpenAI
Account panel shows host sign-in status and provides an explicit connection
action. If reusable file credentials are unavailable, the researcher can
complete the official Codex device sign-in in a separate workbench account
home, then connect it to the team. This does not replace the shared host login.

Amended 2026-10-19 for native Windows: the sandbox uses the shared runtime home,
so UI sign-in targets its file cache instead of a separate workbench home.
An existing file is preserved, and a cache Codex cannot confirm must be resolved
in Codex before another login. Status and research explicitly select the file
credential store, leaving OS keyring entries unchanged. macOS and Linux keep
the separate workbench device-login home. A legacy Windows workspace login is
not presented as a usable runtime connection; the shared runtime account must
be connected explicitly.

Connection fills empty OpenAI member homes, preserves existing credentials,
and records the selected account for future provisioning. Reading status never
copies credentials or initiates login. Credential bytes remain on the host.
Custom providers retain their configured host environment credentials.

## Consequences

- Usage limits are account-wide: four members share one rate pool. Heavy
  P4 workloads may stall. A reset does not authorize automatic re-execution.
- Mitigation (committed): rate-limit/usage telemetry is a first-class part
  of the run view (design/05 §4), so exhaustion is visible, not silent.
- Revisit trigger: the first full P4 on Codex, or the first observed
  mid-run rate-limit stall.
