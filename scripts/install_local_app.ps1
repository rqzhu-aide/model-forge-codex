<#
.SYNOPSIS
Install a built Model Forge release using existing shared runtimes.
.DESCRIPTION
Copies application code into a new release directory, validates it, then switches
current.json. Saved research and provider settings are never copied or changed.
The installer does not start or stop the application. Earlier releases remain.
#>
[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'ModelForge'),
    [string]$PythonPath,
    [string]$ExperimentPythonPath,
    [string]$NodePath,
    [string]$DataRoot = (Join-Path $env:USERPROFILE '.model-forge-codex'),
    [ValidateRange(1024, 65535)][int]$Port = 8766,
    [switch]$StartAtLogon,
    [switch]$SkipShortcuts
)

$ErrorActionPreference = 'Stop'
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$installDirectory = [IO.Path]::GetFullPath($InstallRoot)
$previousConfiguration = $null
$currentPath = Join-Path $installDirectory 'current.json'
if (Test-Path -LiteralPath $currentPath -PathType Leaf) {
    $previousConfiguration = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json
    if (-not $PSBoundParameters.ContainsKey('DataRoot') -and $previousConfiguration.data_root) { $DataRoot = $previousConfiguration.data_root }
    if (-not $PSBoundParameters.ContainsKey('Port') -and $previousConfiguration.port) { $Port = [int]$previousConfiguration.port }
    if (-not $PythonPath -and $previousConfiguration.python_path) { $PythonPath = $previousConfiguration.python_path }
    if (-not $ExperimentPythonPath -and $previousConfiguration.experiment_python_path) { $ExperimentPythonPath = $previousConfiguration.experiment_python_path }
    if (-not $NodePath -and $previousConfiguration.node_path) { $NodePath = $previousConfiguration.node_path }
    if (-not $env:MF_SHARED_NODE_MODULES -and $previousConfiguration.shared_node_modules) { $env:MF_SHARED_NODE_MODULES = $previousConfiguration.shared_node_modules }
}
$dataDirectory = [IO.Path]::GetFullPath($DataRoot)
$utf8 = New-Object Text.UTF8Encoding($false)

function Resolve-SharedPython([string]$ExplicitPath) {
    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) { throw "Python executable not found: $ExplicitPath. Set -PythonPath to an installed shared python.exe." }
        return [IO.Path]::GetFullPath($ExplicitPath)
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') { return $command.Source }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $resolved = & $launcher.Source -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolved -and (Test-Path -LiteralPath ([string]$resolved) -PathType Leaf)) { return [string]$resolved }
    }
    foreach ($relative in @('Python', 'Programs/Python')) {
        $pythonDirectory = Join-Path $env:LOCALAPPDATA $relative
        if (Test-Path -LiteralPath $pythonDirectory -PathType Container) {
            $candidate = Get-ChildItem -LiteralPath $pythonDirectory -Directory | Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName 'python.exe' } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
            if ($candidate) { return $candidate }
        }
    }
    throw 'Shared Python 3.11+ was not found. Set -PythonPath to an existing user-wide or machine-wide python.exe.'
}

function Resolve-SharedNode([string]$ExplicitPath) {
    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath -PathType Leaf)) { throw "Node executable not found: $ExplicitPath. Set -NodePath to the installed shared node.exe." }
        return [IO.Path]::GetFullPath($ExplicitPath)
    }
    $command = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($directory in @($env:ProgramFiles, $env:LOCALAPPDATA)) {
        if ($directory) {
            $candidate = Join-Path $directory 'nodejs/node.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
    }
    throw 'Shared Node.js was not found. Set -NodePath to an existing user-wide or machine-wide node.exe.'
}

function Invoke-ReleaseCheck([string]$AppRoot, [string]$PythonExecutable, [string]$NodeExecutable) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $report = & $PythonExecutable -B (Join-Path $PSScriptRoot 'validate_local_install.py') --app-root $AppRoot --node-path $NodeExecutable 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    $text = ($report | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($code -ne 0) { throw $text }
    return $text | ConvertFrom-Json
}

function Resolve-PhysicalPath([string]$Path, [string]$PythonExecutable) {
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $report = & $PythonExecutable -B -c 'import json, sys; from pathlib import Path; print(json.dumps(str(Path(sys.argv[1]).expanduser().resolve())))' $Path 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    $text = ($report | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    if ($code -ne 0) { throw "Cannot resolve the physical installation path: $text" }
    return $text | ConvertFrom-Json
}

function Copy-ReleaseTree([string]$From, [string]$To) {
    [void][IO.Directory]::CreateDirectory($To)
    foreach ($entry in Get-ChildItem -LiteralPath $From -Force) {
        if ($entry.Name -in @('__pycache__', 'node_modules', '.pytest_cache', '.vite', '.git', '.codex', '.agents') -or $entry.Name -like '*.egg-info' -or $entry.Name -like '*.pyc' -or $entry.Name -like '*.pyo') { continue }
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Release content must be a regular file or directory: $($entry.FullName)" }
        $destination = Join-Path $To $entry.Name
        if ($entry.PSIsContainer) { Copy-ReleaseTree $entry.FullName $destination }
        else { Copy-Item -LiteralPath $entry.FullName -Destination $destination }
    }
}

function Write-AtomicText([string]$Path, [string]$Text) {
    $temporary = $Path + '.next-' + [Guid]::NewGuid().ToString('N')
    [IO.File]::WriteAllText($temporary, $Text, $utf8)
    if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary, $Path, [System.Management.Automation.Language.NullString]::Value) }
    else { [IO.File]::Move($temporary, $Path) }
}

function New-AppShortcut([string]$Path, [string]$Action, [string]$Description) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + (Join-Path $installDirectory 'ModelForge.ps1') + '" ' + $Action + ' -Shortcut'
    $shortcut.WorkingDirectory = $installDirectory
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 7
    $shortcut.Save()
}

if ($env:OS -ne 'Windows_NT') { throw 'This installer creates Windows desktop shortcuts. Use it on Windows.' }
if ($SkipShortcuts -and $StartAtLogon) { throw '-StartAtLogon cannot be combined with -SkipShortcuts.' }
foreach ($tree in @('src', 'contracts', 'web')) {
    $copiedRoot = [IO.Path]::GetFullPath((Join-Path $sourceRoot $tree)).TrimEnd('\')
    if ($installDirectory.Equals($copiedRoot, [StringComparison]::OrdinalIgnoreCase) -or $installDirectory.StartsWith($copiedRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "InstallRoot cannot be inside the source tree being copied: $copiedRoot"
    }
}
$pythonExecutable = Resolve-SharedPython $PythonPath
$experimentPython = if ($ExperimentPythonPath) { Resolve-SharedPython $ExperimentPythonPath } elseif ($env:MF_P4_PYTHON) { Resolve-SharedPython $env:MF_P4_PYTHON } else { $null }
$nodeExecutable = Resolve-SharedNode $NodePath
Write-Host 'Checking the built app, workflow catalog, and shared runtimes...'
$validated = Invoke-ReleaseCheck $sourceRoot $pythonExecutable $nodeExecutable
$pythonExecutable = $validated.python_path
$nodeExecutable = $validated.node_path

# Shortcuts start from the release directory. Resolve user paths now, while
# their original terminal directory still gives relative paths their meaning.
foreach ($setting in @('MF_CODEX_PROVIDER_CONFIG', 'CODEX_HOME', 'MF_SHARED_NODE_MODULES')) {
    $settingValue = [Environment]::GetEnvironmentVariable($setting, 'Process')
    if ($settingValue) { [Environment]::SetEnvironmentVariable($setting, (Resolve-PhysicalPath $settingValue $pythonExecutable), 'Process') }
}

# Packaged terminals can redirect AppData writes into their private cache.
# Resolve only after creating the directory, then pin that physical location in
# the launcher and shortcuts so ordinary desktop processes see the same files.
[void][IO.Directory]::CreateDirectory($installDirectory)
$installDirectory = Resolve-PhysicalPath $installDirectory $pythonExecutable
$dataDirectory = Resolve-PhysicalPath $dataDirectory $pythonExecutable

$releaseId = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
$releasesDirectory = Join-Path $installDirectory 'releases'
$stagingDirectory = [IO.Path]::GetFullPath((Join-Path $releasesDirectory ('.staging-' + $releaseId)))
$releaseDirectory = [IO.Path]::GetFullPath((Join-Path $releasesDirectory $releaseId))
[void][IO.Directory]::CreateDirectory($stagingDirectory)
foreach ($tree in @('src', 'contracts', 'web/src', 'web/scripts', 'web/dist')) {
    Copy-ReleaseTree (Join-Path $sourceRoot $tree) (Join-Path $stagingDirectory $tree)
}
if (Test-Path -LiteralPath (Join-Path $sourceRoot 'web/runtime') -PathType Container) {
    Copy-ReleaseTree (Join-Path $sourceRoot 'web/runtime') (Join-Path $stagingDirectory 'web/runtime')
}
foreach ($file in @('pyproject.toml', 'web/package.json')) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $file) -Destination (Join-Path $stagingDirectory $file)
}
$installedAt = [DateTime]::UtcNow.ToString('o')
$metadata = @{ release_id = $releaseId; installed_at = $installedAt; catalog_version = $validated.catalog_version }
[IO.File]::WriteAllText((Join-Path $stagingDirectory 'local-release.json'), ($metadata | ConvertTo-Json), $utf8)
$validated = Invoke-ReleaseCheck $stagingDirectory $pythonExecutable $nodeExecutable
$stagingDirectory = $validated.app_root

# Both resolved paths must stay within the explicitly chosen releases directory.
$releasePrefix = [IO.Path]::GetFullPath($releasesDirectory).TrimEnd('\') + '\'
if (-not $stagingDirectory.StartsWith($releasePrefix, [StringComparison]::OrdinalIgnoreCase) -or -not $releaseDirectory.StartsWith($releasePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The staged release paths are outside the installation directory.'
}
Move-Item -LiteralPath $stagingDirectory -Destination $releaseDirectory
$releaseDirectory = Resolve-PhysicalPath $releaseDirectory $pythonExecutable
Write-AtomicText (Join-Path $installDirectory 'ModelForge.ps1') ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'run_local_app.ps1')))
$configuration = [ordered]@{
    schema_version = 1; release_id = $releaseId; installed_at = $installedAt; app_root = $releaseDirectory
    python_path = $validated.python_path; node_path = $validated.node_path; shared_node_modules = $validated.shared_node_modules
    experiment_python_path = $experimentPython
    data_root = $dataDirectory; port = $Port
    provider_config_path = $(if ($env:MF_CODEX_PROVIDER_CONFIG) { $env:MF_CODEX_PROVIDER_CONFIG } elseif ($previousConfiguration) { $previousConfiguration.provider_config_path } else { $null })
    codex_home = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } elseif ($previousConfiguration) { $previousConfiguration.codex_home } else { $null })
    codex_bin = $(if ($env:MF_CODEX_BIN) { $env:MF_CODEX_BIN } elseif ($previousConfiguration) { $previousConfiguration.codex_bin } else { $null })
}
Write-AtomicText (Join-Path $installDirectory 'current.json') ($configuration | ConvertTo-Json)

$shortcutDirectory = $null
$startupShortcut = $null
if (-not $SkipShortcuts) {
    $shortcutDirectory = Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Model Forge'
    [void][IO.Directory]::CreateDirectory($shortcutDirectory)
    $shortcutDirectory = Resolve-PhysicalPath $shortcutDirectory $pythonExecutable
    New-AppShortcut (Join-Path $shortcutDirectory 'Open Model Forge.lnk') 'open' 'Open Model Forge, starting its local service if needed.'
    New-AppShortcut (Join-Path $shortcutDirectory 'Start Model Forge.lnk') 'start' 'Start the local Model Forge service without opening a browser.'
    New-AppShortcut (Join-Path $shortcutDirectory 'Stop Model Forge.lnk') 'stop' 'Stop Model Forge when no research runs are active.'
    if ($StartAtLogon) {
        $startupDirectory = Resolve-PhysicalPath ([Environment]::GetFolderPath('Startup')) $pythonExecutable
        $startupShortcut = Join-Path $startupDirectory 'Start Model Forge.lnk'
        New-AppShortcut $startupShortcut 'start' 'Start the local Model Forge service at Windows sign-in.'
        $startupShortcut = Resolve-PhysicalPath $startupShortcut $pythonExecutable
    }
}
Write-Host 'Installed. Existing services were not restarted; saved research and provider settings were not changed.'
[ordered]@{ install_root = $installDirectory; release_id = $releaseId; app_root = $releaseDirectory; data_root = $dataDirectory; port = $Port; shortcuts = $shortcutDirectory; startup_shortcut = $startupShortcut; start_at_logon_requested = [bool]$StartAtLogon } | ConvertTo-Json
