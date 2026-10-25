# Installation and troubleshooting

Use a shared Node.js 22+ installation with npm and a shared CPython 3.11+ installation. Reuse suitable existing installations. The examples below use Python 3.13 where a concrete version is needed; they do not change the minimum requirement. Install Node from its [official distribution](https://nodejs.org/en/download) or an existing user-wide version manager. Check `node --version` and `npm --version` in the terminal you will use.

The npm package contains the application, interface, fonts, mathematics renderer and HTML report exporter. It needs backend Python dependencies, but no frontend build packages. The Codex desktop app is optional. Keep runtimes and packages user-wide or machine-wide, outside research projects.

## Windows

Install shared Python from [Python.org](https://www.python.org/downloads/windows/) if needed. Open PowerShell and select the intended Python. This example captures the executable chosen by the Python launcher; if you have several installations, replace the first line with the absolute path to the one you intend to use.

```powershell
$mfPython = (py -3 -c "import sys; print(sys.executable)").Trim()
& $mfPython --version
& $mfPython -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
$env:MF_PYTHON = $mfPython
npx @rqzhu-aide/model-forge-codex@next web
```

For an explicit executable, use `$mfPython = 'C:/path/to/shared/python.exe'`. Do not pass a command string such as `py -3` as `MF_PYTHON`. Complete the [Windows Codex setup](model-access.md#native-windows-setup) before research; managed Phase 4 requires supported elevated sandbox setup.

If PowerShell blocks `npx.ps1`, use the installed `npx.cmd` with the same arguments. There is no need to change execution policy.

## macOS

If you do not already have a suitable shared Python that permits user package installation, use a Python.org installer, such as Python 3.13. Complete its **Install Certificates.command** step. Select that framework interpreter explicitly so Homebrew or another Python on PATH cannot receive the packages accidentally. See [Python's macOS installer guide](https://docs.python.org/3/using/mac.html).

```sh
export MF_PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
"$MF_PYTHON" --version
"$MF_PYTHON" -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
npx @rqzhu-aide/model-forge-codex@next web
```

Adjust `3.13` to the framework version you installed. This is a shared interpreter with user-wide dependencies. Do not apply this pip command to an externally managed Homebrew Python; use the selected framework interpreter instead.

## Linux

Reuse an existing shared Python that permits user packages, or install a normal user-wide CPython with [pyenv](https://github.com/pyenv/pyenv). Many distribution Pythons are externally managed and reject `pip --user`. The following Debian 12 example leaves the OS Python unchanged and requires compiler/development packages. Other distributions need their own [build prerequisites](https://github.com/pyenv/pyenv/wiki#suggested-build-environment).

```sh
sudo apt update
sudo apt install make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
```

If pyenv is not already installed, install it once in the standard shared user location:

```sh
git clone https://github.com/pyenv/pyenv.git "$HOME/.pyenv"
```

Use the existing pyenv location if different. Install a supported CPython once, select its actual executable, and install the dependencies:

```sh
"$HOME/.pyenv/bin/pyenv" install -s 3.13
export MF_PYTHON="$("$HOME/.pyenv/bin/pyenv" prefix 3.13)/bin/python3"
"$MF_PYTHON" --version
"$MF_PYTHON" -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"
npx @rqzhu-aide/model-forge-codex@next web
```

The pyenv version prefix resolves to a patch release. Its installed interpreter is shared across your projects; no `pyenv local`, virtual environment, or replacement of the system Python is needed. Do not use `--break-system-packages` or remove an external-management marker. See the [Python packaging specification](https://packaging.python.org/en/latest/specifications/externally-managed-environments/).

## Verify the selected Python

The environment setting above lasts for that terminal session. In a new terminal, set it again or supply `--python` with the same absolute executable path. An explicit selection is never silently replaced with another Python.

Check the dependencies in PowerShell:

```powershell
& $env:MF_PYTHON -c "import sys, fastapi, uvicorn, jsonschema, httpx, openai_codex; print(sys.executable)"
```

Or in a POSIX shell:

```sh
"$MF_PYTHON" -c 'import sys, fastapi, uvicorn, jsonschema, httpx, openai_codex; print(sys.executable)'
```

If a restricted terminal cannot start an existing installation, check that same executable in an ordinary terminal before reinstalling anything. If a dependency is missing, rerun the installation command with the selected executable. A configured account is separate from installed dependencies; use [model access](model-access.md) for sign-in and connection tests.

## Research folders and updates

The default research folder is `~/.model-forge-codex`. It holds projects, local settings and the shared provider file. The native Codex account/sandbox home is normally `~/.codex`; its `CODEX_HOME` setting is separate. Retained application code lives in `~/.model-forge-codex-app/releases/<release-id>`. These code snapshots contain no private runtime installations.

Use `--data-root PATH` to choose another research folder and `--port NUMBER` for another instance. Use the same Python, data root and port for its `web`, `status` and `stop` commands. For example:

```sh
npx @rqzhu-aide/model-forge-codex@next status --data-root "/path/to/research" --port 8767
npx @rqzhu-aide/model-forge-codex@next stop --data-root "/path/to/research" --port 8767
```

Finish or cancel active research through the app before stopping. Keep the research folder when updating the application. Relaunch the desired package version with the same folder; the launcher can replace an idle older service and refuses to interrupt active research. Existing projects retain their recorded workflow catalog. Back up your research folder independently of the application cache.

## Recover a damaged application release

An integrity error identifies the affected source or retained-release directory. A damaged downloaded source needs a fresh copy of that package. A damaged **retained release** will be reused even after downloading again, so it needs a separate, targeted repair:

1. Record the exact retained directory shown in the error. It must be one release beneath `~/.model-forge-codex-app/releases`, not the research folder or the entire releases folder.
2. Stop every Model Forge instance using that release, including instances with custom data roots or ports. One default `stop` command does not establish that all instances are idle. If you cannot establish that they have all stopped, leave the directory in place.
3. Rename only that stopped, damaged release directory to an unused sibling name ending in `.damaged`. Retain it for recovery. Leave other releases, research and credentials untouched.
4. Launch again from the intact downloaded package. The launcher validates and recreates the expected application directory.

The npm `stop` command runs from the downloaded package without preparing a retained snapshot first. Use it with each known instance's matching data root and port. Repair never requires deleting projects or force-cancelling research.

## Platform verification

Windows package launch and browser onboarding are tested locally. Native clean-profile macOS/Linux installation and the full minimum-version matrix remain pending. OS recipes are checked against upstream documentation; they are not a claim that every distribution, architecture or sandbox configuration has been tested.
