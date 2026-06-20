param([switch]$Volumes)
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot '..\Docker\docker-compose.test-databases.yml'
$args = @('compose', '-f', $compose, 'down')
if ($Volumes) { $args += '--volumes' }
& docker @args
