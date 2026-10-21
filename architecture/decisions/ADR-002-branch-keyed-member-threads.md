# ADR-002: Branch-keyed member threads

Status: accepted 2026-09-05 (with the branch refinement)

Implementation clarification, 2026-09-27: the keyed registry and project-wide
lead are implemented. Automatic archival of branch threads on method retirement
below remains an original lifecycle intention, not a current feature. Focused
assessments and explanations use fresh isolated contexts and saved discussion.

## Context

Thread granularity trades context continuity and prefix-cache efficiency
against context pollution and provenance clarity. Options ranged from
fresh-thread-per-run (Hermes edition; maximal reproducibility, cold
corrections) to one-thread-per-member-per-project (maximal continuity).

## Decision

Threads are keyed `(member, phase, branch)`:

- research_lead: one thread per project — oversees all branches via
  summaries (briefs, receipts, syntheses), never working rollouts.
- theorist, data_analyst: trunk threads for P1/P2; one thread per method
  branch for P3/P4 respectively. Retiring a method archives its branch
  threads.
- outside_reviewer: one fresh thread per branch P5 review (also protects
  review independence).

## Consequences

- Corrections and retries reuse the thread that produced the work — the
  edition's core advantage (corrections with full context).
- Bit-reproducibility is weaker than the Hermes edition (compaction,
  memory drift); mitigated by stored briefs and sealed rollout digests
  (ADR-003), not eliminated.
- The orchestrator must implement branch-aware thread registry and lead
  summary routing (design/01, design/04 §5).
