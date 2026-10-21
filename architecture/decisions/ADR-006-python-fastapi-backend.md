# ADR-006: Python + FastAPI backend

Status: accepted 2026-09-05

## Context

Codex offers a TypeScript SDK (older, broader) and a stable async Python
SDK (`openai-codex`). Our validation tooling, schema muscle, R toolchain,
and the model-forge reference codebase are Python.

## Decision

Backend: Python 3.12 + FastAPI + `AsyncCodex` from `openai-codex`.
Frontend: React + Vite, adapted conceptually from `model-forge/web`
(the DSH client is plugin-bound and not portable).

## Consequences

- Maximal reuse of Python validation/catalog tooling.
- If the Python SDK's surface lags the app-server protocol, the bridge may
  drop to raw JSON-RPC for specific calls — contained inside design/05's
  bridge module.
