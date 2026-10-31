# Model Forge, Codex edition

[![npm latest](https://img.shields.io/npm/v/%40rqzhu-aide%2Fmodel-forge-codex/latest?label=npm%20latest)](https://www.npmjs.com/package/@rqzhu-aide/model-forge-codex)
[![npm next](https://img.shields.io/npm/v/%40rqzhu-aide%2Fmodel-forge-codex/next?label=npm%20next)](https://www.npmjs.com/package/@rqzhu-aide/model-forge-codex?activeTab=versions)

The installation commands below follow the **`next` prerelease channel**. The badges show the versions currently available on npm.

Model Forge is a local workbench for developing statistical and machine learning models and algorithms with an AI research team. Start from a problem, compare approaches, examine theory and numerical evidence, and build a **technical report** with mathematics, citations, and links to supporting work.

**You direct the research.** The team invites your input on critical decisions affecting the scientific goal, model interpretation, statistical claims, data applicability, or meaningful resource tradeoffs. Each decision explains its consequences. Discuss the question, ask for the Lead's advice, and save an editable answer for future work. The Lead handles routine choices; you choose which phase to run next.

![Model Forge 0.9.3 research workbench showing a synthetic demonstration project](https://raw.githubusercontent.com/rqzhu-aide/model-forge-codex/main/docs/images/model-forge-overview.jpg)

*Earlier 0.9.3 interface with a synthetic demonstration project. The current source uses a brushed silver frame. The example content illustrates the interface and is not output from a live model run.*

## Install and use

Use shared **Node.js 22+ with npm** and **Python 3.11+** installations. Complete the one-time setup for **[Windows](docs/installation.md#windows)**, **[macOS](docs/installation.md#macos)**, or **[Linux](docs/installation.md#linux)**. This installs the backend dependencies and sets `MF_PYTHON` to the shared Python used for launch. Then run in the same terminal:

```sh
npx @rqzhu-aide/model-forge-codex@next web
```

In a new terminal, set `MF_PYTHON` again or pass `--python PATH` to that same shared executable. The package includes the built interface. No project environment or frontend build is needed, and the Codex desktop app is optional.

The app opens at **[http://127.0.0.1:8766](http://127.0.0.1:8766)**. Keep the terminal open while using it.

1. **Create a project.** Describe your problem, data collection, goal, and constraints. Data are optional.
2. **Connect the team.** In **Workspace → OpenAI Account**, sign in and connect the account to the research team, or configure an API provider in **Workspace → Team Settings**. Select available models and reasoning efforts, then run **Test saved settings** for each member. Tests may consume provider tokens; configured credentials alone do not establish a working connection.
3. **Start Phase 1.** Read the interpreted problem and findings, correct the team's understanding, and discuss consequential choices. Saving an answer or instruction does not start a research run. Work already underway keeps its recorded inputs.

For a first project, try: “Develop a model to predict an outcome from baseline and repeated measurements. I do not have data ready yet. Compare feasible approaches and explain which assumptions need my input.”

On native Windows, complete the shared Codex runtime's one-time sandbox setup. Managed **Phase 4 numerical experiments require elevated Windows sandbox mode and completed setup**, plus shared scientific runtimes and packages accessible inside the sandbox. See [model access and runtime setup](docs/model-access.md) for sign-in, API providers, and experiment dependencies.

Projects and settings are saved in **`~/.model-forge-codex`**, separately from application files. Use `--data-root PATH` for another folder or `--python PATH` for a specific shared Python. See `--help` for all options.

Finish or cancel active research before stopping. Use the same data folder and port when checking or stopping a custom instance:

```sh
npx @rqzhu-aide/model-forge-codex@next status
npx @rqzhu-aide/model-forge-codex@next stop
```

Use `@0.9.4` to pin this version or `@latest` for the default npm release. Use the same version or channel for `web`, `status`, and `stop`. For setup errors and updates, see [installation and troubleshooting](docs/installation.md). The development guide also covers [source installation](docs/development.md#source-checkout) and [GitHub tarballs](docs/development.md#prepared-release-tarball).

Windows package launch and browser onboarding have been checked locally. Native clean-profile macOS/Linux verification remains pending. Model-generated scientific claims and results require researcher review.

## Five research phases

Run the phases that serve your question, returning to earlier work when needed. Data are optional at the start; numerical work can use synthetic data or available real data.

| Phase | Purpose |
| --- | --- |
| **Phase 1 - Define and Explore** | Frame the problem and review the literature. |
| **Phase 2 - Propose Methods** | Formulate, compare, and select methods. |
| **Phase 3 - Theory** | Examine assumptions, claims, and mathematical arguments. |
| **Phase 4 - Numerical Eval** | Implement and evaluate methods on synthetic or available real data. |
| **Phase 5 - Report** | Read, discuss, revise, and export the technical report. |

![Researcher response in Model Forge 0.9.3 showing the Lead's recommendation, alternatives, and answer controls](https://raw.githubusercontent.com/rqzhu-aide/model-forge-codex/main/docs/images/model-forge-decisions.jpg)

*Choosing which population a treatment effect should describe. This illustrative selection has not been saved; the researcher can add a note or give a different response. The content is synthetic, not live model output.*

## Architecture and design

- **Specialized team.** A Research Lead, Theorist, Data Analyst, and Outside Reviewer work through a Codex bridge. Structured outputs feed the interface directly.
- **Researcher interaction.** Blue marks team findings, navy marks system controls, and orange marks researcher input. Questions support discussion, advice, and editable answers. Reports support section-level discussion and self-contained HTML export.
- **Traceable work.** Findings link to their method, theory, and experiment sources. Application updates preserve research history; each project retains its workflow catalog until explicitly updated.
- **Consistent scientific presentation.** A shared notation record carries mathematical definitions across phases. The Lead uses presentation guidance for summaries, notation, tables, figures, and consequential questions.
- **Local workspace.** React provides the interface and FastAPI manages runs and artifacts. Research is stored locally; model requests go to your configured account or provider.

See the [architecture guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/README.md) for component responsibilities, artifact flow, and UI specifications.

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
