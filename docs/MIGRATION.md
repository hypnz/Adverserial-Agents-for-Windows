# Move to a new Windows PC

Reinstall the runtime on the new PC. Python virtual environments and generated
Windows executable entry points are not generally portable.

## On the old PC

1. Close all agents launched through the adapter.
2. Keep a copy of the adapter source or its release ZIP.
3. If you want existing history and profiles, copy these folders to a private
   transfer location:

   ```text
   %LOCALAPPDATA%\adverserial-hermes\profiles
   %LOCALAPPDATA%\adverserial-hermes\agents
   ```

   These directories may contain private conversation history, memories and
   agent-local data. They are not files to publish in GitHub.
4. Copy project folders separately. A Windows user environment variable storing
   your API key does not automatically migrate to a different PC.

## On the new PC

Install Python, Node.js/npm, Git and each agent CLI you intend to use. Extract
this adapter or clone its repository. Open PowerShell in the repository root.

For example, with Hermes:

```powershell
python .\scripts\setup.py --agent hermes --kit-dir "$env:USERPROFILE\adverserial-kit-hermes" --download
if ($LASTEXITCODE -ne 0) { throw 'Setup failed.' }
```

Use a new kit directory. Do not copy the old `.venv-hermes`, node_modules or the
old machine's local-config.json in place of running setup. New setup writes a
fresh configuration using the current PC's paths.

Re-enter the API key:

```powershell
$secret = Read-Host 'Adverserial API key' -AsSecureString
$env:ADVERSERIAL_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
[Environment]::SetEnvironmentVariable('ADVERSERIAL_API_KEY', $env:ADVERSERIAL_API_KEY, 'User')
```

The last line is optional and saves the key as plain text in your Windows user
environment for future terminals.

If transferring history, restore the copied `profiles` and `agents` directories
under the equivalent `%LOCALAPPDATA%\adverserial-hermes` location while agents
are closed. Back up any data already present before merging or replacing it.
A restored profile may contain paths to projects or tools on the old machine;
update those as needed. The adapter refreshes its own provider route at launch.

```powershell
python .\scripts\run.py agents
python .\scripts\run.py doctor --for-agent hermes
python .\scripts\run.py hermes --workspace "$env:USERPROFILE\Projects\MyProject"
```

Use your chosen agent name in place of `hermes`. Agents' ordinary, non-adapter
profiles are separate and need their own migration process if you also want them.

## Move only the adapter folder on the same PC

You can move the adapter while keeping its local-config.json if the external kit
stays in place. Relative paths remain anchored to the adapter root; current-user
references resolve dynamically. A kit in a custom sibling location may require
adjusting `kitDir`. After moving the kit itself, recreate its runtime with setup.
