# Adverserial Agents for Windows 2.0.0

Source and installer scripts for nine coding-agent CLI integrations through an
owned Adverserial confidential gateway. Includes dynamic paths, separate profiles,
prelaunch verification, receipt enforcement and Windows native bridge wrappers.

Download the ZIP and extract it. Follow README.md and docs/INSTALL_WINDOWS.md.
Agent CLIs, Python, Node/npm, Git, an API key and a separately installed kit are
required. The ZIP does not include the proprietary kit, model weights or a
portable prebuilt Python environment. SHA256SUMS.txt covers the source ZIP.

Existing users should retain local-config.json, copy updated scripts and bridge,
and run scripts/Update-Adapter.ps1 once. For a new PC, follow docs/MIGRATION.md
and recreate the runtime rather than copying a virtual environment.

Validation is based on local fixtures and the kit gateway suite. Read VALIDATION.md
and the actual CI results for the release tag. Real Windows end-to-end inference
across all nine agent CLIs and all model/context combinations is not established.
This is an independent adapter, not an official Adverserial AI release.
