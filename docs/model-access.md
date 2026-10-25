# Model access and runtime setup

Model Forge runs model work through its Codex bridge. You can connect an OpenAI account or configure a custom provider with an API key. Model availability and reasoning efforts depend on the chosen account or provider. Choose values you can access and test every team member's effective settings before research.

The [installation guide](installation.md) covers shared Python and Node.js setup and selecting the same `MF_PYTHON` for installation and launch. Do not create a project-local environment or download a private runtime for the app.

## Select the shared Codex runtime

The workbench discovers a native Codex CLI on `PATH`, then the CLI supplied by the shared `openai-codex` Python package. To choose a specific existing shared executable, set `MF_CODEX_BIN` to its absolute path before starting the service. For example, in PowerShell:

```powershell
$env:MF_CODEX_BIN = 'C:/path/to/shared/codex.exe'
```

The selected executable handles sign-in, research turns, and managed experiments. An invalid override is reported without silently selecting another installation. On Windows, select the native `.exe`, rather than a `.cmd`, `.bat`, or PowerShell wrapper.

## Native Windows setup

Before using either an OpenAI account or a custom provider on native Windows, open Codex under the same Windows user and `CODEX_HOME` that will run Model Forge, and complete its one-time sandbox setup. The app checks readiness; it does not initialize or replace sandbox identities.

If `codex` is not on `PATH`, open the CLI supplied by your existing shared Python package from PowerShell:

```powershell
$codexExecutable = & $env:MF_PYTHON -c "from codex_cli_bin import bundled_codex_path; print(bundled_codex_path())"
& $codexExecutable
```

When `MF_CODEX_BIN` is set, open that executable instead. Complete the setup offered by Codex, then return to Model Forge and test the team connections.

Managed **Phase 4 numerical experiments require elevated Windows sandbox mode and completed setup**. Model Forge checks the selected mode and readiness before preparing that numerical work; it does not change the mode, initialize identities or relax experiment access rules. An unelevated sandbox may report ready for other Codex operations but does not support the managed experiment contract. Earlier phases retain their own native-tool checks rather than a new global elevated-mode requirement. A setup or access-preparation error should be resolved as a runtime issue, not by replacing research data.

Numerical experiments need a shared Python or R installation and the required scientific packages accessible inside the sandbox. A successful model connection alone does not check this. Set `MF_P4_PYTHON` or `MF_P4_RSCRIPT` before launch to select a particular shared experiment runtime. On Windows, experiment Python discovery prefers the existing shared Codex desktop Python, then falls back to the service interpreter. The desktop app is optional.

These overrides are executable **paths**. Absolute paths are clearest; relative paths belong to the terminal that launches the packaged app, and `~/...` refers to the user's home. Do not pass arguments or a shell command. Leave `MF_P4_RSCRIPT` unset to discover `Rscript` on PATH.

## Connect an OpenAI account

1. Open **Workspace → OpenAI Account**.
2. If an existing host sign-in is available, choose **Connect account to research team**. Otherwise choose **Sign in with OpenAI**, open the offered OpenAI sign-in page, and enter the displayed code.
3. After sign-in, choose **Connect account to research team**. Signing in and connecting the team are separate actions.
4. In **Workspace → Team Settings**, choose **OpenAI account** for the members that should use it, select available models and reasoning efforts, and use **Test saved settings** for each member.

Connection fills empty account-backed member connections and preserves existing credentials. Account tokens stay on the host; the browser receives account status and the short sign-in code. Existing member connections can therefore differ from a newly connected account.

On Windows, sign-in uses the shared native runtime's file cache. If its existing sign-in cannot be confirmed, resolve that account in Codex before trying again. On macOS and Linux, device sign-in uses a separate workbench account cache. The connection uses file-backed credentials; it does not copy an OS keyring entry. Example previews display account status but do not permit sign-in or connection.

The app may report that device-code login needs enabling in account security settings. Follow the sign-in message and your workspace's access rules. Model Forge does not grant account or model access.

## Configure an API key or another provider

An OpenAI account connection is optional when using a custom provider.

1. Open **Workspace → Team Settings → Configure agent models and providers**.
2. For a team-wide default, choose **Shared connection → Add shared default → Custom provider**. You can instead select one team member for its own connection.
3. Enter the provider ID, exact model name, base URL, supported reasoning effort, and API key or backend environment variable name.
4. Use **Test these settings** on the member, then **Save model and provider settings**. Test the saved settings before starting research.

The base URL must be an API base such as `https://api.example.com/v1`, rather than a full `/responses` request URL. The endpoint must support the Responses API and tool calls used by the bridge. A Chat Completions-only endpoint is insufficient.

The provider editor saves a file shared across projects on this backend. Its location is shown in Team Settings. The default is `~/.model-forge-codex/providers.toml`, or `MF_CODEX_HOME/providers.toml` with a custom research folder. Set `MF_CODEX_PROVIDER_CONFIG` before launch to use a different file.

### Edit provider settings as TOML

You can copy the repository's [providers.example.toml](https://github.com/rqzhu-aide/model-forge-codex/blob/main/config/providers.example.toml) to the displayed file location and edit it directly. Keep the populated file outside the repository.

Each member table with a `type` is a complete connection. It does not inherit another provider's endpoint or key:

```toml
[members.research_lead]
type = "custom"
id = "my-provider"
base_url = "https://api.example.com/v1"
model = "your-model-id"
reasoning_effort = "high"
api_key_env = "MY_PROVIDER_API_KEY"
```

Set `MY_PROVIDER_API_KEY` in the environment that launches the backend. In PowerShell, for example:

```powershell
$env:MY_PROVIDER_API_KEY = 'your-key'
```

In a POSIX shell:

```sh
export MY_PROVIDER_API_KEY='your-key'
```

Enter only the variable name into the editor's environment-variable field. Restart an already running backend to pick up changed environment values. Windows shortcuts need the variable in their launching Windows session. Alternatively, use `api_key = "your-key"` in the local provider file or store the key through the editor.

The optional `[provider]` table supplies a shared default. A member table without `type` overrides only the default model or reasoning effort:

```toml
[provider]
type = "openai"
model = "your-account-model-id"
reasoning_effort = "high"

[members.theorist]
model = "your-theory-model-id"
reasoning_effort = "high"
```

Members not governed by the file use their per-project saved settings. Removing the file restores those settings. Member instructions and token controls remain editable in Team Settings.

Changes to the file apply to the next member turn; running turns retain their captured settings. Choose **Refresh settings** to see effective values. An invalid provider file blocks new model turns until repaired. The editor validates and saves atomically, and refuses to overwrite a file that changed after it was opened. Refresh and reapply your edit when a conflict appears. **Remove provider file** deletes that shared configuration.

Stored API keys are masked in the provider editor until revealed. They can be read through that editor, so use the local workbench on a trusted machine. The app does not put keys into research artifacts, run records, or logs.

### Optional Responses shim

The optional shim requires the [source installation](development.md#source-checkout) of Model Forge into the selected shared Python. The npm-only quickstart installs dependencies and bundled app files, so its separate terminal cannot import this Python module. After source installation, start the shim from any directory using that same executable.

```text
"$MF_PYTHON" -m model_forge_codex.shim --port 8780 --auth forward --base-url https://api.example.com/v4
```

In PowerShell, replace `"$MF_PYTHON"` with `& $env:MF_PYTHON`. Check the installation without contacting a provider using `-m model_forge_codex.shim --help` first.

Set `shim` as the provider ID and `http://127.0.0.1:8780/v1` as its base URL. With `--auth forward`, the shim forwards each member's configured key. The repository's [shim design](https://github.com/rqzhu-aide/model-forge-codex/blob/main/architecture/decisions/ADR-008-responses-shim.md) describes its supported scope and the older `shim.env` arrangement. A shim does not establish compatibility with every provider.

## Understand connection tests

**Test saved settings** checks effective saved settings. **Test these settings** checks the provider editor's unsaved draft. The result identifies which settings were tested and reports success, partial progress, or failure. A relevant settings change clears the previous result.

The test performs a bounded exchange of at most 45 seconds: connection, a model response, one tool round trip, and a final response. It uses an isolated temporary home, leaves research runs and documents untouched, and can consume provider tokens. A passed test checks this exchange, not the quality of future scientific work or access to every experiment dependency.

If a test fails, read the reached stage and credential-redacted failure in the app. Confirm the exact model, reasoning effort, API base URL, key source, and Windows sandbox setup before launching research.

For development without model calls, set `MF_CODEX_FAKE_BRIDGE=1` before starting the backend. The interface labels connection results as simulated. Fake output exercises the harness and does not perform research. Unset the variable before using a real connection.
