[CmdletBinding()]
param([ValidateSet('on','off')][string]$Flashlight='on')
$ErrorActionPreference='Stop'
$port=Split-Path $PSScriptRoot -Parent
$repo=Split-Path $port -Parent
$directory=Join-Path $port ('build/stage10-r6-benchmark-8-'+$Flashlight)
$marker=Join-Path $repo 'sh1_data/stage10_cpu_audit.txt'
if(Test-Path -LiteralPath $marker){throw 'Unexpected pending CPU marker'}
[IO.File]::WriteAllText($marker,("CPU_AUDIT"+[char]10),[Text.Encoding]::ASCII)
& (Join-Path $PSScriptRoot 'run_azahar.ps1') -Target Game -Rom (Join-Path $directory 'diagnostic.3dsx') -Restart -Expect None -AutoMenu -Profile
& (Join-Path $PSScriptRoot 'qualify_stage10_pica.ps1') -ReportPrefix stage10-r6-cpu -Name ('town-'+$Flashlight) -DiagnosticDirectory $directory -ExpectedMap 10 -TimeoutSeconds 300
if(Test-Path -LiteralPath $marker){throw 'CPU audit marker was not consumed'}
