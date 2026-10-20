param([Parameter(Mandatory=$true)][string]$HermesPath)
$ErrorActionPreference = 'Stop'
& $HermesPath '--version'
exit $LASTEXITCODE
