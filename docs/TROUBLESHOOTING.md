# Troubleshooting

Run `python .\scripts\run.py doctor --for-agent AGENT` first, using a canonical
agent name. Share only sanitized errors. Never paste keys or full confidential
verification evidence into issues.

## API key is missing in this terminal

Set `ADVERSERIAL_API_KEY` in the current PowerShell. A persisted user variable
is inherited by newly opened terminals; an already-open terminal may need:

```powershell
$env:ADVERSERIAL_API_KEY = [Environment]::GetEnvironmentVariable('ADVERSERIAL_API_KEY', 'User')
```

Do not print the variable to troubleshoot it.

## Kit not found or paths still point to an old machine

Run setup for the new PC, or correct `kitDir` in local-config.json. For example,
`"kitDir": "../adverserial-kit-hermes"` refers to a sibling of the adapter root.
Run setup without `--download` for an existing pinned kit. Moving only the
adapter is supported; moving its Python virtual environment requires recreation.

## Agent executable not found

Install its official CLI, reopen PowerShell, and check PATH. Run `run.py agents`.
You can supply `--agent-bin` with the actual executable/shim path or set the
corresponding `ADVERSERIAL_<BINARY>_BIN` variable. Hermes also has setup's
`--hermes-bin` option. Launcher discovery does not prove inference compatibility.

## Verified proof accepted, then gateway readiness fails

Use the current scripts, including gateway_child.py and session_gateway.py.
The adapter authenticates its private readiness record with a session nonce,
which accommodates Windows Python virtual-environment redirector processes.
Startup failures report an exception class and numeric OS codes without dumping
credentials. Include those codes in a sanitized issue. Check antivirus/firewall
logs if the reported OS error indicates a blocked local bind or process launch.

## JSON/YAML errors in the Hermes profile

Run `scripts/Update-Adapter.ps1` to install the isolated YAML reader. The adapter
accepts JSON and YAML 1.1, rejects duplicate keys, and preserves malformed files.
The error identifies the file and location. Repair that file locally. Do not
post its full contents, since it can include private settings.
The first successful refresh preserves original bytes in
`config.yaml.pre-yaml-fix.bak`.

## Native Pi/OMP verifier wrapper is missing

Run `scripts/Update-Adapter.ps1` after copying both scripts and bridge from the
release. The wrapper must be installed into the kit environment, not an unrelated
system Python. Pi/OMP also require the kit's extension resources.

## The context window shows 131k

Update hermes_profile.py from this release and restart the adapter. Its Hermes
provider sets context_length to 1048576, matching the official kit's Hermes
configuration. This client setting is not a tested maximum-size production
inference guarantee for every model.

## Attestation fails or the model is unavailable

Use `python .\scripts\run.py diagnostics` for a fresh verification result.
That operation may contact external attestation/collateral services. A model
must have an active matching policy. Do not disable verification or TLS checks
to proceed. Successful attestation does not guarantee billing authorization,
credit or inference capacity.

## A particular agent rejects flags or provider configuration

Record the agent's version, the sanitized error and the command used. The
adapter targets the kit's documented CLI formats; upstream versions can change.
The CI fixtures test generated configurations, not actual end-to-end inference
across every installed CLI. Review the agent vendor's Windows support as well.

## Locked profile or concurrent sessions

Only one session owns a given agent/profile at a time. Close the existing
session or choose another `--profile`. Different agents/profiles receive their
own gateway and token. Do not kill unrelated gateway processes to resolve a lock.
