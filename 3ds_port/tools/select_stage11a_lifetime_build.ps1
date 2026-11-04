[CmdletBinding()]
param([ValidateSet('Lifetime','PriorControl','FrozenR6','FrozenRecorder')][string]$Variant='Lifetime')
$ErrorActionPreference='Stop'
$port=Split-Path $PSScriptRoot -Parent
switch($Variant) {
    'Lifetime' {
        $source=Join-Path $port 'build/stage11a-lifetime/silenthill_stage11a_lifetime.3dsx'
        $candidate=Get-Content (Join-Path $port 'build/stage11a-lifetime/manifest.json') -Raw|ConvertFrom-Json
        $build=$candidate.build;$sha=$candidate.sha256
    }
    'FrozenR6' {
        $source=Join-Path $port 'build/hardware-stage10-r6-cpu-audit/silenthill_game.3dsx'
        $build='stage10.0-src-ca390b6b8b45e70c'
        $sha='43462215152cf6405aa0437ab4bbee6fd0fe27cc2ee1c339dfa4cb4f3cf42bd6'
    }
    'PriorControl' {
        $source=Join-Path $port 'build/stage11a-control-profile/silenthill_stage11a_control.3dsx'
        $build='stage11a.0-control-profile-src-91ca2ef7a9630b69'
        $sha='d2cd3cc9054abdfdcecc2121d0d5fd0ea56707ba786ffb714991895fd8585800'
    }
    'FrozenRecorder' {
        $source=Join-Path $port 'build/hardware-stage10-cpu-recorder/silenthill_cpu_recorder.3dsx'
        $build='stage10.0-cpurec-src-a5ed13f76dac9640'
        $sha='95fe9e0030bb29fb28649287ee68989a6a050bfc5a3fc8061a7ce25e16900fd3'
    }
}
if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha){throw 'Preserved binary changed'}
if(-not [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($source)).Contains($build)){throw 'Wrong original embedded source identity'}
& (Join-Path $port 'dev_server/publish.ps1') -Source $source -Build $build
