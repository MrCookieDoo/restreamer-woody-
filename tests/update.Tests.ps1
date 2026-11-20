$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/update.ps1')
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('woody-update-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$envPath = Join-Path $testRoot '.env'
Set-Content -LiteralPath $envPath -Value 'WOODY_HTTP_PORT=8082'
$originalEnv = [System.IO.File]::ReadAllText($envPath)
# No native commands are executed: this checks the orchestration and boundaries.
function git { }
function docker { }
function Assert-WoodyTest {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw $Message }
}
function Reset-WoodyTest {
    $script:case = @{ Dirty = $false; BuildFail = $false; Ambiguous = $false; Bot = $false }
    $script:trace = New-Object System.Collections.Generic.List[string]
}
function Invoke-WoodyCommand {
    param([string]$Program, [string[]]$CommandArguments)
    $script:trace.Add($Program + ' ' + ($CommandArguments -join ' '))
    if ($Program -eq 'git') {
        switch ($CommandArguments[0]) {
            'rev-parse' { return 'true' }
            'status' { if ($script:case.Dirty) { return ' M ui/src/Header.js' }; return }
            'branch' { return 'feat/woody-studio' }
            'pull' { return 'Mock pull succeeded' }
        }
    }
    if ($Program -eq 'docker') {
        switch ($CommandArguments[0]) {
            'info' { return 'linux' }
            'inspect' {
                $projectName = 'woody-test'
                if ($CommandArguments[1] -eq 'second-studio') { $projectName = 'woody-second' }
                return (@{
                    'com.docker.compose.project' = $projectName
                    'com.docker.compose.project.working_dir' = $testRoot
                } | ConvertTo-Json -Compress)
            }
            'ps' {
                if ($CommandArguments -contains 'label=com.docker.compose.service=studio') {
                    if ($script:case.Ambiguous) { return @('first-studio', 'second-studio') }
                    return 'first-studio'
                }
                if ($script:case.Bot) { return 'running-chatbot' }
                return
            }
            'compose' {
                if ($CommandArguments -contains 'build') {
                    if ($script:case.BuildFail) { throw 'Mock build failed' }
                    return 'Mock build succeeded'
                }
                if ($CommandArguments -contains 'port') { return '0.0.0.0:8082' }
                return
            }
        }
    }
    throw "Unexpected native command in test: $Program $CommandArguments"
}
function Assert-WoodyFailure {
    param([string]$Expected, [string]$Project = '')
    $failed = $false
    try { Invoke-WoodyUpdate -RepoRoot $testRoot -Project $Project }
    catch { $failed = $_.Exception.Message -like "*$Expected*" }
    Assert-WoodyTest $failed "Expected refusal: $Expected"
    Assert-WoodyTest (-not (($script:trace -join "`n") -match ' up -d')) 'A refused update restarted containers'
}
try {
    Reset-WoodyTest
    Invoke-WoodyUpdate -RepoRoot $testRoot
    $commands = $script:trace -join "`n"
    Assert-WoodyTest ($commands -match 'docker compose -p woody-test build') 'Wrong build project'
    Assert-WoodyTest ($commands -match 'docker compose -p woody-test up -d --no-build') 'Missing safe start'
    Assert-WoodyTest ($commands.IndexOf(' build') -lt $commands.IndexOf(' up -d')) 'Restart happened before build'
    Assert-WoodyTest (-not ($commands -match ' down| volume rm|setup.py|--profile')) 'Unexpected destructive action or disabled chatbot enabled'
    Assert-WoodyTest ([System.IO.File]::ReadAllText($envPath) -eq $originalEnv) '.env was changed'

    Reset-WoodyTest
    $script:case.Dirty = $true
    Assert-WoodyFailure 'lokale wijzigingen'
    Assert-WoodyTest (-not (($script:trace -join "`n") -match 'git pull')) 'Dirty checkout was pulled'

    Reset-WoodyTest
    $script:case.BuildFail = $true
    Assert-WoodyFailure 'Mock build failed'

    Reset-WoodyTest
    $script:case.Ambiguous = $true
    Assert-WoodyFailure 'Meerdere Woody-projecten'

    Reset-WoodyTest
    Assert-WoodyFailure 'geen bestaande Woody-installatie' -Project 'standard-restreamer'

    Reset-WoodyTest
    $script:case.Bot = $true
    Invoke-WoodyUpdate -RepoRoot $testRoot
    Assert-WoodyTest (($script:trace -join "`n") -match '--profile chatbot build') 'An already running chatbot was skipped'

    Assert-WoodyTest ((ConvertTo-WoodyPath 'C:\Users\Raven\My Project\') -eq (ConvertTo-WoodyPath '/mnt/c/users/raven/my project')) 'Windows/WSL directory comparison failed'
    Write-Host '7 updater checks passed.'
}
finally { Remove-Item -LiteralPath $testRoot -Recurse -Force }
