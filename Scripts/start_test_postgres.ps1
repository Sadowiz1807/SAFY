$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot '..\Docker\docker-compose.test-databases.yml'
docker compose -f $compose up -d runtime_test-postgres
