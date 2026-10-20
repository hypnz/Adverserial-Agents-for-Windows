# Adverserial Agents for Windows — 2.0.0

A shared launcher for the nine terminal agents in Adverserial's official list:
Claude Code, Codex, OpenCode, Pi, Oh My Pi, Hermes, Kimi Code, ZCode, and
DeepSeek Harness. Install each agent separately. This package configures its
connection to the confidential gateway; it does not install or modify the agents.

## Update an existing installation

Close agents running through the adapter. Replace the `scripts` and `bridge`
folders with those from the new ZIP, and add `Start-Agent.ps1`.
**Keep your existing `local-config.json` and kit installation.**
Run these commands once from the repository root (the extracted release folder):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Update-Adapter.ps1
python .\scripts\run.py agents
```

The update installs native wrappers into the kit's isolated Python environment
without changing Hermes's Python installation. The adapter still uses its legacy local data directory for compatibility
with existing profiles.

## Select and launch an agent

Run **one** of the following commands for your chosen agent:

| Agent | Command |
| --- | --- |
| Hermes | `python .\scripts\run.py hermes` |
| Claude Code | `python .\scripts\run.py claude` |
| Codex CLI | `python .\scripts\run.py codex` |
| OpenCode | `python .\scripts\run.py opencode` |
| Pi | `python .\scripts\run.py pi` |
| Oh My Pi | `python .\scripts\run.py omp` |
| Kimi Code | `python .\scripts\run.py kimi` |
| ZCode | `python .\scripts\run.py zcode` |
| DeepSeek Harness | `python .\scripts\run.py dsh` |

To check the runtime before launching:

```powershell
python .\scripts\run.py doctor --for-agent codex
```

The doctor checks the runtime and whether the launcher is installed. It does
not perform production inference or certify compatibility with every CLI version.

To select a workspace and a separate profile:

```powershell
python .\scripts\run.py pi --workspace "$env:USERPROFILE\Projects\MyProject" --profile work
```

Alternatively, use the PowerShell launcher:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Agent.ps1 -Agent pi -Profile work
```

Paths are resolved dynamically. If a CLI is not on PATH, specify its launcher:

```powershell
python .\scripts\run.py codex --agent-bin "${env:LOCALAPPDATA}\path\to\codex.exe"
```

The adapter also accepts `.cmd`, `.bat`, and `.ps1` launchers through PowerShell,
passing arguments separately. Relative `--agent-bin` paths are resolved from
the adapter folder. You can also set environment variables such as
`ADVERSERIAL_CODEX_BIN`, `ADVERSERIAL_CLAUDE_BIN`, `ADVERSERIAL_OMP_BIN`, or
`ADVERSERIAL_DSH_BIN`. Your API key remains in `ADVERSERIAL_API_KEY`, as in
an existing installation.

## What each adapter provides

| Agent | Connection |
| --- | --- |
| Hermes | Separate persistent profile, named provider, OpenAI Chat Completions |
| Claude Code | Anthropic-compatible gateway and environment overrides |
| Codex | Explicit Responses provider and separate `CODEX_HOME` |
| OpenCode | Separate provider/configuration, Chat Completions |
| Pi / OMP | Extensions from the installed kit and a native verifier wrapper |
| Kimi | Separate `KIMI_CODE_HOME` with a named OpenAI provider |
| ZCode | Personal provider configuration with a temporary loopback token |
| DeepSeek Harness | Separate `DSH_HOME` and the official provider patch format |

The gateway implements OpenAI Chat Completions, Responses, and Anthropic Messages
endpoints. Launch requires fresh, successful attestation. Each session has its
own gateway and token; the gateway validates signed inference receipts. The
actual billing key is not passed to the new agent processes.

ZCode requires its local session token to be stored in the provider configuration,
which is deleted on normal session exit. Even after a crash, the token stops
working when that session's gateway closes.

New agents use separate profiles under the adapter's local data directory.
Their normal settings, connections, and history are not copied automatically.
Existing Hermes users retain the profile already used by this adapter.
This release does not forward extra CLI arguments for the new adapters, so
those arguments cannot override the launcher's provider route.

This release does not install native slash commands or skills across all agents.
Pi and OMP use the kit's extensions. For a shared external verification command,
run `python .\scripts\run.py verify` or `python .\scripts\run.py diagnostics`.

## Fresh installation without Hermes

First install your chosen agent, Python, Node.js/npm, and Git.
Choose a new destination for the kit:

```powershell
python .\scripts\setup.py --agent codex --kit-dir "$env:USERPROFILE\adverserial-kit-hermes" --download
python .\scripts\run.py doctor --for-agent codex
```

You do not need to install Hermes to use another agent.
The `--download` option requires a new folder; omit it for an existing kit.

## Validation limits

The official agent list and reference configuration come from
[Adverserial's documentation](https://adverserial.ai/documentation) and the
Adverserial Confidential Kit.

The adapters use official CLI flags and configuration formats. They have been
checked with local fixtures on Linux; the GitHub package validation reports
125 passed checks and one optional integration skip. All actual CLIs
have not been run on Windows, and production inference has not been tested
with every agent. Compatibility also depends on the installed CLI version and
that CLI's own Windows support. The `agents` command reports launcher presence,
not verified inference functionality.
