# Contributing to Model Forge

Model Forge supports researcher-directed development of statistical models, machine learning models, and algorithms. Changes should help researchers understand the scientific account, make meaningful decisions, and obtain a technical report whose claims can be traced to their sources.

Read the [README](README.md), [development guide](docs/development.md), and relevant [repository architecture documentation](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/README.md) before editing. Keep changes focused and preserve existing research history. Use only shared user-wide or machine-wide runtimes, packages, and development tools.

## Repository contents

| Location | Purpose |
| --- | --- |
| `src/`, `bin/`, `web/src/`, `web/scripts/` | Application and launcher source |
| `contracts/` | Versioned workflow catalog, member instructions, schemas, examples, and integrity manifest |
| `tests/`, `web/tests/` | Regression checks and intentional fixtures |
| `scripts/` | Build, installation, validation, preview, and developer tools |
| `config/*.example.toml` | Configuration examples without credentials |
| `docs/` | Public setup and development guidance |
| `architecture/`, `design-system/` | Workflow design, responsibilities, and interface specifications |

The application release version and workflow catalog version have different meanings. The current source tree prepares application version 0.9.4; its workflow catalog version is recorded in `contracts/VERSION`. Source changes do not change an already published package. A catalog update is not an automatic migration of existing projects. Do not move or reseal catalog files as part of unrelated cleanup. Historical fixtures can remain necessary even when their format is older.

## Keep private and generated files local

Never commit populated provider files, API keys, account caches, tokens, raw research homes, or live-run logs and exports containing private material. Use generic examples and intentional fixtures when a change needs a reproducible case. Check the proposed file list before sharing.

`web/dist/`, `web/runtime/`, and `npm-release-manifest.json` are generated release outputs. They remain ignored in Git and are deliberately included in the npm package. Put release tarballs under ignored `dist/`. Shared runtimes and package installations stay outside the repository.

## Verify the affected behavior

Use focused checks from the [development guide](docs/development.md). For a workflow change, check the executable contracts and the researcher-facing projection together. Preserve frozen sources, method lineage, and the distinction between discussion, published scientific changes, and researcher decisions. A passing build establishes neither scientific validity nor live model reliability.

For interface changes, verify the affected interaction in a browser, including keyboard use and relevant viewport sizes. For any change to text a researcher reads, fill in the reader acceptance block in [AGENTS.md](AGENTS.md) and include it with the change. For model behavior claims, state the provider, scope, and limits of any live evaluation separately from deterministic tests.

Before proposing a change, run `git diff --check`, inspect `git status --short`, and review the diff and file list. Explain the problem, the researcher-facing result, relevant verification, and any remaining limitation. Packaging and publication follow the [repository release guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/npm-release.md); rebuilding and testing a tarball do not publish it.
