# Installation and troubleshooting

Run this reviewer snapshot from source using shared **Node.js 22+ with npm** and **CPython 3.11+** installations. Reuse suitable existing installations. Keep runtimes and packages user-wide or machine-wide; do not create a project-local environment or `node_modules`. The Codex desktop app is optional.

Open a terminal in the snapshot's root folder, which contains `pyproject.toml` and `package.json`. Follow the sequence below in that same terminal. It installs this snapshot rather than a public registry package.

## Select Python

First check `node --version` and `npm --version`. Install Node from its [official distribution](https://nodejs.org/en/download) or use an existing user-wide version manager if needed. Select a shared Python that permits user package installation.

### Windows

Use an existing shared Python, or install one from [Python.org](https://www.python.org/downloads/windows/). In PowerShell:

```powershell
$env:MF_PYTHON = (py -3 -c "import sys; print(sys.executable)").Trim()
& $env:MF_PYTHON --version
```

If several versions are installed, set the intended executable explicitly, for example `$env:MF_PYTHON = 'C:/path/to/shared/python.exe'`. `MF_PYTHON` is an executable path, not a command such as `py -3`.

### macOS

Use an existing suitable shared Python, or a [Python.org framework installation](https://docs.python.org/3/using/mac.html). Complete its **Install Certificates.command** step. For a Python 3.13 framework installation:

```sh
export MF_PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
"$MF_PYTHON" --version
```

Adjust the path to the version installed. Do not apply the pip commands below to an externally managed Homebrew Python.

### Linux

Reuse a suitable shared Python that permits user packages. Distribution Pythons often reject `pip --user` because they are externally managed. If needed, install shared CPython with [pyenv](https://github.com/pyenv/pyenv), following its [distribution-specific build prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment). With pyenv in its standard user-wide location:

```sh
"$HOME/.pyenv/bin/pyenv" install -s 3.13
export MF_PYTHON="$("$HOME/.pyenv/bin/pyenv" prefix 3.13)/bin/python3"
"$MF_PYTHON" --version
```

The version prefix resolves to a patch release. Its interpreter is shared across projects; do not use `pyenv local`, replace the OS Python, remove its external-management marker, or use `--break-system-packages`. See the [Python packaging specification](https://packaging.python.org/en/latest/specifications/externally-managed-environments/).

## Install Python dependencies

From the snapshot root, install the backend and development dependencies into the selected shared Python. In PowerShell:

```powershell
& $env:MF_PYTHON -m pip install --user "setuptools>=68" wheel
& $env:MF_PYTHON -m pip install --user --no-build-isolation ".[dev]"
```

In a macOS or Linux shell:

```sh
"$MF_PYTHON" -m pip install --user "setuptools>=68" wheel
"$MF_PYTHON" -m pip install --user --no-build-isolation ".[dev]"
```

## Build the interface

Install the frontend packages globally, then build the interface from the snapshot root:

```text
npm install --global react@18.3.1 react-dom@18.3.1 katex@0.18.7 vite@5.4.11 @vitejs/plugin-react@4.3.4 @fontsource-variable/ibm-plex-sans@5.3.0 @fontsource/ibm-plex-mono@5.3.0 @fontsource/marcellus@5.3.0
node web/scripts/vite.mjs build
```

If automatic discovery cannot find those shared packages, set `$env:MF_SHARED_NODE_MODULES = npm root --global` in PowerShell, or `export MF_SHARED_NODE_MODULES="$(npm root --global)"` in a POSIX shell, then rebuild. See [shared developer packages](development.md#shared-developer-packages) if the global prefix is not writable. If PowerShell blocks `npm.ps1`, use `npm.cmd` with the same arguments.

## Launch the workbench

In PowerShell:

```powershell
& $env:MF_PYTHON -B scripts/run_from_source.py
```

In a macOS or Linux shell:

```sh
"$MF_PYTHON" -B scripts/run_from_source.py
```

The launcher opens [http://127.0.0.1:8766](http://127.0.0.1:8766). Keep the terminal open. It uses the Python that invokes it; repeat the Python selection in a new terminal. `--no-open` skips opening the browser, and `--help` lists the options.

Before research, follow [model access and runtime setup](model-access.md) to connect an account or API provider and test each member's saved settings. On native Windows, complete the [one-time Codex sandbox setup](model-access.md#native-windows-setup). Managed Phase 4 numerical experiments require elevated Windows sandbox mode and shared scientific runtimes and packages accessible inside that sandbox.

## Status and stop

Finish or cancel active research through the app before stopping. From another terminal in the snapshot root, select the same Python and run:

```powershell
& $env:MF_PYTHON -B scripts/run_from_source.py status
& $env:MF_PYTHON -B scripts/run_from_source.py stop
```

In a macOS or Linux shell:

```sh
"$MF_PYTHON" -B scripts/run_from_source.py status
"$MF_PYTHON" -B scripts/run_from_source.py stop
```

## Research folders and updates

The default research folder is `~/.model-forge-codex`. It holds projects, local settings and the shared provider file, separately from application source. The native Codex account/sandbox home is normally `~/.codex`; its `CODEX_HOME` setting is separate.

Use `--data-root PATH` to choose another research folder and `--port NUMBER` for another instance. Supply the same data root and port to launch, `status`, and `stop`. Back up research independently of application files. Stop the source service before replacing its snapshot, then reinstall the Python source package, rebuild the interface, and restart with the same research folder. Existing projects retain their recorded workflow catalog and earlier research history.

If the app closes while updating a project's workflow, restart it and open the project. If the previous workflow version is displayed, retry the update; if the new version is displayed, continue working. Earlier runs and saved answers keep their original records.

## Verify the selected Python

Check the installed dependencies with the selected executable. In PowerShell:

```powershell
& $env:MF_PYTHON -c "import sys, fastapi, uvicorn, jsonschema, httpx, openai_codex; print(sys.executable)"
```

In a POSIX shell:

```sh
"$MF_PYTHON" -c 'import sys, fastapi, uvicorn, jsonschema, httpx, openai_codex; print(sys.executable)'
```

If a restricted terminal cannot start an existing installation, check that same executable in an ordinary terminal before reinstalling anything. If a dependency is missing, rerun the installation commands with the selected executable. Installed dependencies and a configured account do not establish a working model connection; use the app's connection tests.

## Recover a damaged application release

For a source snapshot, restore an intact copy and rebuild. Do not replace the research folder to repair application files.

When testing a [prepared release tarball](development.md#prepared-release-tarball), the launcher retains application code in `~/.model-forge-codex-app/releases/<release-id>`. An integrity error identifies whether the source archive or a retained release is damaged. Replace a damaged archive with an intact copy. For a damaged retained release:

1. Record the exact directory shown in the error. It must be one release beneath `~/.model-forge-codex-app/releases`.
2. Stop every instance using that release, including custom data roots or ports. If you cannot establish that they have all stopped, leave the directory in place.
3. Rename only that stopped release directory to an unused sibling name ending in `.damaged`. Keep other releases, research, and credentials intact.
4. Launch from the intact archive to recreate the application directory.

The packaged `stop` command does not prepare a retained snapshot first. Use each instance's matching data root and port. Repair never requires deleting projects or force-cancelling research.

## Platform verification

Windows package launch and browser onboarding were verified locally. A user reported a successful Linux installation of this release. Native macOS installation and tests at the minimum supported runtime versions are pending. These checks do not establish scientific correctness or working access to every model and experiment dependency.
