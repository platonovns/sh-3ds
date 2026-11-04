param([Parameter(Mandatory)][string]$Name,
      [Parameter(Mandatory)][string]$DiagnosticDirectory,
      [Parameter(Mandatory)][int]$ExpectedMap,
      [int]$ExpectedRoom=-1,[int]$TimeoutSeconds=180,[string]$ReportPrefix='stage10-r5')
$ErrorActionPreference='Stop'
$port=Split-Path $PSScriptRoot -Parent
$repo=Split-Path $port -Parent
$variant=Get-Content (Join-Path $DiagnosticDirectory 'manifest.json') -Raw|ConvertFrom-Json
$run=Get-Content (Join-Path $port 'build/azahar/last-run.json') -Raw|ConvertFrom-Json
if($run.build_sha256 -ne $variant.sha256){throw 'Wrong diagnostic launch'}
$dest=Join-Path $port ('reports/'+$ReportPrefix+'-'+$Name+'-pica')
New-Item -ItemType Directory -Force $dest|Out-Null
$clock=[Diagnostics.Stopwatch]::StartNew()
$runStartedUtc=if($run.started -is [DateTime]){$run.started.ToUniversalTime()}
    else{[DateTimeOffset]::Parse([string]$run.started,[Globalization.CultureInfo]::InvariantCulture).UtcDateTime}
do {
    # A repeated diagnostic has the same build ID. Never accept the previous
    # process's completed EXIT before this process has written its own report.
    if((Get-Item (Join-Path $repo 'sh1_data/stage4_status.txt')).LastWriteTimeUtc -le $runStartedUtc) {
        Start-Sleep -Milliseconds 300
        continue
    }
    $text=Get-Content (Join-Path $repo 'sh1_data/stage4_status.txt') -Raw
    $values=@{}
    foreach($line in $text -split "`n") {if($line -match '^([^=]+)=(.*)$'){$values[$Matches[1]]=$Matches[2].TrimEnd("`r")}}
    if($values.build -eq $variant.build -and $values.report_complete -eq '1') {
        if($values.first_failure -ne '0'){throw ('Game failure '+$values.first_failure+': '+$values.operation)}
        if($values.checkpoint -eq 'EXIT'){break}
    }
    Start-Sleep -Milliseconds 300
} while($clock.Elapsed.TotalSeconds -lt $TimeoutSeconds)
if($values.build -ne $variant.build -or $values.checkpoint -ne 'EXIT' -or $values.report_complete -ne '1'){throw 'No complete diagnostic exit'}
if([int]$values.map_idx -ne $ExpectedMap -or ($ExpectedRoom -ge 0 -and [int]$values.map_room -ne $ExpectedRoom)){throw 'Wrong destination map/room'}
if([int]$values.readback_direct_mismatches -ne 0 -or [int]$values.gpu_duplicate_presents -ne 0){throw 'Readback/presentation mismatch'}
[IO.File]::WriteAllText((Join-Path $dest 'status.txt'),$text)
$run|ConvertTo-Json -Depth 6|Set-Content (Join-Path $dest 'run.json') -Encoding utf8
$started=if($run.started -is [DateTime]){$run.started.ToLocalTime()}
    else{[DateTimeOffset]::Parse([string]$run.started,[Globalization.CultureInfo]::InvariantCulture).LocalDateTime}
$captures=@()
foreach($file in Get-ChildItem (Join-Path $repo 'sh1_data') -Filter 'dev*.bmp') {
    if($file.LastWriteTime -ge $started.AddSeconds(-2)) {
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $dest $file.Name)
        $captures+=@{file=$file.Name;bytes=$file.Length;sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()}
    }
}
$record=@{status='PASS';scope='Actual Azahar PICA diagnostic; not New 3DS hardware acceptance';
    diagnostic=$variant;launch_sha256=$run.build_sha256;checkpoint=$values.checkpoint;map=[int]$values.map_idx;
    room=[int]$values.map_room;map_frames=[int]$values.map_frames;first_failure=0;
    readback_direct_mismatches=0;duplicate_presents=0;packet_peak=[int]$values.packet_peak;
    packet_capacity=[int]$values.packet_capacity;captures=$captures;hardware_accepted=$false}
$record|ConvertTo-Json -Depth 8|Set-Content (Join-Path $dest 'qualification.json') -Encoding utf8
$record|ConvertTo-Json -Depth 8
