[CmdletBinding()]
param([ValidateRange(30,1800)][int]$Seconds=600,[ValidateRange(60,3600)][int]$TimeoutSeconds=1800,[string]$Label='stage6',[switch]$Stage7)
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo=Split-Path $port -Parent
$run=Get-Content -LiteralPath (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
$directory=Split-Path $run.launched -Parent
function Read-SharedStatus([string]$Path) {
    $stream=[IO.File]::Open($Path,[IO.FileMode]::Open,[IO.FileAccess]::Read,
        ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $reader=[IO.StreamReader]::new($stream)
    try{return $reader.ReadToEnd()}finally{$reader.Dispose()}
}
$samples=[Collections.Generic.List[object]]::new()
$watch=[Diagnostics.Stopwatch]::StartNew()
$cafeStart=$null;$cafeSceneFinished=$false;$lastFrame=-1;$lastFresh=0;$result='RUNNING';$errorText=$null
$processObserved=$false
try {
    while($watch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        # A separate restricted shell may not see a GUI process launched by a
        # different host context. Assert disappearance only after seeing it.
        if(Get-Process -Id $run.pid -ErrorAction SilentlyContinue){$processObserved=$true}
        elseif($processObserved) {
            throw 'Azahar process ended before capture completed; cause requires user observation or emulator diagnostics'
        }
        $status=[ordered]@{}
        $rawStatus=Read-SharedStatus (Join-Path $repo 'sh1_data/stage4_status.txt')
        foreach($line in ($rawStatus -split "`n")){
            if($line -match '^([^=]+)=(.*)$'){$status[$Matches[1]]=$Matches[2].Trim()}
        }
        if($status.build -eq $run.build_identity -and $status.report_complete -eq '1') {
            if([int]$status.first_failure){throw "Failure $($status.first_failure): $($status.operation) detail $($status.detail)"}
            foreach($key in @($status.Keys)) {
                if($key -match '^state_\d+$') {
                    $row=$status[$key] -split ','
                    if($row.Count -eq 12 -and $row[1] -eq '1' -and $row[5] -eq '10' -and
                       $row[8] -eq '3' -and [uint32]$row[6] -ge 48 -and
                       [uint32]$row[6] -le 100){$cafeSceneFinished=$true}
                }
            }
            # The retail loop may submit without waiting for vblank. Use map
            # submissions once present; the wait counter can remain unchanged.
            # Stage 7 legitimately pauses world submissions in menus. A fresh
            # complete report comes from the live original loop on its thread.
            $freshFrame=if($Stage7){(Get-Item (Join-Path $repo 'sh1_data/stage4_status.txt')).LastWriteTimeUtc.Ticks}
                elseif([int]$status.map_frames -gt 0){[int]$status.map_frames}else{[int]$status.frames}
            if($freshFrame -ne $lastFrame) {
                $lastFrame=$freshFrame
                $lastFresh=$watch.Elapsed.TotalSeconds
                $samples.Add([ordered]@{elapsed=[Math]::Round($watch.Elapsed.TotalSeconds,2);status=$status})
                [IO.File]::WriteAllText((Join-Path $directory ($Label+'-samples.json')),(ConvertTo-Json -InputObject @($samples.ToArray()) -Depth 6))
                [IO.File]::WriteAllText((Join-Path $directory 'stage4_status.txt'),$rawStatus)
            }
            if($Stage7 -and ($status.map_idx -ne '1' -or $status.game_state -ne '11' -or
               $status.player_state -ne '0' -or $status.control_disabled -ne '0' -or [int]$status.player_health -le 0)){$cafeStart=$null}
            if($null -eq $cafeStart -and $cafeSceneFinished -and $status.map_idx -eq '1' -and $status.game_state -eq '11' -and
               $status.player_state -eq '0' -and $status.control_disabled -eq '0' -and [int]$status.player_health -gt 0){
                $cafeStart=$watch.Elapsed.TotalSeconds
            }
            if($watch.Elapsed.TotalSeconds-$lastFresh -gt 45) {
                throw 'No new runtime reports for 45 seconds; capture incomplete (pause, stall or terminated emulation)'
            }
            if($null -ne $cafeStart -and $watch.Elapsed.TotalSeconds-$cafeStart -ge $Seconds -and
               $watch.Elapsed.TotalSeconds-$lastFresh -le 20 -and $status.map_idx -eq '1' -and
               $status.game_state -eq '11' -and $status.player_state -eq '0' -and
               $status.control_disabled -eq '0' -and [int]$status.player_health -gt 0){
                $result='CAFE_LOG_CAPTURE_COMPLETE_VISUAL_REVIEW_REQUIRED';break
            }
        }
        Start-Sleep -Seconds 3
    }
    if($result -eq 'RUNNING'){throw 'Cafe capture timeout'}
} catch {$errorText=$_.Exception.Message;$result='FAIL'}
$report=[ordered]@{result=$result;error=$errorText;build=$run.build_identity;sha256=$run.build_sha256;
    seconds=$Seconds;elapsed=[Math]::Round($watch.Elapsed.TotalSeconds,2);cafe_start_elapsed=$cafeStart;
    cafe_scene_finished=$cafeSceneFinished;continuous_free_cafe=[bool]$Stage7;samples=$samples.Count;last=$status}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $directory ($Label+'-result.json')) -Encoding utf8
[ordered]@{result=$result;error=$errorText;directory=$directory;samples=$samples.Count;map=$status.map_idx;
    sys=$status.player_state;step=$status.sys_step0} | ConvertTo-Json
if($result -eq 'FAIL'){exit 1}
