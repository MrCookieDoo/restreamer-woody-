[CmdletBinding()]
param([string]$Container = 'woody-test-studio-1')
$ErrorActionPreference = 'Stop'
try {
    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is niet gevonden. Start Docker Desktop.' }
    $source = Join-Path (Split-Path -Parent $PSScriptRoot) 'services/studio/woody/diagnostics.py'
    Get-Content -LiteralPath $source -Raw | & docker exec -i $Container python -
    if ($LASTEXITCODE -ne 0) { throw 'Uitlezen mislukt. Controleer of de opgegeven Studio-container draait.' }
    Write-Host 'Alleen status en tellers uitgelezen. Containers en instellingen zijn niet gewijzigd.'
}
catch { Write-Error -ErrorAction Continue $_.Exception.Message; exit 1 }
