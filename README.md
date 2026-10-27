# Model Forge, Codex edition

[![Version 0.9.3 prerelease](https://img.shields.io/badge/version-0.9.3--prerelease-blue)](https://www.npmjs.com/package/@rqzhu-aide/model-forge-codex/v/0.9.3)

Model Forge is a local workbench for developing statistical models, machine learning models, and algorithms with an AI research team. Start with a problem, explore methods, examine theory and numerical results, and produce a concise **technical report** with mathematical notation, citations, and reproducible sources.

**Interactive model development is a core feature.** The team actively invites your feedback on critical decisions affecting model interpretation, assumptions, statistical inference, or practical use. Decision cards explain what is affected and the trade-offs. You can discuss the issue, request a recommendation, choose an option, or save an editable instruction to guide subsequent work. The Lead handles routine choices.

## Install and use

Use shared **Node.js 22+ with npm** and **Python 3.11+** installations. Follow the one-time setup for your system: **[Windows](docs/installation.md#windows)**, **[macOS](docs/installation.md#macos)**, or **[Linux](docs/installation.md#linux)**. Each route installs the backend dependencies and selects the same Python for launch using `MF_PYTHON`.

```sh
npx @rqzhu-aide/model-forge-codex@next web
```

Run this in the terminal where you selected Python. In a new terminal, set `MF_PYTHON` again or pass `--python PATH` to that same shared executable. No project environment or frontend build is needed. The Codex desktop app is optional.

The app opens at **[http://127.0.0.1:8766](http://127.0.0.1:8766)**. Keep the terminal open while using it.

1. **Create a project.** Describe your problem, data collection, goal, and constraints. Data are optional.
2. **Connect the team.** Use **Workspace → OpenAI Account**, or configure an API provider in **Workspace → Team Settings**. The run controls show missing connection settings for team members. Configured credentials do not mean a connection has been tested. Select available models and run **Test saved settings** for each member; tests may consume provider tokens.
3. **Start Phase 1.** Read the findings, discuss consequential choices, and choose which phase to run next. Saving a comment or instruction does not start a research run.

On native Windows, complete the shared Codex runtime's one-time sandbox setup. Managed Phase 4 numerical experiments require its supported **elevated sandbox** setup. See [model access and setup](docs/model-access.md) for sign-in, API providers, Windows setup, and experiment dependencies.

Projects and settings are saved in **`~/.model-forge-codex`**, separately from application files. Use `--data-root PATH` for another folder or `--python PATH` for a specific shared Python. See `--help` for all options.

Finish or cancel active research before stopping. Use the same data folder and port when checking or stopping a custom instance:

```sh
npx @rqzhu-aide/model-forge-codex@next status
npx @rqzhu-aide/model-forge-codex@next stop
```

`@next` tracks prereleases; use `@0.9.3` to pin this version. The development guide also covers [source installation](docs/development.md#source-checkout) and [GitHub tarballs](docs/development.md#prepared-release-tarball).

For example, start a project with: “Develop a model to predict an outcome from baseline and repeated measurements. I do not have data ready yet. Compare feasible approaches and explain which assumptions need my input.” For setup errors, updates, and application-cache recovery, see [installation and troubleshooting](docs/installation.md).

## Architecture and design

| Phase | Purpose |
| --- | --- |
| **Phase 1 - Define and Explore** | Frame the problem and review the literature. |
| **Phase 2 - Propose Methods** | Formulate, compare, and select methods. |
| **Phase 3 - Theory** | Examine assumptions, claims, and mathematical arguments. |
| **Phase 4 - Numerical Eval** | Implement and evaluate methods on synthetic or available real data. |
| **Phase 5 - Report** | Read, discuss, revise, and export the technical report. |

- **Specialized team.** A Research Lead, Theorist, Data Analyst, and Outside Reviewer work through a Codex bridge. Structured outputs feed the interface directly.
- **Clear interaction.** Blue marks team findings, navy (Illini Blue) marks system controls, and orange marks researcher input. Reports support section-level discussion and self-contained HTML export.
- **Traceable work.** Results retain their method, theory, and experiment sources. Application updates preserve research history; each project retains its workflow catalog until explicitly updated.
- **Local workspace.** React provides the interface and FastAPI manages runs and artifacts. Research is stored locally; model requests go to your configured account or provider.

See the [architecture guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/README.md) for component responsibilities, artifact flow, and UI specifications.

**Prerelease status:** Windows package launch and shutdown have been checked; clean macOS/Linux verification remains pending. Model-generated scientific claims and results require researcher review.

## Development

The [development guide](docs/development.md) covers source installation, local servers, focused tests, and package preparation. Use shared runtimes and packages, and a separate research folder for development.

```text
src/model_forge_codex/   Backend, orchestration, storage, and Codex bridge
web/                    React interface and frontend checks
contracts/              Versioned team instructions, schemas, and examples
tests/                  Backend and package checks
architecture/           System design and interface specifications
```

Read [CONTRIBUTING](https://github.com/rqzhu-aide/model-forge-codex/blob/main/CONTRIBUTING.md) before changing workflow contracts or preparing a release. Application and workflow catalog versions are maintained separately.

[MIT License](LICENSE).
