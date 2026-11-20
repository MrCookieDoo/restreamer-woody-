$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/nvr-sources.ps1')
function Assert-NvrTest {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
$first = '11111111-1111-1111-1111-111111111111'
$last = '22222222-2222-2222-2222-222222222222'
$ignored = '33333333-3333-3333-3333-333333333333'
$process = @{}
$metadata = @{}
foreach ($entry in @(@($first,18550,0,'memfs'), @($last,18565,15,'diskfs'), @($ignored,18550,0,'memfs'))) {
    $id = 'restreamer-ui:ingest:' + $entry[0]
    $source = "http://127.0.0.1:$($entry[1])/channel$($entry[2]).ts"
    if ($entry[0] -eq $ignored) { $source = 'rtsp://private-user:private-password@camera/live' }
    $process[$id] = @{ id = $id; config = @{ input = @(@{ address = $source }) } }
    $metadata[$id] = @{ 'restreamer-ui' = @{
        sources = @(@{ type = 'network'; settings = @{mode='pull';address=$source}; inputs = @(@{address=$source}) })
        profiles = @(@{video=@{source=0}})
        control = @{hls=@{storage=$entry[3]}}
    } }
}
$json = @{ version=4;process=$process;metadata=@{process=$metadata} } | ConvertTo-Json -Depth 15 -Compress
$rows = @(ConvertFrom-NvrDatabase $json 'http://host.docker.internal:8080' | Sort-Object NVR)
Assert-NvrTest ($rows.Count -eq 2) 'Non-NVR sources were included or matching sources were missed'
Assert-NvrTest ($rows[0].NVR -eq 1 -and $rows[0].Bronadres -eq "http://host.docker.internal:8080/memfs/$first.m3u8") 'Incorrect first NVR memory HLS address'
Assert-NvrTest ($rows[1].NVR -eq 16 -and $rows[1].Bronadres -eq "http://host.docker.internal:8080/$last.m3u8") 'Incorrect final NVR disk HLS address'
Assert-NvrTest (-not (($rows | ConvertTo-Json) -match 'private-password|private-user|rtsp://|18550')) 'Source credentials or raw loopback addresses were exposed'
$failed = $false
try { ConvertFrom-NvrDatabase 'invalid-private-password' 'http://host.docker.internal:8080' }
catch { $failed = $_.Exception.Message -notmatch 'invalid-private-password' }
Assert-NvrTest $failed 'Malformed data was not safely rejected'
$failed = $false
try { ConvertFrom-NvrDatabase $json 'http://admin:private-password@host:8080' }
catch { $failed = $_.Exception.Message -notmatch 'private-password' }
Assert-NvrTest $failed 'Credential-bearing output URLs were accepted'
# Exercise the actual orchestration with a read-only Docker-command mock.
function docker {
    $script:dockerCall = $args -join ' '
    $global:LASTEXITCODE = 0
    return $json
}
$output = Show-NvrSources 'Woody' 'http://host.docker.internal:8080' '/core/config/db.json'
Assert-NvrTest ($script:dockerCall -eq 'exec Woody cat /core/config/db.json') 'Unexpected Docker mutation'
Assert-NvrTest (($output -join '') -notmatch 'private-password|private-user') 'Private source values appeared in output'
Write-Host '7 NVR-source checks passed.'
