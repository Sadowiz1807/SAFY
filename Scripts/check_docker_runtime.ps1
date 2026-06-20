param(
  [switch]$RequireSqlServerOdbc,
  [switch]$RequireOracleImage
)

$ErrorActionPreference = "Stop"
function Block($Code, $Message) {
  Write-Host "${Code}: $Message"
  exit 2
}

try {
  docker info *> $null
} catch {
  Block "BLOCKED_DOCKER_ENGINE_NOT_RUNNING" "Docker Desktop/engine is not running or docker is unavailable."
}

if ($RequireSqlServerOdbc) {
  $drivers = @()
  try { $drivers = Get-OdbcDriver | ForEach-Object { $_.Name } } catch { $drivers = @() }
  if (-not ($drivers | Where-Object { $_ -like "*ODBC Driver 18 for SQL Server*" })) {
    Block "SQLSERVER_ODBC_DRIVER_MISSING" "Install Microsoft ODBC Driver 18 for SQL Server before running SQL Server integration tests."
  }
}

if ($RequireOracleImage) {
  $image = docker image inspect gvenzl/oracle-free:23-slim 2>$null
  if (-not $image) {
    Write-Host "BLOCKED_ORACLE_VALIDATION: Oracle image is not present locally; start script can attempt docker pull if network is available."
    exit 3
  }
}

Write-Host "DOCKER_RUNTIME_CHECK_OK"
