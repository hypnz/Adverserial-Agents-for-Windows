# Windows installation

## 1. Prepare the PC

Install Python 3.10+, Node.js 20+ including npm, Git and your chosen agent CLI
from their official distributions. Restart PowerShell after installations that
change PATH. Use the Python command that works on your PC: the examples use
`python`; `py -3` is an alternative for the adapter scripts.

```powershell
python --version
node --version
npm --version
git --version
hermes --version
```

Replace the last command with the chosen agent's version command.

## 2. Download or clone the adapter

Extract the release ZIP into a permanent directory, or clone your published
repository and open PowerShell in its root. Avoid installing a runtime in a
folder you intend to delete after setup.

## 3. Prepare the isolated kit runtime

```powershell
python .\scripts\setup.py --agent hermes --kit-dir "$env:USERPROFILE\adverserial-kit-hermes" --download
if ($LASTEXITCODE -ne 0) { throw 'Setup failed.' }
```

Use any canonical agent name accepted by `setup.py --help`. For Oh My Pi, use
`--agent oh-my-pi`; for DeepSeek Harness, use `--agent deepseek-harness`.
The shorter `omp` and `dsh` aliases are launch aliases only.

Setup downloads kit revision `527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9`, creates
its `.venv-hermes` environment, installs the Python SDK/gateway and the adapter
bridge, installs npm dependencies, and checks hardware-verifier imports. It
writes machine-local `local-config.json`, which is ignored by Git.

For an existing kit at that revision, pass its folder without `--download`.
Do not use the older `confidential-sdk` repository in its place. Setting up a
non-Hermes target does not require Hermes.

For a nonstandard Hermes launcher, append `--hermes-bin` with its actual path.
For other launchers, use `run.py --agent-bin` when launching.

## 4. Enter and optionally persist the API key

```powershell
$secret = Read-Host 'Adverserial API key' -AsSecureString
$env:ADVERSERIAL_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
```

This sets the current terminal only. To reuse it in future terminals:

```powershell
[Environment]::SetEnvironmentVariable('ADVERSERIAL_API_KEY', $env:ADVERSERIAL_API_KEY, 'User')
```

Persistent user environment variables are plain text, not encrypted storage.
To remove the persisted key later:

```powershell
[Environment]::SetEnvironmentVariable('ADVERSERIAL_API_KEY', $null, 'User')
Remove-Item Env:ADVERSERIAL_API_KEY -ErrorAction SilentlyContinue
```

## 5. Check and launch

```powershell
python .\scripts\run.py agents
python .\scripts\run.py doctor --for-agent hermes
python .\scripts\run.py hermes --workspace "$env:USERPROFILE\Projects\MyProject"
```

The workspace must already exist. Replace `hermes` in the two commands with the
chosen agent's name. Doctor's `--for-agent` uses canonical names, such as
`oh-my-pi`, while launch also accepts `omp`.

Alternatively:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Agent.ps1 -Agent hermes -Workspace "$env:USERPROFILE\Projects\MyProject"
```

## Update an existing adapter

Close agents started through the adapter. Back up your adapter folder and retain
`local-config.json`. Replace `scripts`, `bridge`, `core.mjs` and the root launchers
from the new release, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Update-Adapter.ps1
python .\scripts\run.py doctor --for-agent hermes
```

The updater resolves the existing runtime and installs the bridge into its
isolated environment. It does not install a new kit revision or upgrade agent
CLIs. When cloning/pulling updates, Git leaves ignored local-config.json intact.

## Paths and profiles

Relative configuration paths are anchored to this repository's root, independent
of the terminal's current directory. New configuration uses relative paths or
`${USERPROFILE}` / `${LOCALAPPDATA}` references where possible. Node and default
agent launchers can be discovered on PATH. Old Windows user paths are rebased
in memory; the original configuration is not automatically overwritten.

Hermes profiles: `%LOCALAPPDATA%\adverserial-hermes\profiles\<profile>`.
Other agents: `%LOCALAPPDATA%\adverserial-hermes\agents\<agent>\profiles\<profile>`.

The data folder's legacy name is intentional. Use `--profile work` for a separate
profile. Agent profiles do not automatically inherit normal agent settings or
history. Python virtual environments must be recreated if relocated.
