param(
    [string]$RepoRoot = "",
    [switch]$FetchOrigin,
    [switch]$RunDashboardBuild,
    [switch]$RunPythonChecks,
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}

if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
    throw "Repo root does not contain .git: $RepoRoot"
}

Set-Location $RepoRoot

function Invoke-CheckedCommand {
    param(
        [string]$Label,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "== $Label ==" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Write-Host "Seen-It-First repo checkpoint" -ForegroundColor Green
Write-Host "Repo root: $RepoRoot"
Write-Host "Timestamp: $(Get-Date -Format s)"

Invoke-CheckedCommand "Git status" { git status --short --branch }
Invoke-CheckedCommand "Git branch" { git branch --show-current }

if ($FetchOrigin) {
    Invoke-CheckedCommand "Git fetch origin" { git fetch origin }
}

if ($RunDashboardBuild) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm is not available on PATH"
    }

    Push-Location (Join-Path $RepoRoot "dashboard")
    try {
        Invoke-CheckedCommand "Dashboard build" { npm run build }
    }
    finally {
        Pop-Location
    }
}

if ($RunPythonChecks) {
    if (-not (Get-Command $PythonExe -ErrorAction SilentlyContinue)) {
        throw "Python executable not found: $PythonExe"
    }

    & $PythonExe -c "import yaml" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Missing Python dependency 'pyyaml'. Install it with: $PythonExe -m pip install pyyaml"
    }

    Invoke-CheckedCommand "Config validation" { & $PythonExe scripts/validate_config.py }
    Invoke-CheckedCommand "Selected Python tests" {
        & $PythonExe -m unittest `
            tests.test_validate_config `
            tests.test_preflight_check `
            tests.test_prepare_jetson_runtime `
            tests.test_phase3_ocr_training `
            tests.test_phase3_plate_training -v
    }
}

Write-Host ""
Write-Host "Checkpoint complete." -ForegroundColor Green
Write-Host "Recommended next steps:"
Write-Host "1. Review git diff"
Write-Host "2. Commit the verified slice"
Write-Host "3. Push the branch to GitHub"
