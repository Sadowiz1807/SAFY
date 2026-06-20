param([switch]$Wait)
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot '..\Docker\docker-compose.test-databases.yml'
docker compose -f $compose up -d
if ($Wait) { docker compose -f $compose ps }
