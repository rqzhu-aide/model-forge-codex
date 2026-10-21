# Stable desktop entry point. The installed copy is named ModelForge.ps1.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'open', 'status', 'stop')]
    [string]$Action = 'open',
    [switch]$CancelActive,
    [switch]$Shortcut
)

$ErrorActionPreference = 'Stop'
$exitCode = 1
try {
    $configurationPath = Join-Path $PSScriptRoot 'current.json'
    if (-not (Test-Path -LiteralPath $configurationPath -PathType Leaf)) {
        throw 'Model Forge has no installed release. Run scripts/install_local_app.ps1 from the source checkout.'
    }
    $configuration = Get-Content -LiteralPath $configurationPath -Raw | ConvertFrom-Json
    $appRoot = [IO.Path]::GetFullPath($configuration.app_root)
    $sourceRoot = Join-Path $appRoot 'src'
    if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot 'model_forge_codex/local_app.py') -PathType Leaf)) {
        throw 'The selected Model Forge release is incomplete. Run the installer again; saved research is separate from the application.'
    }
    if ($CancelActive -and $Action -ne 'stop') { throw '-CancelActive is only available for the stop command.' }
    $env:PYTHONPATH = $sourceRoot
    $env:PATH = (Split-Path -Parent $configuration.node_path) + [IO.Path]::PathSeparator + $env:PATH
    $env:MF_SHARED_NODE_MODULES = $configuration.shared_node_modules
    if ($configuration.experiment_python_path) { $env:MF_P4_PYTHON = $configuration.experiment_python_path }
    if ($configuration.provider_config_path) { $env:MF_CODEX_PROVIDER_CONFIG = $configuration.provider_config_path }
    if ($configuration.codex_bin) { $env:MF_CODEX_BIN = $configuration.codex_bin }
    if ($configuration.codex_home) { $env:CODEX_HOME = $configuration.codex_home }
    $arguments = @('-m', 'model_forge_codex.local_app', $Action, '--data-root', $configuration.data_root, '--port', [string]$configuration.port)
    if ($CancelActive) { $arguments += '--cancel-active' }
    Push-Location -LiteralPath $appRoot
    try {
        # Native stderr must be captured even in Windows PowerShell 5.1.
        $ErrorActionPreference = 'Continue'
        $output = & $configuration.python_path @arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = 'Stop'
        Pop-Location
    }
    $message = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($message) { Write-Output $message }
    if ($exitCode -ne 0) { throw $message }
} catch {
    $message = $_.Exception.Message
    $logPath = Join-Path $PSScriptRoot 'launcher-error.log'
    Add-Content -LiteralPath $logPath -Value ((Get-Date -Format o) + ' ' + $Action + ': ' + $message) -Encoding UTF8
    if ($Shortcut) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show($message, 'Model Forge', 'OK', 'Warning')
    } else {
        Write-Error $message -ErrorAction Continue
    }
    if ($exitCode -eq 0) { $exitCode = 1 }
}
exit $exitCode
