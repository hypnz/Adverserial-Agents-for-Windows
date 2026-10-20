$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = & python (Join-Path $PSScriptRoot 'runtime_paths.py') --python-only
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the adapter runtime paths.' }
# Install only into the existing isolated kit venv, not the Hermes interpreter.
& $python -m pip install (Join-Path $root 'bridge')
if ($LASTEXITCODE -ne 0) { throw 'Could not install the adapter bridge and YAML reader.' }
Write-Host 'Adapter updated. Run: python .\scripts\run.py hermes'
