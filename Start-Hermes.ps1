param([string]$Workspace = (Get-Location).Path, [string]$Profile = 'adverserial')
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'scripts/run.py') hermes --workspace $Workspace --profile $Profile
exit $LASTEXITCODE
