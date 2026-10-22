# Model Forge, Codex edition

[![Version 0.9.0 prerelease](https://img.shields.io/badge/version-0.9.0--prerelease-blue)](https://www.npmjs.com/package/@rqzhu-aide/model-forge-codex/v/0.9.0)

Model Forge is a local workbench for developing statistical models, machine learning models, and algorithms with an AI research team. Start with a problem, explore methods, examine theory and numerical results, and produce a concise **technical report** with mathematical notation, citations, and reproducible sources.

## Install and use

Use shared **Node.js 22+ with npm** and **Python 3.11+** installations. Install the Python dependencies once, then launch the prerelease:

```sh
python -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
npx @rqzhu-aide/model-forge-codex@next web
```

Use `python3` or `py -3` if that selects your shared Python. Where `--user` is unavailable, use your system's supported shared installation method. No project environment or frontend build is needed. The Codex desktop app is optional.

The app opens at **[http://127.0.0.1:8766](http://127.0.0.1:8766)**. Keep the terminal open while using it.

1. **Create a project.** Describe your problem, data collection, goal, and constraints. Data are optional.
2. **Connect the team.** Use **Workspace → OpenAI Account**, or configure an API provider in **Workspace → Team Settings**. Select available models and run **Test saved settings** for each member. Tests use your provider account and may consume tokens.
3. **Start Phase 1.** Read the findings, discuss consequential choices, and choose which phase to run next. Saving a comment or instruction does not start a research run.

On native Windows, complete the shared Codex runtime's one-time sandbox setup before research. See [model access and setup](docs/model-access.md) for sign-in, API providers, Windows setup, and experiment dependencies.

Projects and settings are saved in **`~/.model-forge-codex`**, separately from application files. Use `--data-root PATH` for another folder or `--python PATH` for a specific shared Python. See `--help` for all options.

Finish or cancel active research before stopping. Use the same data folder and port when checking or stopping a custom instance:

```sh
npx @rqzhu-aide/model-forge-codex@next status
npx @rqzhu-aide/model-forge-codex@next stop
```

`@next` tracks prereleases; use `@0.9.0` to pin this version. The development guide also covers [source installation](docs/development.md#source-checkout) and [GitHub tarballs](docs/development.md#prepared-release-tarball).

## Architecture and design

| Phase | Purpose |
| --- | --- |
| **Phase 1 - Define and Explore** | Frame the problem and review the literature. |
| **Phase 2 - Propose Methods** | Formulate, compare, and select methods. |
| **Phase 3 - Theory** | Examine assumptions, claims, and mathematical arguments. |
| **Phase 4 - Numerical Eval** | Implement and evaluate methods on synthetic or available real data. |
| **Phase 5 - Report** | Read, discuss, revise, and export the technical report. |

- **Researcher direction.** The Lead handles routine choices and raises consequential decisions with concise explanations and options.
- **Specialized team.** A Research Lead, Theorist, Data Analyst, and Outside Reviewer work through a Codex bridge. Structured outputs feed the interface directly.
- **Clear interaction.** Blue marks team findings, green marks system controls, and orange marks researcher input. Reports support section-level discussion and self-contained HTML export.
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
