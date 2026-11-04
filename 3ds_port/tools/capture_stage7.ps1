[CmdletBinding()]
param([Parameter(Mandatory)][ValidatePattern('^[a-z0-9-]+$')][string]$Label)
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo=Split-Path $port -Parent
$run=Get-Content (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
$statusPath=Join-Path $repo 'sh1_data/stage4_status.txt'
$status=[ordered]@{}
for($attempt=0;$attempt -lt 10;$attempt++) {
    $raw=Get-Content -LiteralPath $statusPath -Raw
    $status=[ordered]@{}
    foreach($line in ($raw -split "`n")) {
        if($line -match '^([^=]+)=(.*)$'){$status[$Matches[1]]=$Matches[2].Trim()}
    }
    if($status.report_complete -eq '1' -and $status.build -eq $run.build_identity){break}
    Start-Sleep -Milliseconds 100
}
if($status.report_complete -ne '1' -or $status.build -ne $run.build_identity){throw 'Incomplete or stale status'}
if($status.first_failure -ne '0'){throw "Runtime failure $($status.first_failure): $($status.operation)"}
$card=Join-Path $repo 'sh1_data/memcard.mcr'
$cardInfo=$null
if(Test-Path -LiteralPath $card) {
    $cardInfo=[ordered]@{bytes=(Get-Item $card).Length;sha256=(Get-FileHash $card -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$evidence=Join-Path $port 'reports/azahar-stage7-systems'
New-Item -ItemType Directory -Force $evidence | Out-Null
$target=Join-Path $evidence ($Label+'.json')
if(Test-Path -LiteralPath $target){throw "Evidence already exists: $target"}
$record=[ordered]@{label=$Label;captured=[DateTimeOffset]::Now.ToString('o');run=$run;card=$cardInfo;status=$status}
[IO.File]::WriteAllText($target,($record | ConvertTo-Json -Depth 8))
[ordered]@{label=$Label;build=$status.build;state=$status.game_state;sys=$status.player_state;
    x=$status.player_x;z=$status.player_z;inventory=$status.inventory_count;equipped=$status.inventory_equipped;
    pickups=$status.picked_up_item_count;card=$cardInfo} | ConvertTo-Json -Depth 4
