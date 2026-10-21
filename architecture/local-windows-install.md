# Local Windows installation

Model Forge can serve its built interface and API from one local service at
`http://127.0.0.1:8766`. The Windows installer copies a release into the user's
application directory and adds shortcuts. It uses existing shared Python,
Node.js, Codex, and package installations. It never installs packages or copies
credentials.

Build and install from the repository root:

```powershell
node web/scripts/vite.mjs build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install_local_app.ps1
```

Use `-PythonPath` and `-NodePath` when the desired shared executables are not on
PATH. `MF_SHARED_NODE_MODULES` can identify the existing global npm package
directory. Missing dependencies stop installation with an actionable message.

Phase 4 experiments use a shared Python interpreter inside the Codex workspace
sandbox. `-ExperimentPythonPath` selects it independently of the service's Python
and is preserved in the desktop launcher configuration. For direct service runs,
set `MF_P4_PYTHON` to that existing interpreter. No project environment is created.
The experiment interpreter must be executable by the Windows sandbox account;
ordinary host execution alone does not establish this. The managed runner never
falls back to unrestricted Python if sandbox execution fails. Verify the selected
interpreter inside the sandbox on the machine where experiments will run.

`MF_P4_BUDGET_SECONDS` sets the default experiment budget, initially 600 seconds.
The researcher can override it at launch and explicitly add time when continuing
a paused study. This budget measures experimental computation, separately from
model planning and review. A Phase 4 run waiting for direction remains saved and
idle when the application stops or restarts.

The default application location is `%LOCALAPPDATA%\ModelForge`. Packaged
terminals can redirect that location; the installer reports the actual physical
path as `install_root` and pins it in the shortcuts. The default research data
location is `%USERPROFILE%\.model-forge-codex`. `-InstallRoot`,
`-DataRoot`, and `-Port` override these defaults. Later installations preserve
saved paths and the port unless explicitly overridden. Optional
`MF_CODEX_PROVIDER_CONFIG` and `CODEX_HOME` path overrides are retained so that
desktop shortcuts use the same existing configuration.

The **Model Forge** folder on the Desktop contains:

- **Open Model Forge**: start or reuse the local service, then open the browser.
- **Start Model Forge**: start or reuse the service without opening the browser.
- **Stop Model Forge**: stop the service when no research runs are active.

Processes started by these shortcuts run without a terminal window. Failed
shortcut actions show their error and write `launcher-error.log` in the
application directory. The ordinary Stop shortcut never cancels active work.

Add `-StartAtLogon` to the installer to create a Start shortcut in the current
user's Windows Startup folder. This is optional. Remove that shortcut from
`shell:startup` to disable automatic startup. An ordinary update leaves an
existing Startup shortcut in place. The `-SkipShortcuts` option is available
for testing or command-line-only installation.

For command-line control after installation, replace the placeholder with the
`install_root` path printed by the installer:

```powershell
$installedApp = '<install_root>'
powershell -NoProfile -ExecutionPolicy Bypass -File "$installedApp\ModelForge.ps1" status
powershell -NoProfile -ExecutionPolicy Bypass -File "$installedApp\ModelForge.ps1" open
powershell -NoProfile -ExecutionPolicy Bypass -File "$installedApp\ModelForge.ps1" stop
```

The execution-policy option applies only to that launcher process; it does not
change the user's Windows policy.

Only an explicit `stop -CancelActive` requests cancellation of active runs.

Each installation creates `releases/<release-id>` and validates the copied
application and catalog before atomically switching `current.json`. The
release contains source code, contracts, built browser assets, and the bundled
math checker. Shared frontend packages are needed for building, not for running
the built release. Project data, provider files, development data,
`node_modules`, and caches are excluded. Earlier releases remain available.

Installing an update does not restart an already running service. Finish active
work, stop the service, then use Open or Start to run the newly selected release.
The installed application is a snapshot. Editing the source checkout does not
change it; build and run the installer again to deploy those edits. Use
`-InstallRoot` with the reported physical path when updating from a different
terminal so that it updates the same installation.
After a shutdown or interruption, existing research remains saved, but unfinished
research does not automatically resume. Inspect its recorded status and explicitly
start the next work from the application.
Existing projects keep their workflow pins until the researcher chooses
**Update workflow** inside the application.

For a diagnosed native-runtime incompatibility, `MF_CODEX_BIN` can select an
existing shared Codex executable for this installation. The installer retains
that explicit path as `codex_bin`; its launcher supplies it only to Model Forge.
This does not change global PATH, account selection or member models. An installed
executable must pass the actual member command checks; sandbox setup status alone
does not establish tool usability. Command/write coverage does not certify native
editing, which needs a separate bounded check.

## Configure the research team

Before starting research, open the selected shared Codex executable once under
the same Windows user and `CODEX_HOME` and complete its native sandbox setup.
This is required for custom API providers as well as OpenAI accounts. The UI
and installer can open successfully before the sandbox is ready; **Test saved
settings** reports missing setup before a research turn starts. See the
[Windows runtime setup](../docs/model-access.md#native-windows-setup) and the
[official Windows sandbox guide](https://learn.chatgpt.com/docs/windows/windows-sandbox).

The OpenAI Account panel signs in to that shared runtime's file cache on
Windows. It preserves existing credential files and OS keyring entries. A new
sign-in still requires **Connect account to research team** before it fills
empty member connections. Custom providers need their own API key, with no
OpenAI account connection required.

Open a project, then choose **Team Settings**. Use **Configure provider** beside
a member's model, or **Configure agent models and providers** at the top of the page.
Choose the member to edit and select either the connected OpenAI account, a
custom provider, or the shared default.

For a custom provider, enter its identifier, base URL, model name, reasoning
effort, and API key. You can use the name of an existing environment variable
instead of storing a key in the local configuration. The base URL must support
the Responses API and function calls. A Chat Completions endpoint alone is not
compatible; use the project's Responses shim when needed. Only choose reasoning
effort values supported by the model, including `none` for models that accept it.

**Test these settings** checks the current editor values before saving. It does
not change the saved provider configuration or start research. **Test saved
settings** checks the member's saved connection. Each test includes a small model
request and a tool exchange, so it can consume provider tokens. Read the reported
stage if a test fails.

Provider settings saved in this editor apply to the corresponding member across
all projects. Member instructions and context thresholds remain separate
per-project settings. Keys stay in the local provider configuration and are not
copied into research artifacts. Changes apply to the next turn.
