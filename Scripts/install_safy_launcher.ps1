param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

Set-Location $RepoRoot
python -m pip install -e .

$scriptDir = Split-Path (Get-Command safy -ErrorAction SilentlyContinue).Source -ErrorAction SilentlyContinue
if (-not $scriptDir) {
    $pythonExe = (Get-Command python).Source
    $scriptDir = Join-Path (Split-Path $pythonExe) 'Scripts'
}

Write-Host "SAFY editable install complete."
Write-Host "If 'safy' is not recognized from C:\Users\ASUS, add this directory to PATH:"
Write-Host "  $scriptDir"
Write-Host "Current-session PATH command:"
Write-Host "  `$env:Path = '$scriptDir;' + `$env:Path"
