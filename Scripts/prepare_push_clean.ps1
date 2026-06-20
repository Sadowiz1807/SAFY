$ErrorActionPreference = "Stop"

$Root = Resolve-Path "."
$BackupRoot = Join-Path $Root ("_push_clean_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss"))

Write-Host "SAFY push clean started at $Root"
Write-Host "Backup folder: $BackupRoot"

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null

function Backup-And-Remove($Path) {
    $Full = Join-Path $Root $Path
    if (Test-Path $Full) {
        $Target = Join-Path $BackupRoot $Path
        $TargetDir = Split-Path $Target -Parent
        New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
        Copy-Item $Full $Target -Recurse -Force
        Remove-Item $Full -Recurse -Force
        Write-Host "Removed local runtime path: $Path"
    }
}

function Ensure-GitignoreLine($Line) {
    $Gitignore = Join-Path $Root ".gitignore"
    if (-not (Test-Path $Gitignore)) {
        New-Item -ItemType File -Force -Path $Gitignore | Out-Null
    }
    $Content = Get-Content $Gitignore -ErrorAction SilentlyContinue
    if ($Content -notcontains $Line) {
        Add-Content $Gitignore $Line
        Write-Host "Added .gitignore rule: $Line"
    }
}

$Rules = @(
    ".env",
    ".env.*",
    "!.env.template",
    "!.env.local.example",
    "Docker/.env",
    "!Docker/.env.example",
    "Data/secrets/",
    "Data/sessions/",
    "Data/sandboxes/",
    "Data/SchemaGraph/*",
    "!Data/SchemaGraph/.gitkeep",
    "Data/**/*.db",
    "Data/**/*.sqlite",
    "Data/**/*.sqlite3",
    "Data/**/*.local.json",
    "Data/Database_management/database_profiles.json",
    "Data/safy_profiles.json",
    "Data/model_profiles/model_profiles.json",
    "Sandbox/workspaces/",
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    "gateway_task.log",
    "*.log",
    "_push_clean_backup_*/"
)

foreach ($Rule in $Rules) { Ensure-GitignoreLine $Rule }

$RemovePaths = @(
    ".env",
    ".env.local",
    ".env.production",
    "Docker/.env",
    "Data/secrets",
    "Data/sessions",
    "Data/sandboxes",
    "Data/SchemaGraph",
    "Sandbox/workspaces",
    "Data/safy_audit.db",
    "Data/safy_runtime.db",
    "Data/Database_management/database_profiles.local.json",
    "Data/safy_profiles.local.json",
    "gateway_task.log"
)

foreach ($Path in $RemovePaths) { Backup-And-Remove $Path }

$SchemaGraphKeep = Join-Path $Root "Data/SchemaGraph/.gitkeep"
New-Item -ItemType Directory -Force -Path (Split-Path $SchemaGraphKeep -Parent) | Out-Null
if (-not (Test-Path $SchemaGraphKeep)) { New-Item -ItemType File -Force -Path $SchemaGraphKeep | Out-Null }

$ProfilePath = Join-Path $Root "Data/Database_management/database_profiles.json"
New-Item -ItemType Directory -Force -Path (Split-Path $ProfilePath -Parent) | Out-Null
"[]" | Out-File -Encoding UTF8 $ProfilePath

$SafyProfilesPath = Join-Path $Root "Data/safy_profiles.json"
New-Item -ItemType Directory -Force -Path (Split-Path $SafyProfilesPath -Parent) | Out-Null
"[]" | Out-File -Encoding UTF8 $SafyProfilesPath

$ModelProfilesPath = Join-Path $Root "Data/model_profiles/model_profiles.json"
New-Item -ItemType Directory -Force -Path (Split-Path $ModelProfilesPath -Parent) | Out-Null
"[]" | Out-File -Encoding UTF8 $ModelProfilesPath

$GitRemoveCached = @(
    ".env",
    ".env.local",
    ".env.production",
    "Docker/.env",
    "Data/secrets",
    "Data/sessions",
    "Data/sandboxes",
    "Data/SchemaGraph",
    "Sandbox/workspaces",
    "Data/safy_audit.db",
    "Data/safy_runtime.db",
    "Data/Database_management/database_profiles.local.json",
    "Data/safy_profiles.local.json"
)

foreach ($Path in $GitRemoveCached) {
    git rm --cached -r --ignore-unmatch $Path | Out-Null
}

git add Data/SchemaGraph/.gitkeep | Out-Null

Write-Host "`nTracked suspicious files:"
git ls-files | Select-String -Pattern "\.env|secret|token|key|password|\.db|\.sqlite|\.local\.json|sessions|sandboxes|workspaces" -CaseSensitive:$false

Write-Host "`nRunning gitleaks if available..."
$Gitleaks = Get-Command gitleaks -ErrorAction SilentlyContinue
if ($null -ne $Gitleaks) {
    gitleaks detect --source . --verbose
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`nGitleaks found leaks. Do NOT push."
        exit $LASTEXITCODE
    }
} else {
    Write-Host "WARNING: gitleaks not found in PATH. Run it manually before push."
}

Write-Host "`nPush clean completed. Review git status before commit:"
git status --short
