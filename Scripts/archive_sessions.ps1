param(
    [string]$SessionsDir = "Data/sessions",
    [string]$ArchiveDir = "Data/sessions_archive",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$sessionsPath = Join-Path $root $SessionsDir
$archivePath = Join-Path $root $ArchiveDir

if (-not (Test-Path $sessionsPath)) {
    Write-Host "No sessions directory found: $sessionsPath"
    exit 0
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$target = Join-Path $archivePath $stamp
$files = Get-ChildItem -Path $sessionsPath -Filter "session_*.json" -File

if (-not $files) {
    Write-Host "No session JSON files found to archive."
    exit 0
}

Write-Host "Found $($files.Count) session file(s)."
Write-Host "Archive target: $target"

if (-not $Apply) {
    Write-Host "Dry run only. Re-run with -Apply to move files."
    $files | ForEach-Object { Write-Host "Would archive: $($_.Name)" }
    exit 0
}

New-Item -ItemType Directory -Force -Path $target | Out-Null
foreach ($file in $files) {
    Move-Item -LiteralPath $file.FullName -Destination (Join-Path $target $file.Name)
}

Write-Host "Archived $($files.Count) session file(s) to $target"
