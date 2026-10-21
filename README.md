# Model Forge, Codex edition

Model Forge is a local, researcher-directed workbench for developing statistical models, machine learning models, and algorithms for a problem. A Research Lead, Theorist, Data Analyst, and Outside Reviewer support the investigation. The researcher chooses the question, directs consequential decisions, and decides what work to pursue.

The end product is a readable **technical report** that connects the proposed model to its mathematical justification, numerical evidence, limitations, and reproducible sources. Reports can also be exported as self-contained HTML with mathematics and retained figures.

**0.9.0 is a prerelease.** The application version is separate from the bundled workflow catalog, currently **1.26.0**. Existing projects retain their pinned catalog until they explicitly adopt an update.

## The research workflow

The interface has five phases:

| Phase | What you do |
| --- | --- |
| **Phase 1 - Define and Explore** | Clarify the research setting and study relevant literature. |
| **Phase 2 - Propose Methods** | Develop, compare, and select models or algorithms. |
| **Phase 3 - Theory** | Inspect assumptions, claims, proofs, and targeted theory revisions. |
| **Phase 4 - Numerical Eval** | Run a feasibility check or detailed evaluation, with implementation review, comparisons, uncertainty, and failures. |
| **Phase 5 - Report** | Assemble and revise the technical report, with review tied to its exact sources. |

You can discuss the problem and revise your instructions throughout the workflow. Saving an answer does not launch research. Results retain their original method and theory sources, and later revisions remain distinguishable from earlier evidence. An interim report can record incomplete numerical support; report completion and independent review are separate states.

## Install and start

Use the npm prerelease under **`next`**, the **0.9.0 release tarball** from the [GitHub prerelease](https://github.com/rqzhu-aide/model-forge-codex/releases/tag/v0.9.0), or a source checkout.

All routes require existing user-wide or machine-wide **Node.js 22+ with npm** and **Python 3.11+**. Model Forge does not install language runtimes or create project environments. Install the backend dependencies in your shared Python:

```text
python -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
```

Use `python3` or `py -3` consistently if that selects your shared Python. On managed systems that prohibit `--user`, use the supported user-wide or machine-wide installation method. The bridge currently requires the tested `openai-codex` 0.147 SDK series. Its SDK supplies a Codex CLI; the Codex desktop app is optional.

### npm prerelease

Start the current prerelease with:

```text
npx @rqzhu-aide/model-forge-codex@next web
```

To keep using this exact application version, replace `@next` with `@0.9.0`. The `next` tag can move to later prereleases; it is separate from `latest`. No global installation of Model Forge or frontend build is needed.

### Prepared release tarball

Download `rqzhu-aide-model-forge-codex-0.9.0.tgz` and `SHA256SUMS.txt` from the [GitHub prerelease](https://github.com/rqzhu-aide/model-forge-codex/releases/tag/v0.9.0), verify the tarball checksum, then run this from the download folder:

```text
npm exec --yes --package ./rqzhu-aide-model-forge-codex-0.9.0.tgz -- model-forge-codex web
```

The tarball includes the built interface and mathematics tools, so this route needs no frontend build packages. To build a tarball from source, use the [repository release guide](https://github.com/rqzhu-aide/model-forge-codex/blob/v0.9.0/architecture/npm-release.md).

### Source checkout

Install Git and the shared runtimes above, then run:

```text
git clone --branch v0.9.0 https://github.com/rqzhu-aide/model-forge-codex.git
cd model-forge-codex
python -m pip install --user "setuptools>=68" wheel
python -m pip install --user --no-build-isolation .
npm install --global react@18.3.1 react-dom@18.3.1 katex@0.18.7 vite@5.4.11 @vitejs/plugin-react@4.3.4
node web/scripts/vite.mjs build
python -B scripts/run_from_source.py
```

These commands select the 0.9.0 prerelease tag. The default branch can contain later changes. Do not create a project-local environment or `node_modules` directory. If shared npm packages are not discovered, set `MF_SHARED_NODE_MODULES` to the directory reported by `npm root --global`.

### First use

The launcher opens [http://127.0.0.1:8766](http://127.0.0.1:8766). Keep its terminal open. Finish or cancel research before pressing Ctrl+C to stop the service.

1. Create a project with your research question, how observations arise, intended use, and relevant constraints. Data are optional; unknown information can remain unknown.
2. Open **Workspace → OpenAI Account** to connect an account, or **Workspace → Team Settings → Configure agent models and providers** to configure an API key or another provider.
3. Choose available models and reasoning efforts for the team. Use **Test saved settings** for each member before launching research. Connection tests make small live model requests and can consume provider tokens.
4. Start a literature study in Phase 1, inspect the findings and decisions, then choose the next work to pursue.

See [model access and Windows setup](docs/model-access.md) for account sign-in, custom providers, and connection troubleshooting. On native Windows, complete the shared Codex runtime's one-time sandbox setup before research, including when using a custom provider. Experiments also need shared computation runtimes and packages accessible inside that sandbox.

## Saved work and updates

Research and settings default to `~/.model-forge-codex`, outside the checkout and npm cache. Use `--data-root PATH` or `MF_CODEX_HOME` to select another research folder. The packaged launcher accepts `--python PATH` or `MF_PYTHON` to select a shared Python; the source launcher uses the Python that invokes it. Both accept `--port NUMBER` and `--no-open`.

Use `status` or `stop` in place of `web`, with the same data folder and port. For npm:

```text
npx @rqzhu-aide/model-forge-codex@next status
npx @rqzhu-aide/model-forge-codex@next stop
```

From a source checkout:

```text
python -B scripts/run_from_source.py status
python -B scripts/run_from_source.py stop
```

Packaged application snapshots live separately in `~/.model-forge-codex-app/releases`. They contain application code, not private copies of language runtimes. Starting the same release reuses its running service. Switching releases stops an idle earlier service; active research must finish or be cancelled first. Stop a source service before updating its checkout, then rebuild and restart.

## Prerelease limits

- This is a local research application. Keep the service bound to the loopback address used by the launchers.
- Model-generated claims, proofs, code, and results require researcher judgment. Successful execution and structural validation do not establish scientific correctness or reliable unattended research.
- Provider access, supported models, usage limits, and experiment dependencies depend on your account and shared runtime setup. A successful connection test does not establish that a numerical experiment can run.
- Windows has recorded local package launch and shutdown checks. A clean macOS/Linux package launch and Ctrl+C exercise remain pending; cross-platform parity is not established for this prerelease.
- Interrupted work does not automatically resume into new research. Retained historical evidence is not automatically pooled into every later evaluation.

For contributor setup and focused verification, see [development](docs/development.md) and the [repository contributor guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/CONTRIBUTING.md). The [repository architecture guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/README.md) describes the workflow and implementation boundaries. Links labeled repository open source guides on GitHub; those files are not installed by the npm package. The project is licensed under the [MIT License](LICENSE).
