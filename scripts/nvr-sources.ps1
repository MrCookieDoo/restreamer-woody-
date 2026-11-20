[CmdletBinding()]
param(
    [string]$Container = 'Woody',
    [string]$BaseUrl = 'http://host.docker.internal:8080',
    [string]$DatabasePath = '/core/config/db.json'
)
$ErrorActionPreference = 'Stop'

function Get-NvrProperty {
    param($Value, [string]$Name)
    if ($null -eq $Value) { return $null }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function ConvertFrom-NvrDatabase {
    param([string]$Json, [string]$BaseUrl)
    $base = $null
    if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$base) -or $base.Scheme -notin @('http', 'https') -or $base.UserInfo -or $base.Query -or $base.Fragment) {
        throw 'Gebruik een HTTP(S)-basisadres zonder wachtwoord, query of fragment.'
    }
    try { $database = $Json | ConvertFrom-Json }
    catch { throw 'De Core-database kon niet worden gelezen. De inhoud wordt niet afgedrukt omdat er bronwachtwoorden in kunnen staan.' }
    $processes = Get-NvrProperty $database 'process'
    $allMetadata = Get-NvrProperty (Get-NvrProperty $database 'metadata') 'process'
    if ($null -eq $processes -or $null -eq $allMetadata) { throw 'Geen ondersteunde Restreamer Core-database gevonden.' }
    $baseAddress = $BaseUrl.TrimEnd('/')
    foreach ($property in $processes.PSObject.Properties) {
        $processId = $property.Name
        if ($processId -notmatch '^restreamer-ui:ingest:([a-f0-9-]{36})$') { continue }
        $channelId = $Matches[1]
        $meta = Get-NvrProperty (Get-NvrProperty $allMetadata $processId) 'restreamer-ui'
        if ($null -eq $meta) { continue }
        $profiles = @(Get-NvrProperty $meta 'profiles')
        $sourceIndex = 0
        if ($profiles.Count -gt 0 -and $null -ne $profiles[0]) {
            $configured = Get-NvrProperty (Get-NvrProperty $profiles[0] 'video') 'source'
            if ($null -ne $configured -and -not [int]::TryParse([string]$configured, [ref]$sourceIndex)) { continue }
        }
        $sources = @(Get-NvrProperty $meta 'sources')
        if ($sourceIndex -lt 0 -or $sourceIndex -ge $sources.Count) { continue }
        $source = $sources[$sourceIndex]
        if ((Get-NvrProperty $source 'type') -ne 'network') { continue }
        $settings = Get-NvrProperty $source 'settings'
        if ((Get-NvrProperty $settings 'mode') -eq 'push') { continue }
        $inputs = @(Get-NvrProperty $source 'inputs')
        $address = Get-NvrProperty $settings 'address'
        if ($inputs.Count -gt 0 -and $null -ne $inputs[0]) { $address = Get-NvrProperty $inputs[0] 'address' }
        $uri = $null
        if (-not [Uri]::TryCreate([string]$address, [UriKind]::Absolute, [ref]$uri)) { continue }
        if ($uri.Scheme -notin @('http', 'https') -or -not $uri.IsLoopback -or $uri.Port -lt 18550 -or $uri.Port -gt 18565) { continue }
        $number = $uri.Port - 18550
        if ($uri.AbsolutePath -ne "/channel$number.ts") { continue }
        $storage = Get-NvrProperty (Get-NvrProperty (Get-NvrProperty $meta 'control') 'hls') 'storage'
        $prefix = 'memfs/'
        if ($storage -and $storage -ne 'memfs') {
            if ($storage -ne 'diskfs') { throw 'Een kanaal heeft een onbekende HLS-opslaginstelling.' }
            $prefix = ''
        }
        [pscustomobject]@{ NVR = $number + 1; Bronadres = "$baseAddress/$prefix$channelId.m3u8" }
    }
}

function Read-NvrDatabase {
    param([string]$Container, [string]$DatabasePath)
    $output = @(& docker exec $Container cat $DatabasePath)
    if ($LASTEXITCODE -ne 0) { throw 'De bestaande Core-database kon niet worden uitgelezen. Controleer containernaam en DatabasePath.' }
    return $output -join "`n"
}

function Show-NvrSources {
    param([string]$Container, [string]$BaseUrl, [string]$DatabasePath)
    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is niet gevonden. Start Docker Desktop.' }
    $raw = Read-NvrDatabase $Container $DatabasePath
    $rows = @(ConvertFrom-NvrDatabase $raw $BaseUrl | Sort-Object NVR, Bronadres)
    $raw = $null
    if ($rows.Count -eq 0) { throw 'Geen NVR-kanalen met localhost-poorten 18550-18565 gevonden in deze database.' }
    Write-Host 'HLS-bronadressen voor de nieuwe Restreamer/Studio:'
    foreach ($row in $rows) {
        Write-Host "`nNVR-kanaal $($row.NVR)"
        Write-Output $row.Bronadres
    }
    Write-Host "`nDe oude containers en broninstellingen zijn niet gewijzigd. Gebruik deze HLS-adressen als netwerkbron in de nieuwe Restreamer."
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Show-NvrSources $Container $BaseUrl $DatabasePath }
    catch { Write-Error -ErrorAction Continue $_.Exception.Message; exit 1 }
}
