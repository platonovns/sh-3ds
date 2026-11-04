[CmdletBinding()]
param([ValidateRange(30,1800)][int]$TimeoutSeconds=900)
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$repo=Split-Path $port -Parent
$run=Get-Content (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
$timer=[Diagnostics.Stopwatch]::StartNew()
while($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
    $raw=Get-Content (Join-Path $repo 'sh1_data/stage4_status.txt') -Raw
    if($raw -match ('(?m)^build='+[regex]::Escape($run.build_identity)+'\r?$') -and $raw -match '(?m)^report_complete=1\r?$') {
        if($raw -match '(?m)^first_failure=([1-9][0-9]*)\r?$'){throw "Runtime failure $($Matches[1])"}
        if($raw -match '(?m)^map_idx=1\r?$') {
            [IO.File]::WriteAllText((Join-Path $repo 'sh1_data/stage7_pad.txt'),"STOP_ROUTE`n",[Text.Encoding]::ASCII)
            @{action='Stop only diagnostic route movement at Cafe; normal dialogue/action input continues';
              build=$run.build_identity;sha256=$run.build_sha256;elapsed=$timer.Elapsed.TotalSeconds;
              time=[DateTimeOffset]::Now.ToString('o')} | ConvertTo-Json | Set-Content (Join-Path $port 'reports/stage7-final-route-stop.json') -Encoding utf8
            return
        }
    }
    Start-Sleep -Milliseconds 500
}
throw 'Cafe was not observed before diagnostic route timeout'
