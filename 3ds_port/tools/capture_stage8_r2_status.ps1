param([Parameter(Mandatory)][string]$Label)
$ErrorActionPreference='Stop'
if($Label -notmatch '^[a-z0-9-]+$'){throw 'Invalid evidence label'}
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$source=Join-Path (Split-Path $port -Parent) 'sh1_data/stage4_status.txt'
for($attempt=0;$attempt -lt 20;$attempt++) {
    $raw=[IO.File]::ReadAllText($source)
    if($raw -match '(?m)^report_complete=1\r?$'){break}
    Start-Sleep -Milliseconds 100
}
if($raw -notmatch '(?m)^report_complete=1\r?$'){throw 'Incomplete snapshot'}
$values=@{}
foreach($line in ($raw -split "`n")) {
    if($line -match '^([^=]+)=(.*)$'){$values[$Matches[1]]=$Matches[2].Trim()}
}
$run=Get-Content (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
if($values.build -ne $run.build_identity -or $values.first_failure -ne '0'){throw 'Stale or failed snapshot'}
$target=Join-Path $port ('reports/azahar-stage8-r2-cafe/'+$Label+'.txt')
if(Test-Path -LiteralPath $target){throw 'Evidence label already exists'}
[IO.File]::WriteAllText($target,$raw)
[ordered]@{label=$Label;build=$values.build;state=$values.game_state;sys=$values.player_state;
    map=$values.map_idx;fps_mode=$values.stage8_fps_limit;fps=$values.recent_fps;
    simulation=$values.recent_sim_speed;status_opens=$values.stage8_status_opens} | ConvertTo-Json
