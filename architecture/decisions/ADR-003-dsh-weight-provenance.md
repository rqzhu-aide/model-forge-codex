# ADR-003: DSH-weight provenance

Status: accepted 2026-09-05 , conditional on effort (met: the lighter
option)

## Context

The Hermes edition runs a full content-addressed artifact store plus an
authority hash chain. The DSH edition runs a publication journal +
receipts + sealed run dirs. Both answer "what was published, from which
bytes, after which agent activity" — at very different machinery cost.

## Decision

DSH-edition weight: append-only JCS-stamped journal, per-publication
receipts, current-slot indexes, and — new in this edition — Codex thread
rollout digests sealed at publication. No content-addressed store, no
authority hash chain.

## Consequences

- Enough evidence for audit and reproducibility narratives.
- Upgrade path preserved: the data a future hash-chain would need
  (digests, order, receipts) is already kept.
- Rollout files remain in member homes; only digests are sealed —
  retention of the homes is therefore part of the evidence chain.
