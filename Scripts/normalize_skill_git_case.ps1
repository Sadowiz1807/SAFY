$ErrorActionPreference = "Stop"

$repo = (git rev-parse --show-toplevel 2>$null)
if (-not $repo) {
    throw "Run this script inside the SAFY Git repository."
}
Set-Location $repo

$canonicalSkills = @(
    "command_router",
    "create_database",
    "database_context",
    "database_switch",
    "execute_box",
    "execute_query",
    "query_explain",
    "query_guard",
    "query_repair",
    "schema_graph",
    "text_to_sql"
)

foreach ($name in $canonicalSkills) {
    $skillFile = Join-Path (Join-Path "Skills" $name) "SKILL.md"
    if (-not (Test-Path $skillFile)) {
        throw "Missing canonical skill file: $skillFile"
    }
}

$previousIgnoreCase = (git config --get core.ignorecase 2>$null)
if (-not $previousIgnoreCase) { $previousIgnoreCase = "true" }

try {
    # The working tree already contains canonical lowercase directories and
    # uppercase SKILL.md filenames. Temporarily disable Git's case folding so
    # `git add -A` records the case-only renames in the index on Windows.
    git config core.ignorecase false
    git add -A -- Skills
    if ($LASTEXITCODE -ne 0) {
        throw "git add failed while normalizing skill paths."
    }
}
finally {
    git config core.ignorecase $previousIgnoreCase
}

$legacy = git ls-files -- Skills | Where-Object {
    $_ -match '^Skills/[A-Z]' -or $_ -match '/Skill\.md$' -or $_ -match '/skill\.md$'
}
if ($legacy) {
    Write-Host "Legacy paths remain in the Git index:" -ForegroundColor Red
    $legacy | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Skill path casing is canonical in the Git index." -ForegroundColor Green
git diff --cached --name-status -- Skills
Write-Host "Next: python Scripts/validate_skills.py" -ForegroundColor Cyan
