[CmdletBinding()]
param(
    [string]$Container = 'Woody',
    [string]$BaseUrl = 'http://host.docker.internal:8080',
    [string]$DatabasePath = '/core/config/db.json',
    [switch]$NoCheck
)
$ErrorActionPreference = 'Stop'

function Get-NvrProperty {
    param($Value, [string]$Name)
    if ($null -eq $Value) { return $null }
    $property = $Value.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $null
}

function Get-NvrHlsPaths {
    param($Config, [string]$BaseUrl)
    $urls = New-Object System.Collections.Generic.List[string]
    foreach ($output in @(Get-NvrProperty $Config 'output')) {
        $address = [string](Get-NvrProperty $output 'address')
        $options = @(Get-NvrProperty $output 'options')
        $master = ''
        for ($index = 0; $index -lt $options.Count - 1; $index++) {
            if ($options[$index] -eq '-master_pl_name') { $master = [string]$options[$index + 1] }
        }
        foreach ($match in [regex]::Matches($address, '\{(memfs|diskfs)(?:\^:)?\}(/[^\[\]|:?\r\n]*?\.m3u8)')) {
            $storage = $match.Groups[1].Value
            $path = $match.Groups[2].Value.Replace('{outputid}', [string](Get-NvrProperty $output 'id'))
            if ($path -match '[{}]') { continue }
            $before = $address.Substring(0, $match.Index)
            $teeMaster = [regex]::Match(($before -split '\|')[-1], '(?:^|:)master_pl_name=([^:\]\|]+)')
            $chosenMaster = $master
            if ($teeMaster.Success) { $chosenMaster = $teeMaster.Groups[1].Value }
            $prefix = ''
            if ($storage -eq 'memfs') { $prefix = '/memfs' }
            if ($chosenMaster) {
                $directory = $path.Substring(0, $path.LastIndexOf('/') + 1)
                $urls.Add($BaseUrl.TrimEnd('/') + $prefix + $directory + $chosenMaster)
            }
            $urls.Add($BaseUrl.TrimEnd('/') + $prefix + $path)
        }
    }
    return @($urls | Select-Object -Unique)
}

function Test-NvrPlaylist {
    param([string]$Address)
    $target = New-Object System.UriBuilder($Address)
    if ($target.Host -eq 'host.docker.internal') { $target.Host = '127.0.0.1' }
    $response = $null
    try {
        $request = [System.Net.HttpWebRequest]::Create($target.Uri)
        $request.Proxy = $null
        $request.Timeout = 3000
        $request.ReadWriteTimeout = 3000
        $response = $request.GetResponse()
        $buffer = New-Object byte[] 1024
        $count = $response.GetResponseStream().Read($buffer, 0, $buffer.Length)
        $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $count).TrimStart([char]0xFEFF)
        return [pscustomobject]@{ Valid = $text.StartsWith('#EXTM3U'); Status = [int]$response.StatusCode }
    }
    catch [System.Net.WebException] {
        $status = 0
        if ($null -ne $_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode; $_.Exception.Response.Close() }
        return [pscustomobject]@{ Valid = $false; Status = $status }
    }
    catch { return [pscustomobject]@{ Valid = $false; Status = 0 } }
    finally { if ($null -ne $response) { $response.Close() } }
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
        $candidates = @(Get-NvrHlsPaths (Get-NvrProperty $property.Value 'config') $baseAddress)
        $preferred = ''
        if ($candidates.Count -gt 0) { $preferred = $candidates[0] }
        [pscustomobject]@{ NVR = $number + 1; Bronadres = $preferred; Candidates = $candidates }
    }
}

function Read-NvrDatabase {
    param([string]$Container, [string]$DatabasePath)
    $output = @(& docker exec $Container cat $DatabasePath)
    if ($LASTEXITCODE -ne 0) { throw 'De bestaande Core-database kon niet worden uitgelezen. Controleer containernaam en DatabasePath.' }
    return $output -join "`n"
}

function Show-NvrSources {
    param([string]$Container, [string]$BaseUrl, [string]$DatabasePath, [switch]$NoCheck)
    if ($null -eq (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker is niet gevonden. Start Docker Desktop.' }
    $raw = Read-NvrDatabase $Container $DatabasePath
    $rows = @(ConvertFrom-NvrDatabase $raw $BaseUrl | Sort-Object NVR, Bronadres)
    $raw = $null
    if ($rows.Count -eq 0) { throw 'Geen NVR-kanalen met localhost-poorten 18550-18565 gevonden in deze database.' }
    Write-Host 'HLS-uitgangen uit de daadwerkelijke uitvoerconfiguratie:'
    foreach ($row in $rows) {
        Write-Host "`nNVR-kanaal $($row.NVR)"
        if ($row.Candidates.Count -eq 0) { Write-Host 'Geen HLS-uitvoer gevonden. Er wordt geen adres gegokt.'; continue }
        if ($NoCheck) { Write-Host 'Niet op beschikbaarheid gecontroleerd:'; $row.Candidates | Write-Output; continue }
        $found = $false
        $lastStatus = 0
        foreach ($candidate in $row.Candidates) {
            $result = Test-NvrPlaylist $candidate
            $lastStatus = $result.Status
            if ($result.Valid) { Write-Host 'Playlist bereikbaar (HTTP 200):'; Write-Output $candidate; $found = $true; break }
        }
        if (-not $found) {
            if ($lastStatus -eq 0) { Write-Host 'Niet bereikbaar vanaf deze pc. Controleer oude Woody en poort.' }
            elseif ($lastStatus -eq 200) { Write-Host 'HTTP 200, maar de reactie is geen HLS-playlist.' }
            else { Write-Host "Geen beschikbare playlist (HTTP $lastStatus). Gebruik een kanaal dat in de oude Woody beeld geeft." }
        }
    }
    Write-Host "`nDe oude containers en broninstellingen zijn niet gewijzigd. Gebruik deze HLS-adressen als netwerkbron in de nieuwe Restreamer."
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Show-NvrSources $Container $BaseUrl $DatabasePath -NoCheck:$NoCheck }
    catch { Write-Error -ErrorAction Continue $_.Exception.Message; exit 1 }
}
