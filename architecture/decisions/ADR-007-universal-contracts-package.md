# ADR-007: Universal contracts package

Status: accepted 2026-09-05 (extended to "universal"); executed same
day

## Context

The 46-schema contract catalog + phase contracts + golden/invalid examples
are the most valuable harness-agnostic assets of the product family. They
lived inside `model-forge/architecture`, coupled to that repo's clock.

## Decision

The catalog is a standalone, versioned package: `~/product/model-forge-contracts`
(v1.0.0, tagged). Every edition — model-forge, model-forge-dsh,
model-forge-codex, and future products — pins a catalog version via
`catalog-pin.json` (version + manifest sha256 + sync time) and syncs
deliberately with `tools/sync_to.py`. The package carries a standalone
validator (`tools/validate_catalog.py`) for the portable core; the full
narrative cross-checks remain in model-forge until that edition migrates.

## Consequences

- One catalog, three+ consumers; schema evolution is versioned and
  deliberate instead of accidental.
- Versioning rules (semver by validation outcome) are normative — see the
  package README.
- model-forge's internal copy remains authoritative for that edition until
  it migrates to pinning (per-edition work, not this edition's).
