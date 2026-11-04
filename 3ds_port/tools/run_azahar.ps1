[CmdletBinding()]
param(
    [string]$Azahar = 'C:\azahar-windows\azahar.exe',
    [string]$ImageDirectory,
    [ValidateSet('Diagnostic','Game')][string]$Target = 'Diagnostic',
    [string]$Rom,
    [switch]$Build,
    [switch]$Restart,
    [ValidateSet('Stage41','Title','Scene','None')][string]$Expect = 'Stage41',
    [switch]$AutoMenu,
    [switch]$AutoGameplay,
    [switch]$AutoStationary,
    [switch]$Profile,
    [switch]$AutoRunning,
    [switch]$AutoGarage,
    [switch]$GdbStub,
    [switch]$RpcServer,
    [ValidateRange(5,600)][int]$TimeoutSeconds = 90,
    [switch]$PrepareOnly
)
$ErrorActionPreference = 'Stop'
$port = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$repo = Split-Path $port -Parent
$runtime = Join-Path $port 'build\azahar'
$userDir = Join-Path $runtime 'user'
if (-not $ImageDirectory) { $ImageDirectory = Join-Path $repo 'sh1_data' }
$ImageDirectory = (Resolve-Path -LiteralPath $ImageDirectory).Path
$Azahar = (Resolve-Path -LiteralPath $Azahar).Path
foreach ($name in @('sh1.bin','sh1.cue')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ImageDirectory $name) -PathType Leaf)) { throw "Missing $name in $ImageDirectory" }
}
$running = @(Get-Process azahar -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $Azahar})
if ($running.Count) {
    $lastPath = Join-Path $runtime 'last-run.json'
    $last = if (Test-Path -LiteralPath $lastPath) { Get-Content -LiteralPath $lastPath -Raw | ConvertFrom-Json } else { $null }
    $lastStarted = if ($last -and $last.started -is [DateTime]) { $last.started.ToUniversalTime() }
                   elseif ($last) { [DateTimeOffset]::Parse([string]$last.started, [Globalization.CultureInfo]::InvariantCulture).UtcDateTime }
                   else { [DateTime]::MinValue }
    if (-not $Restart -or $running.Count -ne 1 -or -not $last -or $running[0].Id -ne $last.pid `
        -or $running[0].StartTime.ToUniversalTime() -lt $lastStarted.AddSeconds(-2) `
        -or $running[0].StartTime.ToUniversalTime() -gt $lastStarted.AddSeconds(5)) {
        throw 'Azahar is already running. Exit that session normally, or use -Restart only for a session owned by this helper.'
    }
    # Process lifecycle, never window/UI injection. Only our last recorded PID.
    Stop-Process -Id $running[0].Id
    $running[0].WaitForExit(5000) | Out-Null
}
if ($Build) {
    if ($Rom) { throw '-Build cannot be combined with an explicit -Rom snapshot.' }
    $taskRoot = Split-Path $repo -Parent
    $wslRoot = '/mnt/' + $taskRoot.Substring(0,1).ToLowerInvariant() + ($taskRoot.Substring(2) -replace '\\','/')
    $makeArguments = @('make','-C','3ds_port','-j2')
    if ($Target -eq 'Game') { $makeArguments += @('-f','Makefile.game') }
    & wsl.exe -d Ubuntu-26.04 -- bash "$wslRoot/.toolchain/run_stage1a.sh" @makeArguments
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $LASTEXITCODE" }
}
$rom = if ($Rom) { [IO.Path]::GetFullPath($Rom) } elseif ($Target -eq 'Game') {
    Join-Path $port 'silenthill_game.3dsx'
} else { Join-Path $port 'silenthill_3ds.3dsx' }
if (-not (Test-Path -LiteralPath $rom -PathType Leaf)) { throw "Build missing: $rom" }
foreach ($folder in @('config','sdmc\3ds','nand','log','screenshots')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $userDir $folder) | Out-Null
}
function Assert-OrCreateJunction([string]$Link, [string]$Target) {
    if (Test-Path -LiteralPath $Link) {
        $item = Get-Item -LiteralPath $Link -Force
        if ($item.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$item.Target) -ne [IO.Path]::GetFullPath($Target)) {
            throw "Refusing to replace existing path: $Link (expected junction to $Target)"
        }
    } else { New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null }
}
# Installed 2126.2 chooses exe-directory/user on Windows. No guessed env override.
Assert-OrCreateJunction (Join-Path (Split-Path $Azahar -Parent) 'user') $userDir
Assert-OrCreateJunction (Join-Path $userDir 'sdmc\3ds\silenthill') $ImageDirectory
$nand = (Join-Path $userDir 'nand') -replace '\\','/'
$sdmc = (Join-Path $userDir 'sdmc') -replace '\\','/'
$shots = (Join-Path $userDir 'screenshots') -replace '\\','/'
# Reproducible project profile, separate from %APPDATA%/Azahar. Azahar fills defaults.
$config = @"
[Data%20Storage]
use_virtual_sd\default=false
use_virtual_sd=true
use_custom_storage\default=false
use_custom_storage=true
nand_directory\default=false
nand_directory=$nand
sdmc_directory\default=false
sdmc_directory=$sdmc
[Core]
use_cpu_jit\default=false
use_cpu_jit=true
cpu_clock_percentage\default=false
cpu_clock_percentage=100
[System]
is_new_3ds\default=false
is_new_3ds=true
[Renderer]
graphics_api\default=false
graphics_api=1
resolution_factor\default=false
resolution_factor=1
[Miscellaneous]
log_filter\default=false
log_filter=*:Info
[Debugging]
instant_debug_log\default=false
instant_debug_log=true
use_gdbstub\default=false
use_gdbstub=$(([bool]$GdbStub).ToString().ToLowerInvariant())
gdbstub_port\default=false
gdbstub_port=24689
enable_rpc_server\default=false
enable_rpc_server=$(([bool]$RpcServer).ToString().ToLowerInvariant())
[UI]
Paths\screenshotPath\default=false
Paths\screenshotPath=$shots
"@
$configPath = Join-Path $userDir 'config\qt-config.ini'
Set-Content -LiteralPath $configPath -Value $config -Encoding utf8
if ($PrepareOnly) { Write-Output "Prepared $userDir; no image copy created"; return }
$run = Join-Path $runtime ('runs\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $run -Force | Out-Null
$snapshot = Join-Path $run 'silenthill_3ds.3dsx'
Copy-Item -LiteralPath $rom -Destination $snapshot
Copy-Item -LiteralPath $configPath -Destination (Join-Path $run 'qt-config.ini')
$sourceHash = (Get-FileHash -LiteralPath $rom -Algorithm SHA256).Hash.ToLowerInvariant()
if ((Get-FileHash -LiteralPath $snapshot -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceHash) { throw 'Build snapshot mismatch' }
$identityMatch = [regex]::Match([Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($snapshot)), 'stage11a-cpu-[AB]-src-[0-9a-f]{16}|stage11a\.[0-9]-(?:control-(?:profile|timing)|lifetime|tracefix)-src-[0-9a-f]{16}|stage(?:[4-9]|10)\.[0-9](?:-dev[1-9]|-cpurec)?-src-[0-9a-f]{16}')
$buildIdentity = if ($identityMatch.Success) { $identityMatch.Value } else { $null }
$started = Get-Date
if($AutoRunning -or $AutoGarage) { $AutoGameplay=$true }
if($Profile) { [IO.File]::WriteAllText((Join-Path $ImageDirectory 'stage5_profile.txt'),"DETAIL16`n",[Text.Encoding]::ASCII) }
if ($AutoMenu -or $AutoGameplay -or $AutoStationary) {
    if ($Target -ne 'Game') { throw 'AutoMenu is input-only for the Game target.' }
    $fixtureText = if ($AutoGarage) { "STAGE5_GARAGE_PAD_INPUT`n" } elseif ($AutoStationary) { "STAGE5_STATIONARY_PAD_INPUT`n" } elseif ($AutoRunning) { "STAGE5_RUNNING_PAD_INPUT`n" } elseif ($AutoGameplay) { "STAGE5_GAMEPLAY_PAD_INPUT`n" } else { "STAGE4_LEVEL_B_PAD_INPUT`n" }
    [IO.File]::WriteAllText((Join-Path $ImageDirectory 'stage4_autoinput.txt'),$fixtureText,[Text.Encoding]::ASCII)
}
$process = Start-Process -FilePath $Azahar -ArgumentList ('"' + $snapshot + '"') -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $run 'stdout.txt') -RedirectStandardError (Join-Path $run 'stderr.txt') -PassThru
$manifest = [ordered]@{schema=1;started=$started.ToString('o');pid=$process.Id;source=$rom;launched=$snapshot;
    build_sha256=$sourceHash;build_bytes=(Get-Item -LiteralPath $snapshot).Length;build_identity=$buildIdentity;
    azahar=$Azahar;azahar_sha256=(Get-FileHash -LiteralPath $Azahar -Algorithm SHA256).Hash.ToLowerInvariant();
    config_sha256=(Get-FileHash -LiteralPath $configPath -Algorithm SHA256).Hash.ToLowerInvariant();
    expectation=$Expect;diagnostic_pad_pulses=[bool]($AutoMenu -or $AutoGameplay -or $AutoStationary);diagnostic_gameplay=[bool]$AutoGameplay;diagnostic_stationary=[bool]$AutoStationary;gdb_stub=[bool]$GdbStub;result='RUNNING';user_directory=$userDir;image_directory=$ImageDirectory}
function Save-Manifest {
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $run 'run.json') -Encoding utf8
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $runtime 'last-run.json') -Encoding utf8
}
function Collect-Reports {
    # Explicit small report allowlist. Never recurse into or copy the image directory.
    foreach ($name in @('stage4_fs.txt','stage4_status.txt','tim_test.txt','disc_test.txt','smoke.txt')) {
        $path = Join-Path $ImageDirectory $name
        if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -le 1048576 `
            -and (Get-Item -LiteralPath $path).LastWriteTime -ge $started) {
            # Copy-Item can deny a concurrent SDMC writer on Windows. Read one
            # shared snapshot, then save it without reopening the live file.
            $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,
                ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
            $reader=[IO.StreamReader]::new($stream)
            try{$snapshotText=$reader.ReadToEnd()}finally{$reader.Dispose()}
            [IO.File]::WriteAllText((Join-Path $run $name),$snapshotText)
        }
    }
    $log = Join-Path $userDir 'log\azahar_log.txt'
    if (Test-Path -LiteralPath $log) {
        try { Get-Content -LiteralPath $log -Tail 2000 | Set-Content -LiteralPath (Join-Path $run 'azahar_log.txt') -Encoding utf8 }
        catch [System.IO.IOException] { Write-Verbose 'Azahar is rotating its log; retry on the next poll.' }
        catch [System.ArgumentException] { Write-Verbose 'Azahar truncated its log during tail; retry on the next poll.' }
        catch [System.Management.Automation.ItemNotFoundException] { Write-Verbose 'Azahar rotated its log; retry on the next poll.' }
    }
}
Save-Manifest
Write-Output "Launched SHA256=$sourceHash PID=$($process.Id)"
Write-Output "Run directory: $run"
Write-Output 'Keyboard defaults: A = 3DS A; M = START; Ctrl+P = screenshot; Ctrl+Q = exit emulator.'
if ($Expect -eq 'None') { $manifest.result='LAUNCHED_UNVERIFIED'; Save-Manifest; return }
$timer = [Diagnostics.Stopwatch]::StartNew()
try {
    while ($timer.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $process.Refresh()
        if ($process.HasExited) { throw "Azahar exited before expected report (exit code $($process.ExitCode))" }
        Collect-Reports
        if ($Expect -eq 'Stage41' -and (Test-Path -LiteralPath (Join-Path $run 'stage4_fs.txt')) `
            -and (Test-Path -LiteralPath (Join-Path $run 'tim_test.txt'))) {
            $fs = Get-Content -LiteralPath (Join-Path $run 'stage4_fs.txt') -Raw
            $tim = Get-Content -LiteralPath (Join-Path $run 'tim_test.txt') -Raw
            if ($buildIdentity -and $fs -notmatch [regex]::Escape($buildIdentity)) { Start-Sleep -Milliseconds 250; continue }
            if ($fs -notmatch 'vram_crc=[0-9A-F]{8}' -or $tim -notmatch 'Result=(PASS|FAIL)') {
                Start-Sleep -Milliseconds 250; continue # ignore an in-progress stdio write
            }
            if ($fs -notmatch 'checkpoint=FS_DONE first_failure=0' -or $fs -notmatch 'completed=2 reads=2 uploads=4 ticks=12 vram_crc=B6E4F832') {
                throw "Stage 4.1 baseline mismatch: $fs"
            }
            if ($tim -notmatch 'PICA 2ZANKO80.TIM allocated=1 upload=1' -or $tim -notmatch 'PICA FONT16.TIM allocated=1 upload=1' -or $tim -notmatch 'Result=PASS') {
                throw 'PICA/TIM report differs from the accepted Stage 4.1 baseline'
            }
            $manifest.result='STAGE41_CPU_PICA_REPORT_PASS_VISUAL_REVIEW_REQUIRED'; break
        }
        if ($Expect -in @('Title','Scene') -and (Test-Path -LiteralPath (Join-Path $run 'stage4_status.txt'))) {
            $status = Get-Content -LiteralPath (Join-Path $run 'stage4_status.txt') -Raw
            if ($buildIdentity -and $status -notmatch ('(?m)^build=' + [regex]::Escape($buildIdentity) + '\r?$')) { Start-Sleep -Milliseconds 250; continue }
            if ($status -match 'first_failure=([1-9][0-9]*)') { throw "Title checkpoint failure: $status" }
            if ($Expect -eq 'Title' -and $status -match 'report_complete=1' -and $status -match 'checkpoint=TITLE_FRAME_SUBMITTED') {
                $manifest.result='TITLE_REPORT_READY_VISUAL_REVIEW_REQUIRED'; break
            }
            if ($Expect -eq 'Scene' -and $status -match 'report_complete=1' -and $status -match 'checkpoint=MAP0_FRAME_SUBMITTED' -and
                $status -match '(?m)^map_frames=(\d+)' -and [int]$Matches[1] -ge 60) {
                $manifest.result='MAP0_REPORT_READY_VISUAL_REVIEW_REQUIRED'; break
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if ($manifest.result -eq 'RUNNING') { throw "Timed out waiting for $Expect after $TimeoutSeconds seconds" }
    $manifest.elapsed_seconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)
    Save-Manifest
    Write-Output $manifest.result
} catch {
    Collect-Reports; $manifest.result='FAIL'; $manifest.error=$_.Exception.Message; Save-Manifest; throw
}
# Leave the owned GUI open for visual inspection. M stops homebrew cleanly;
# Ctrl+Q exits Azahar. Exit code alone is never treated as application success.
