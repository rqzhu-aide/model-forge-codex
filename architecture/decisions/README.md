# Decisions

Accepted Architecture Decision Records for Model Forge (Codex edition).
The first seven decisions date to the initial architecture review.

| ADR | Decision |
|---|---|
| [ADR-001](ADR-001-shared-openai-account-auth.md) | One shared OpenAI account; host login supported through the workspace account panel |
| [ADR-002](ADR-002-branch-keyed-member-threads.md) | Threads keyed (member, phase, branch); lead spans the project |
| [ADR-003](ADR-003-dsh-weight-provenance.md) | Journal + receipts + sealed rollout digests; no hash chain |
| [ADR-004](ADR-004-codex-native-souls.md) | Souls via Codex-native per-member AGENTS.md |
| [ADR-005](ADR-005-per-member-codex-homes.md) | Per-member CODEX_HOME under the project root |
| [ADR-006](ADR-006-python-fastapi-backend.md) | Python + FastAPI + openai-codex Python SDK |
| [ADR-007](ADR-007-universal-contracts-package.md) | Universal contracts package, versioned pins |
| [ADR-008](ADR-008-responses-shim.md) | Responses-API shim for non-OpenAI providers (dev/test path) |
| [ADR-009](ADR-009-p2-explanation-quality.md) | Phase 2 scientific quality review remains separate from deterministic publication checks |
