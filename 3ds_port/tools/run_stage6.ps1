[CmdletBinding()]
param([switch]$DevelopmentCafe,[switch]$Restart,[string]$Rom)
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo=Split-Path $port -Parent
if(-not $Rom) {
    $Rom=Join-Path $port $(if($DevelopmentCafe){'silenthill_game_dev.3dsx'}else{'silenthill_game.3dsx'})
}
$route=Join-Path $repo 'sh1_data/stage6_route.txt'
if(Test-Path -LiteralPath $route){throw 'An unconsumed Stage 6 pad fixture already exists.'}
Copy-Item -LiteralPath (Join-Path $port 'tests/stage6_route.txt') -Destination $route
& (Join-Path $PSScriptRoot 'run_azahar.ps1') -Target Game -Rom $Rom -Restart:$Restart -AutoMenu -Expect Scene -TimeoutSeconds 180

