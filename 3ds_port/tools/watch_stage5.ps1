[CmdletBinding()]
param([ValidateRange(180,900)][int]$Seconds=300)
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo=Split-Path $port -Parent
$run=Get-Content -LiteralPath (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
$directory=Split-Path $run.launched -Parent
$samples=[Collections.Generic.List[object]]::new()
$watch=[Diagnostics.Stopwatch]::StartNew()
$mapStart=$null
$lastFrame=-1
$result='RUNNING'
try {
    while ($watch.Elapsed.TotalSeconds -lt $Seconds+240) {
        $content=Get-Content -LiteralPath (Join-Path $repo 'sh1_data/stage4_status.txt') -Raw
        $status=[ordered]@{}
        foreach ($line in $content -split "`n") {
            if ($line -match '^([^=]+)=(.*)\r?$') { $status[$Matches[1]]=$Matches[2].Trim() }
        }
        if ($status.build -eq $run.build_identity -and $status.report_complete -eq '1') {
            if ([int]$status.map_frames -gt 0 -and $null -eq $mapStart) { $mapStart=$watch.Elapsed.TotalSeconds }
            $freshFrame=if ([int]$status.map_frames -gt 0) {[int]$status.map_frames} else {[int]$status.frames}
            if ($freshFrame -ne $lastFrame) {
                $lastFrame=$freshFrame
                $samples.Add([ordered]@{elapsed=[Math]::Round($watch.Elapsed.TotalSeconds,2);status=$status})
                [IO.File]::WriteAllText((Join-Path $directory 'stage5-samples.json'),(ConvertTo-Json -InputObject @($samples.ToArray()) -Depth 6))
                Copy-Item -LiteralPath (Join-Path $repo 'sh1_data/stage4_status.txt') -Destination (Join-Path $directory 'stage4_status.txt')
            }
            if ([int]$status.first_failure) { throw "Game failure $($status.first_failure): $($status.operation)" }
            if ($null -ne $mapStart -and $watch.Elapsed.TotalSeconds-$mapStart -ge $Seconds) {
                if ([int]$status.map_frames -le 1000) { throw 'Insufficient map submissions' }
                if ([int]$status.control_changes -le 10) { throw 'No sustained normal-pad movement evidence' }
                $recent=@($samples | Where-Object { $_.elapsed -ge $watch.Elapsed.TotalSeconds-75 })
                if ($recent.Count -lt 2 -or
                    [int]$status.control_changes-[int]$recent[0].status.control_changes -lt 5) {
                    throw 'Normal-pad movement stalled during the last minute; renderer endurance alone is insufficient'
                }
                $result='STABILITY_LOG_PASS_VISUAL_AND_HARDWARE_REVIEW_REQUIRED'; break
            }
        }
        Start-Sleep -Seconds 5
    }
    if ($result -eq 'RUNNING') { throw 'Stability timeout' }
} catch { $result='FAIL'; $failure=$_.Exception.Message }
$summary=[ordered]@{result=$result;error=$failure;build=$run.build_identity;sha256=$run.build_sha256;
    elapsed=[Math]::Round($watch.Elapsed.TotalSeconds,2);map_seconds=if ($null -ne $mapStart) {[Math]::Round($watch.Elapsed.TotalSeconds-$mapStart,2)} else {0};
    sample_count=$samples.Count;last=$status}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $directory 'stage5-stability.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $port 'build/azahar/user/log/azahar_log.txt') -Tail 2000 |
    Set-Content -LiteralPath (Join-Path $directory 'azahar_log.txt') -Encoding utf8
$summary | ConvertTo-Json -Depth 6
if ($result -eq 'FAIL') { exit 1 }
