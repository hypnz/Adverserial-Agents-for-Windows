param(
    [Parameter(Mandatory=$true)][string]$HermesPath,
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$HermesArgs
)
$ErrorActionPreference = 'Stop'
& $HermesPath 'chat' '--provider' 'adverserial-confidential' '--model' $Model @HermesArgs
exit $LASTEXITCODE
