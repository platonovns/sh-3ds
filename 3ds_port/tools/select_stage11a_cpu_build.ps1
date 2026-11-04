[CmdletBinding()]
param([ValidateSet('A','B','F1')][string]$Variant='B')
$ErrorActionPreference='Stop'
$port=Split-Path $PSScriptRoot -Parent
$folder=if($Variant -eq 'F1'){'stage11a-tracefix'}else{'stage11a-cpu-'+$Variant}
$candidate=Get-Content (Join-Path $port ('build/'+$folder+'/manifest.json')) -Raw|ConvertFrom-Json
$name=if($Variant -eq 'F1'){'silenthill_stage11a_tracefix.3dsx'}else{'silenthill_stage11a_cpu_'+$Variant+'.3dsx'}
$source=Join-Path $port ('build/'+$folder+'/'+$name)
if((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $candidate.sha256){throw 'Candidate SHA-256 mismatch'}
if(-not [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($source)).Contains($candidate.build)){throw 'Embedded build ID mismatch'}
& (Join-Path $port 'dev_server/publish.ps1') -Source $source -Build $candidate.build
