# ADR-008: Responses-API shim for non-OpenAI providers (dev/test path)

Status: accepted 2026-09-05 implemented
same day (`src/model_forge_codex/shim.py`).

Current scope clarification (2026-09-08): provider transport does not
change scientific authority, method activation, or the separate assessment
lane. All use the same frozen-input, isolated-review, and atomic-publication
rules in the [binding specification](../SPEC-context-and-artifacts.md).
The provider and CLI observations below are dated test evidence, not a
claim about every provider's current capabilities.

Current Z.AI documentation checked 2026-09-10 now specifies a native
Responses endpoint, `https://api.z.ai/api/v1`, for GLM-5.3 in Codex.
Its `https://api.z.ai/api/anthropic` endpoint is for Anthropic-compatible
clients. Use the native Responses route for this harness when the account
supports it; the optional shim remains for Chat Completions-only services.
Sources: [Z.AI Codex integration](https://docs.z.ai/devpack/tool/codex) and
[model switching](https://docs.z.ai/devpack/latest-model).

Live native acceptance on 2026-09-10: a separate diagnostic turn through the
harness's `SdkCodexBridge` and installed SDK 0.147.0 completed with GLM-5.3,
high reasoning, and the native Responses endpoint. The app-server acknowledged
the intended model/provider/effort, and the model returned the requested check
phrase. No research phase was started. This verifies authentication and a basic
SDK turn, not literature search, tool execution, or a complete research phase.
The SDK reported a 258,400-token context window in this check; provider-specific
catalog metadata for a larger context has not been configured.

## Context

ADR-001 chose a shared OpenAI/ChatGPT account. Without an available
account, live testing was blocked. Empirical probe (2026-09-05): codex-cli
0.147 removed `wire_api = "chat"` — custom providers MUST speak the
Responses API. GLM (z.ai), Kimi, and DeepSeek only speak Chat Completions.

## Decision

Ship a small FastAPI **shim** that accepts Responses API calls from Codex
and translates to Chat Completions against one upstream provider. Members
configure **custom provider** mode manually in Team Settings: Provider ID,
model, Base URL, API-key environment variable name, and reasoning effort.
No provider preset is required or selected; secrets stay in the host
environment. The Base URL can point directly to a Responses-compatible
endpoint or to this optional shim for a Chat Completions upstream. ADR-001
remains the production default; the shim is the dev/test path and a long-term
multi-provider escape hatch.

## Verified 2026-09-05

- `codex exec` → shim → z.ai **glm-5.3-flash**: complete agent turn,
  file-writing tool call, token accounting.
- Member soul (AGENTS.md) loaded from a provisioned member home; the model
  answered in character.

## Consequences

- Dropped in translation: `namespace` tools (member sub-agent spawning),
  `web_search`, and reasoning/encrypted-content fields. A reviewer using
  this shim must report unavailable search honestly; a public-search
  allowance in the review brief does not make the tool available.
- The shim has a direct `/responses/compact` route, but the dated Codex
  app-server probe did not call it and the thread stalled. The harness
  uses provider-independent thread rotation and a saved handoff rather
  than relying on that compaction path.
- `developer` role maps to `system` (GLM/DeepSeek reject "developer").
- Upstream calls are non-streaming; the shim emits the full SSE sequence
  after the completion returns (turn latency = provider latency).
- A per-provider quota panel remains an intended extension, not a
  currently implemented shim quota guarantee.
