# Development and verification

Use the [source installation steps](../README.md#source-checkout) and existing shared Python 3.11+ and Node.js 22+ installations. Install packages user-wide or machine-wide. Do not create a `.venv`, `.Rlib`, project-local `node_modules`, or a private copy of a runtime or development tool.

If a restricted terminal cannot access an existing shared installation, verify it through a normal-access check before treating it as missing. Set `MF_SHARED_NODE_MODULES` to the intended global package directory when automatic discovery selects the wrong installation.

## Python development dependencies

From the repository root, install the development extras into the same shared Python:

```text
python -m pip install --user --no-build-isolation ".[dev]"
```

The build requires shared `setuptools>=68`, as described in the README. On systems that prohibit `--user`, use the supported shared installation method.

## Run development servers

The production source launcher serves a built interface. For frontend work, use separate backend and Vite development servers.

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m uvicorn model_forge_codex.service:app --host 127.0.0.1 --port 8766
```

In a POSIX shell:

```sh
PYTHONPATH=src python -m uvicorn model_forge_codex.service:app --host 127.0.0.1 --port 8766
```

In a second terminal, from the repository root:

```text
node web/scripts/vite.mjs dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies the API to `127.0.0.1:8766`; `MF_WEB_PORT` and `MF_API_URL` override those defaults. Its development cache stays in the system temporary directory. The [repository frontend guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/web/README.md) explains shared package resolution.

Use a separate research folder for development. Set `MF_CODEX_HOME` before starting the backend, and keep the folder outside the repository. To exercise the harness without model calls, also set `MF_CODEX_FAKE_BRIDGE=1`. Simulated results do not establish scientific behavior. Remove that variable before real model evaluation.

## Focused checks

Run the tests that cover the changed behavior. Backend tests need the source import path shown above. Typical commands from the repository root are:

```text
python -m pytest -q tests/test_npm_launcher.py
node --test web/tests/provider-editor.test.mjs
node web/scripts/vite.mjs build
```

For a broader regression run when the scope warrants it:

```text
python -m pytest -q
node --test web/tests/*.test.mjs
npm run test:npm
```

The build writes `web/dist` and prepares the portable mathematics and report-export runtimes. These generated files are not source changes. A passing test or build does not certify model-authored scientific correctness.

For workflow catalog edits, verify integrity and declared examples with the existing catalog checks, including:

```text
python -m pytest -q tests/test_catalog_scientific.py
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

Follow the [repository npm release guide](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/npm-release.md) to prepare and smoke-test the release tarball. `npm pack` runs the prepack build and verifies the final file inventory. Use shared frontend build dependencies; a prepared tarball does not require those packages on the user's machine.

Rebuild after source or README changes so the reviewed package contains the final bytes. Test with a disposable research folder and avoid real model calls unless separately intended. Package preparation and local testing do not publish a release.
