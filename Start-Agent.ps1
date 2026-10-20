param(
 [Parameter(Mandatory=$true)][ValidateSet('hermes','claude','codex','opencode','pi','oh-my-pi','omp','kimi','zcode','deepseek-harness','dsh')][string]$Agent,
 [string]$Workspace = (Get-Location).Path,
 [string]$Profile = 'adverserial'
)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'scripts/run.py') $Agent --workspace $Workspace --profile $Profile
exit $LASTEXITCODE
