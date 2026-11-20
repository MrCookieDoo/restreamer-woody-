[CmdletBinding()]
param([string]$Project = '')

$ErrorActionPreference = 'Stop'
$script:WoodyRepoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-WoodyCommand {
    param([string]$Program, [string[]]$CommandArguments)
    & $Program @CommandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program is mislukt (code $LASTEXITCODE). Bekijk de melding hierboven. Er zijn geen opslagvolumes verwijderd."
    }
}

function ConvertTo-WoodyPath {
    param([string]$Value)
    $normalized = $Value.Replace('\', '/').TrimEnd('/').ToLowerInvariant()
    if ($normalized -match '^/mnt/([a-z])/(.*)$') {
        $normalized = $Matches[1] + ':/' + $Matches[2]
    }
    return $normalized
}

function Get-WoodyLabel {
    param($Labels, [string]$Name)
    if ($null -eq $Labels) { return '' }
    $property = $Labels.PSObject.Properties[$Name]
    if ($null -eq $property) { return '' }
    return [string]$property.Value
}

function Get-WoodyProject {
    param([string]$RepoRoot, [string]$Requested)
    $containerIds = @(Invoke-WoodyCommand 'docker' @('ps', '-a', '--filter', 'label=com.docker.compose.service=studio', '--format', '{{.ID}}'))
    $projects = @()
    foreach ($containerId in $containerIds) {
        if ([string]::IsNullOrWhiteSpace($containerId)) { continue }
        $json = (Invoke-WoodyCommand 'docker' @('inspect', $containerId, '--format', '{{json .Config.Labels}}')) -join "`n"
        $labels = $json | ConvertFrom-Json
        $workingDir = Get-WoodyLabel $labels 'com.docker.compose.project.working_dir'
        if ((ConvertTo-WoodyPath $workingDir) -eq (ConvertTo-WoodyPath $RepoRoot)) {
            $name = Get-WoodyLabel $labels 'com.docker.compose.project'
            if ($name) { $projects += $name }
        }
    }
    $projects = @($projects | Sort-Object -Unique)
    if ($Requested) {
        if ($projects -notcontains $Requested) {
            throw "Project '$Requested' is geen bestaande Woody-installatie uit deze map. Er wordt geen nieuw project gestart."
        }
        return $Requested
    }
    if ($projects.Count -eq 1) { return $projects[0] }
    if ($projects.Count -eq 0) {
        throw 'Geen bestaande Woody Studio-container uit deze map gevonden. Start eerst de eenmalige installatie en bewaar dezelfde projectmap.'
    }
    throw "Meerdere Woody-projecten gevonden: $($projects -join ', '). Kies er een met update.cmd -Project PROJECTNAAM."
}

function Invoke-WoodyUpdate {
    param([string]$Project = '', [string]$RepoRoot = $script:WoodyRepoRoot)
    Push-Location -LiteralPath $RepoRoot
    try {
        foreach ($program in @('git', 'docker')) {
            if ($null -eq (Get-Command $program -ErrorAction SilentlyContinue)) {
                throw "$program is niet gevonden. Installeer Git/Docker Desktop eenmalig en open PowerShell opnieuw."
            }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.env'))) {
            throw '.env ontbreekt. Dit is een updater voor een bestaande installatie; het maakt of overschrijft geen instellingen.'
        }
        $inside = (Invoke-WoodyCommand 'git' @('rev-parse', '--is-inside-work-tree')) -join ''
        if ($inside.Trim() -ne 'true') { throw 'Deze map is geen Git-checkout.' }
        $dirty = @(Invoke-WoodyCommand 'git' @('status', '--porcelain', '--untracked-files=no'))
        if (($dirty -join '').Trim()) {
            throw 'De broncode bevat lokale wijzigingen. Bewaar die eerst met Git; de updater overschrijft ze niet. .env mag wel aangepast zijn.'
        }
        $branch = ((Invoke-WoodyCommand 'git' @('branch', '--show-current')) -join '').Trim()
        if (-not $branch) { throw 'Geen actieve Git-branch. Kies eerst de Woody-branch.' }
        $engine = ((Invoke-WoodyCommand 'docker' @('info', '--format', '{{.OSType}}')) -join '').Trim()
        if ($engine -ne 'linux') { throw 'Woody vereist de Linux-containerengine van Docker Desktop.' }
        Invoke-WoodyCommand 'docker' @('compose', 'version') | Out-Host
        $selectedProject = Get-WoodyProject $RepoRoot $Project
        $composeArguments = @('compose', '-p', $selectedProject)
        $runningBots = @(Invoke-WoodyCommand 'docker' @('ps', '--filter', "label=com.docker.compose.project=$selectedProject", '--filter', 'label=com.docker.compose.service=chatbot', '--format', '{{.ID}}'))
        if (($runningBots -join '').Trim()) { $composeArguments += @('--profile', 'chatbot') }

        Write-Host "Woody bijwerken: project $selectedProject, branch $branch"
        Write-Host '1/3 Wijzigingen ophalen...'
        Invoke-WoodyCommand 'git' @('pull', '--ff-only', 'origin', $branch) | Out-Host
        Invoke-WoodyCommand 'docker' ($composeArguments + @('config', '--quiet')) | Out-Host
        Write-Host '2/3 Images bouwen met de bestaande cache. De containers blijven intussen draaien...'
        Invoke-WoodyCommand 'docker' ($composeArguments + @('build')) | Out-Host
        Write-Host '3/3 Alleen dit Woody-project bijwerken...'
        Invoke-WoodyCommand 'docker' ($composeArguments + @('up', '-d', '--no-build')) | Out-Host
        $binding = ((Invoke-WoodyCommand 'docker' ($composeArguments + @('port', 'gateway', '80'))) -join "`n")
        if ($binding -match ':(\d+)') { Write-Host "Klaar. Open http://localhost:$($Matches[1])/ui/ en druk Ctrl+F5." }
        else { Write-Host 'Klaar. Open je bestaande Woody-adres en druk Ctrl+F5.' }
        Write-Host 'Je .env, camera-instellingen en opslagvolumes zijn behouden.'
    }
    finally { Pop-Location }
}

if ($MyInvocation.InvocationName -ne '.') {
    try { Invoke-WoodyUpdate -Project $Project }
    catch { Write-Error -ErrorAction Continue $_.Exception.Message; exit 1 }
}
