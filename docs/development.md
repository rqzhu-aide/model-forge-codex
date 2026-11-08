# Development and verification

Use existing shared Python 3.11+ and Node.js 22+ installations. Follow the [installation guide](installation.md) for the canonical source setup and launch sequence. Install packages user-wide or machine-wide. Do not create a `.venv`, `.Rlib`, project-local `node_modules`, or a private copy of a runtime or development tool.

If a restricted terminal cannot access an existing shared installation, verify it through a normal-access check before treating it as missing. Set `MF_SHARED_NODE_MODULES` to the intended global package directory when automatic discovery selects the wrong installation.

## Source checkout

Use the supplied reviewer snapshot. From its root folder, follow [Python selection](installation.md#select-python), [Python dependency installation](installation.md#install-python-dependencies), [the frontend build](installation.md#build-the-interface), and [source launch](installation.md#launch-the-workbench). There is no public-package installation step. Source installation includes the backend and development dependencies.

The launcher opens `http://127.0.0.1:8766` and uses `~/.model-forge-codex` by default. For development, choose a separate research folder outside the repository with `--data-root PATH`. Keep the terminal open; finish or cancel research before using Ctrl+C. Stop the source service before updating its checkout, then rebuild and restart.

Use the same Python, data folder and port for [status and stop](installation.md#status-and-stop).

For the remaining POSIX Python examples, use `& $env:MF_PYTHON` in place of `"$MF_PYTHON"` in PowerShell.

Both launchers accept `--port NUMBER` and `--no-open`. The source launcher uses the Python that invokes it; the packaged launcher accepts `--python PATH` or `MF_PYTHON`.

## Prepared release tarball

This optional developer path tests a prepared local archive. It is separate from the reviewer source installation above. Copy the archive to the test machine as `candidate.tgz` and compare its SHA-256 with the value recorded when it was prepared: use `sha256sum candidate.tgz` on Linux, `shasum -a 256 candidate.tgz` on macOS, or `Get-FileHash ./candidate.tgz -Algorithm SHA256` in PowerShell.

Select the shared Python as described in [OS-specific setup](installation.md#select-python) and install the backend dependencies with that executable:

```sh
"$MF_PYTHON" -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
```

In PowerShell, replace `"$MF_PYTHON"` with `& $env:MF_PYTHON`. From the folder containing the archive, run:

```text
npm exec --yes --package ./candidate.tgz -- model-forge-codex web
```

Use that same local package for lifecycle commands:

```text
npm exec --yes --package ./candidate.tgz -- model-forge-codex status
npm exec --yes --package ./candidate.tgz -- model-forge-codex stop
```

Keep the same `MF_PYTHON`, data folder and port for these commands. In PowerShell, use `npm.cmd` if script policy blocks `npm.ps1`. This [npm exec](https://docs.npmjs.com/cli/v11/commands/npm-exec/) command uses the local archive through npm's user-wide cache; it does not publish it.

For a native installation smoke check without a checkout, copy the companion `scripts/verify_npm_candidate.py` beside the tarball. After shared Python setup, run:

```sh
"$MF_PYTHON" -B verify_npm_candidate.py ./candidate.tgz --sha256 REVIEWED_SHA256
```

Replace `REVIEWED_SHA256` with the recorded artifact hash. The helper checks the archive and uses disposable research data to check launch, the running release identity, served interface assets, shutdown and settings preservation. It records the native OS and runtime versions in a JSON receipt and makes no model requests. In PowerShell, replace `"$MF_PYTHON"` with `& $env:MF_PYTHON`. Browser interaction, account connection and scientific work still need separate checks.

The tarball includes the built interface and mathematics tools. It needs no frontend build packages. Application snapshots live in `~/.model-forge-codex-app/releases`, separately from research and settings. They contain application code, not private runtime installations. Starting the same release reuses its running service. Switching releases stops an idle earlier service; active research must finish or be cancelled first. [Recovery instructions](installation.md#recover-a-damaged-application-release) distinguish a damaged download from a damaged retained snapshot.

## Shared developer packages

Reuse an existing writable npm global prefix. On a POSIX system where the prefix is not writable and a Node version manager does not already manage it, npm supports a user-wide prefix:

```sh
npm config set prefix "$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
```

Then run the [global frontend installation](installation.md#build-the-interface) and set `export MF_SHARED_NODE_MODULES="$(npm root --global)"`. This changes the user's npm prefix, so do it only when needed. Use the equivalent environment setting in each new development terminal. See [npm's permissions guidance](https://docs.npmjs.com/resolving-eacces-permissions-errors-when-installing-packages-globally/). Do not use `sudo npm install` or fall back to project-local packages.

## Run development servers

The production source launcher serves a built interface. For frontend work, use separate backend and Vite development servers.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& $env:MF_PYTHON -m uvicorn model_forge_codex.service:app --host 127.0.0.1 --port 8766
```

In a POSIX shell:

```sh
PYTHONPATH=src "$MF_PYTHON" -m uvicorn model_forge_codex.service:app --host 127.0.0.1 --port 8766
```

In a second terminal, from the repository root:

```text
node web/scripts/vite.mjs dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies the API to `127.0.0.1:8766`; `MF_WEB_PORT` and `MF_API_URL` override those defaults. Its development cache stays in the system temporary directory. The [repository frontend guide](../web/README.md) explains shared package resolution.

Send browser API calls to relative `/api` URLs on the workspace origin. The development proxy preserves the browser's host and port. Browser requests that change workspace state use `Content-Type: application/json`, including actions with an empty body.

Use a separate research folder for development. Set `MF_CODEX_HOME` before starting the backend, and keep the folder outside the repository. To exercise the harness without model calls, also set `MF_CODEX_FAKE_BRIDGE=1`. Simulated results do not establish scientific behavior. Remove that variable before real model evaluation.

## Focused checks

Run the tests that cover the changed behavior. Backend tests need the source import path shown above. Typical commands from the repository root are:

```text
"$MF_PYTHON" -m pytest -q tests/test_npm_launcher.py
node --test web/tests/provider-editor.test.mjs
node web/scripts/vite.mjs build
```

For a broader regression run when the scope warrants it:

```text
"$MF_PYTHON" -m pytest -q
node --test web/tests/*.test.mjs
npm run test:npm
```

The build writes `web/dist`, including the self-hosted font licenses, and prepares the portable mathematics and report-export runtimes. These generated files are not source changes. A passing test or build does not certify model-authored scientific correctness.

For workflow catalog edits, verify integrity and declared examples with the existing catalog checks, including:

```text
"$MF_PYTHON" -m pytest -q tests/test_catalog_scientific.py
```

Read the applicable contract before changing catalog contents or their manifest. Check the generated member instructions and the fields consumed by the UI together. A documentation-only description does not establish executable behavior.

Browser verification is needed for changed navigation, keyboard and focus behavior, streaming progress, viewport layout, and service integration. Keep deterministic checks, browser checks, live model behavior, and scientific assessment distinct in your report of a change.

## Runtime and settings reference

| Setting | Purpose |
| --- | --- |
| `MF_CODEX_HOME` | Research and settings directory; defaults to `~/.model-forge-codex` |
| `MF_PYTHON` | Shared Python selected by the packaged Node launcher |
| `MF_CODEX_BIN` | Absolute path to an existing native Codex CLI |
| `CODEX_HOME` | Shared Codex home, including the native Windows sandbox setup |
| `MF_CODEX_PROVIDER_CONFIG` | Alternative shared provider file |
| `MF_SHARED_NODE_MODULES` | Shared npm package directory used for source builds |
| `MF_P4_PYTHON`, `MF_P4_RSCRIPT` | Shared computation runtimes for experiments |
| `MF_CODEX_FAKE_BRIDGE` | Set to `1` for simulated harness output without model calls |

The [model access guide](model-access.md) covers sign-in, provider configuration, and connection tests. Keep secrets in the host's local account or provider configuration, outside the repository.

## Prepare a package

Follow the [repository npm release guide](../architecture/npm-release.md) to prepare and smoke-test a local release tarball. `npm pack` runs the prepack build and verifies the final file inventory. Use shared frontend build dependencies; a prepared tarball does not require those packages on the user's machine.

The smoke script accepts `--node PATH` and `--npm-cli PATH` for existing shared installations. The latter selects npm's JavaScript CLI file, not a shell wrapper. Automatic discovery supports normal Node-adjacent layouts and the installed POSIX npm symlink. An explicit choice is not silently replaced.

Rebuild after source or README changes so the reviewed package contains the final bytes. Test with a disposable research folder and avoid real model calls unless separately intended. Package preparation and local testing do not publish a release.
