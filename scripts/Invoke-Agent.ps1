param([Parameter(Mandatory=$true)][string]$ArgumentFile)
$ErrorActionPreference = 'Stop'
$items = @(Get-Content -LiteralPath $ArgumentFile -Raw -Encoding UTF8 | ConvertFrom-Json)
if ($items.Count -lt 1) { throw 'Missing agent executable.' }
$binary = [string]$items[0]
$agentArgs = @()
if ($items.Count -gt 1) { $agentArgs = @($items[1..($items.Count-1)]) }
& $binary @agentArgs
exit $LASTEXITCODE
