# Security and reporting

This adapter handles credentials locally and delegates confidential transport
and receipt validation to the separately installed Adverserial kit.

- Never commit API keys, local-config.json, user profiles, evidence or private
  project data. The release builder excludes these local/runtime locations.
- User-scoped environment persistence stores an API key as plain text. It is
  optional and is not a Windows encrypted credential vault.
- Trusted agent processes receive only a local session token from this adapter;
  the owned gateway receives the billing key for upstream authorization.
- Local agent tools and the computer remain trusted. Attestation does not attest
  those tools or validate their actions.
- Do not disable TLS, use development/TOFU evidence, or bypass failed attestation.
- Native agent plugins and versions may affect UI status. A badge is not a
  replacement for the gateway's verification and receipt checks.

For a suspected vulnerability, use GitHub's private vulnerability-reporting
feature if the repository owner has enabled it. Otherwise contact the owner
through a private channel. Do not post credentials, raw attestation evidence,
or sensitive prompts in public issues. Report upstream service/SDK issues to
Adverserial through its official reporting channels.

CI uses synthetic local fixtures and no production account credentials. The
release workflow creates drafts only. Review the artifact, source and validation
results before publishing a release.
