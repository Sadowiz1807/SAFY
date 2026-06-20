param(
  [switch]$Wait,
  [switch]$SqlServerOnly,
  [switch]$OracleOnly
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$compose = Join-Path $root "Docker\docker-compose.database-services.yml"
$envFile = Join-Path $root "Docker\.env.database-services"
$check = Join-Path $PSScriptRoot "check_docker_runtime.ps1"
$sqlSeed = "/database-services-init/01_seed_readonly.sql"
$sqlContainer = "safy-database-services-sqlserver"

& $check -RequireSqlServerOdbc
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$services = @()
if (-not $OracleOnly) { $services += "database-services-sqlserver" }
if (-not $SqlServerOnly) { $services += "database-services-oracle" }

$composeArgs = @("compose", "-f", $compose)
if (Test-Path $envFile) { $composeArgs += @("--env-file", $envFile) }
$composeArgs += @("up", "-d") + $services
& docker @composeArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

function Wait-Healthy($ContainerName, [int]$Retries) {
  for ($i = 1; $i -le $Retries; $i++) {
    $status = (& docker inspect -f "{{.State.Health.Status}}" $ContainerName 2>$null)
    if ($LASTEXITCODE -eq 0 -and $status -eq "healthy") { return $true }
    Start-Sleep -Seconds 2
  }
  return $false
}

function Get-SqlcmdPath {
  $path = (& docker exec $sqlContainer /bin/bash -lc 'if [ -x /opt/mssql-tools18/bin/sqlcmd ]; then echo /opt/mssql-tools18/bin/sqlcmd; elif [ -x /opt/mssql-tools/bin/sqlcmd ]; then echo /opt/mssql-tools/bin/sqlcmd; else exit 88; fi' 2>$null)
  if ($LASTEXITCODE -eq 88 -or -not $path) {
    Write-Host "BLOCKED_SQLSERVER_SQLCMD_MISSING"
    exit 88
  }
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  return $path.Trim()
}

function Invoke-SqlServerSeed {
  $sqlcmd = Get-SqlcmdPath
  $saPassword = (& docker exec $sqlContainer printenv SA_PASSWORD)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($saPassword)) { exit 1 }
  $saPassword = $saPassword.Trim()

  $seedSqlcmdArgs = @("-S", "localhost", "-U", "sa", "-P", $saPassword, "-b", "-i", $sqlSeed)
  $smokeSqlcmdArgs = @("-S", "localhost", "-U", "safy_readonly", "-P", "safy_ro_database_services_fake_123!", "-d", "safy_database_services", "-b", "-Q", "SELECT TOP 5 * FROM dbo.database_services_items;")
  if ($sqlcmd -like "*tools18*") {
    $seedSqlcmdArgs = @("-S", "localhost", "-U", "sa", "-P", $saPassword, "-C", "-b", "-i", $sqlSeed)
    $smokeSqlcmdArgs = @("-S", "localhost", "-U", "safy_readonly", "-P", "safy_ro_database_services_fake_123!", "-C", "-d", "safy_database_services", "-b", "-Q", "SELECT TOP 5 * FROM dbo.database_services_items;")
  }

  Write-Host "Running SQL Server Database services seed in $sqlContainer with $sqlcmd"
  $dockerSeedArgs = @("exec", $sqlContainer, $sqlcmd) + $seedSqlcmdArgs
  & docker @dockerSeedArgs
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

  Write-Host "Running SQL Server Database services readonly smoke test"
  $dockerSmokeArgs = @("exec", $sqlContainer, $sqlcmd) + $smokeSqlcmdArgs
  & docker @dockerSmokeArgs
  if ($LASTEXITCODE -ne 0) {
    Write-Host "BLOCKED_SQLSERVER_LOGIN_MAPPING"
    exit $LASTEXITCODE
  }
}

if (-not $OracleOnly) {
  if ($Wait) {
    if (-not (Wait-Healthy $sqlContainer 90)) {
      Write-Host "BLOCKED_SQLSERVER_VALIDATION: $sqlContainer did not become healthy"
      exit 1
    }
  }
  Invoke-SqlServerSeed
}

if ($Wait -and -not $SqlServerOnly) {
  if (-not (Wait-Healthy "safy-database-services-oracle" 120)) {
    Write-Host "BLOCKED_ORACLE_VALIDATION: safy-database-services-oracle did not become healthy"
    exit 1
  }
}

& docker compose -f $compose ps
Write-Host "Database services database containers requested. SQL Server seed and readonly smoke completed when SQL Server was selected."
