[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$port=Split-Path $PSScriptRoot -Parent
$cases=@(
    @('final-town-off','stage10-r6-benchmark-8-off'),
    @('final-town-on','stage10-r6-benchmark-8-on'),
    @('baseline-town-off','stage10-r6-benchmark-8-off-renderer-r5'),
    @('baseline-town-on','stage10-r6-benchmark-8-on-renderer-r5'),
    @('combat-air-after','stage10-r6-benchmark-8-off-air'),
    @('combat-air-before','stage10-r6-benchmark-8-off-air-renderer-r5'),
    @('combat-groaner-after','stage10-r6-benchmark-8-off-groaner'),
    @('combat-groaner-before','stage10-r6-benchmark-8-off-groaner-renderer-r5'))
foreach($case in $cases) {
    $directory=Join-Path $port ('build/'+$case[1])
    & (Join-Path $PSScriptRoot 'run_azahar.ps1') -Target Game -Rom (Join-Path $directory 'diagnostic.3dsx') -Restart -Expect None -AutoMenu -Profile
    & (Join-Path $PSScriptRoot 'qualify_stage10_pica.ps1') -ReportPrefix stage10-r6 -Name $case[0] -DiagnosticDirectory $directory -ExpectedMap 10 -TimeoutSeconds 300
    Write-Output ('QUALIFIED '+$case[0])
}
