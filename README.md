# Adverserial Agents for Windows

A Windows-oriented launcher that connects nine installed coding-agent CLIs to
Adverserial's confidential gateway, using dynamic paths and isolated profiles.

**Independent project; not an official Adverserial AI release.** Current adapter
version: **2.0.0**. Native Windows end-to-end inference across all nine agents
has not been verified. See [validation](VALIDATION.md) for the tests actually run.

## Supported launch targets

| Agent | Launch name | Provider protocol |
| --- | --- | --- |
| Hermes | `hermes` | OpenAI Chat Completions |
| Claude Code | `claude` | Anthropic Messages |
| Codex CLI | `codex` | OpenAI Responses |
| OpenCode | `opencode` | OpenAI Chat Completions |
| Pi | `pi` | Kit extension / Chat Completions |
| Oh My Pi | `omp` | Kit extension / Chat Completions |
| Kimi Code | `kimi` | OpenAI Chat Completions |
| ZCode | `zcode` | OpenAI Chat Completions |
| DeepSeek Harness | `dsh` | Kit provider patch / Chat Completions |

Install the agent's own CLI first. The adapter reuses that installation; it does
not install, modify, or emulate the agent. Compatibility depends on its version
and its own Windows support.

## Requirements

- Windows with PowerShell; Linux is also used for fixture testing.
- Python 3.10+, Node.js 20+ with npm, and Git, available on PATH.
- At least one supported agent CLI.
- An Adverserial API key, an available model with an active policy, and sufficient
  account credit for inference.

The kit and dependencies are downloaded separately. Review their licenses and
service terms; this repository's MIT license does not license those components.

## Quick start

Extract a release ZIP or clone this repository, then open PowerShell in its root.
The following example sets up Hermes; change `--agent hermes` for another target.

```powershell
python .\scripts\setup.py --agent hermes --kit-dir "$env:USERPROFILE\adverserial-kit-hermes" --download
if ($LASTEXITCODE -ne 0) { throw 'Setup failed.' }
```

`--download` requires a new folder. For a previously installed kit, omit it.
No Hermes installation is required when setting up a different agent.

Enter your API key without placing the literal key in command history:

```powershell
$secret = Read-Host 'Adverserial API key' -AsSecureString
$env:ADVERSERIAL_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
```

Then check and launch:

```powershell
python .\scripts\run.py agents
python .\scripts\run.py doctor --for-agent hermes
python .\scripts\run.py hermes
```

To save the entered key for future terminals:

```powershell
[Environment]::SetEnvironmentVariable('ADVERSERIAL_API_KEY', $env:ADVERSERIAL_API_KEY, 'User')
```

This stores it as plain text in your Windows user environment. It is not an
encrypted credential vault. The adapter does not save the billing key in its
configuration files or include it in releases.

## How the connection works

1. Refresh the model's active policy and public receipt keys.
2. Require a fresh, pinned hardware-verification verdict before agent launch.
3. Start a dedicated loopback gateway for this session.
4. Give the agent a temporary local token; keep the billing key in the gateway.
5. Require verified final inference receipts through the kit gateway.
6. Stop the owned gateway when the agent session ends.

Failed verification blocks launch. This does not attest local agent tools,
prove their output correct, or remove the need to trust the local computer.
Native slash commands and status badges differ by agent; this repository does
not install them across all nine agents.

## Guides

- [Windows installation and configuration](docs/INSTALL_WINDOWS.md)
- [Agent commands and profile behavior](README-AGENTS.md)
- [Dynamic paths and configuration](docs/CONFIGURATION.md)
- [Move to a new PC](docs/MIGRATION.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Upload this repository to GitHub and create releases](docs/GITHUB_DEPLOYMENT.md)
- [Development, tests and contribution guide](CONTRIBUTING.md)
- [Security reporting and credential handling](SECURITY.md)
- [Third-party licenses and compatibility references](THIRD_PARTY_NOTICES.md)

## Build a release locally

No SDK, API key, GitHub account, or network access is needed to package the source:

```powershell
python .\scripts\build_release.py
```

The `dist` folder receives a source ZIP and `SHA256SUMS.txt`. This ZIP excludes
local-config.json, credentials, installed kit sources, environments and caches.
You still run setup after extracting it on a new machine.

## CI and releases

GitHub Actions is configured for Windows and Linux with Python 3.12 and 3.14.
It downloads the pinned public kit and tests local fixtures without production
API keys or production attestation requests. A matching `v*` tag starts the
release workflow, which runs checks and creates a **draft** release for review.
The workflows have not been executed in your GitHub repository yet.
