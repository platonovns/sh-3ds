[CmdletBinding()]
param([ValidateRange(60,900)][int]$Seconds=300,[string]$Label='stationary-baseline')
$ErrorActionPreference='Stop'
$port=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo=Split-Path $port -Parent
$run=Get-Content -LiteralPath (Join-Path $port 'build/azahar/last-run.json') -Raw | ConvertFrom-Json
$directory=Split-Path $run.launched -Parent
$samples=[Collections.Generic.List[object]]::new()
$timer=[Diagnostics.Stopwatch]::StartNew()
$controlStart=$null; $lastFrame=-1; $failure=$null; $result='RUNNING'
try {
    while ($timer.Elapsed.TotalSeconds -lt $Seconds+240) {
        $status=[ordered]@{}
        $content=Get-Content -LiteralPath (Join-Path $repo 'sh1_data/stage4_status.txt') -Raw
        foreach ($line in $content -split "`n") {
            if ($line -match '^([^=]+)=(.*)\r?$') { $status[$Matches[1]]=$Matches[2].Trim() }
        }
        if ($status.build -eq $run.build_identity -and $status.report_complete -eq '1') {
            if ([int]$status.first_failure) { throw "Failure $($status.first_failure): $($status.operation)" }
            if ($null -eq $controlStart -and $status.player_state -eq '0' -and [int]$status.map_frames -gt 700) {
                $controlStart=$timer.Elapsed.TotalSeconds
            }
            $freshFrame=if ([int]$status.map_frames -gt 0) {[int]$status.map_frames} else {[int]$status.frames}
            if ($freshFrame -ne $lastFrame) {
                $lastFrame=$freshFrame
                $samples.Add([ordered]@{elapsed=[Math]::Round($timer.Elapsed.TotalSeconds,2);
                    control_elapsed=if($null -eq $controlStart){-1}else{[Math]::Round($timer.Elapsed.TotalSeconds-$controlStart,2)};status=$status})
                [IO.File]::WriteAllText((Join-Path $directory ($Label+'-samples.json')),
                    (ConvertTo-Json -InputObject @($samples.ToArray()) -Depth 6))
                Copy-Item -LiteralPath (Join-Path $repo 'sh1_data/stage4_status.txt') -Destination (Join-Path $directory 'stage4_status.txt')
            }
            if ($null -ne $controlStart -and $timer.Elapsed.TotalSeconds-$controlStart -ge $Seconds) {
                $result='CAPTURE_COMPLETE_ANALYSIS_REQUIRED'; break
            }
        }
        Start-Sleep -Seconds 3
    }
    if ($result -eq 'RUNNING') { throw 'Capture timeout' }
} catch { $failure=$_.Exception.Message; $result='FAIL' }
$summary=[ordered]@{result=$result;label=$Label;error=$failure;build=$run.build_identity;sha256=$run.build_sha256;
    seconds=$Seconds;sample_count=$samples.Count;last=$status}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $directory ($Label+'-result.json')) -Encoding utf8
$summary | ConvertTo-Json -Depth 6
if ($result -eq 'FAIL') { exit 1 }
