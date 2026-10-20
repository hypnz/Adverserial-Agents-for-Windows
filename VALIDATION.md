# Validation — GitHub package 2.0.0

Last local verification: 2026-10-20. This document distinguishes actual test
results from planned GitHub CI and untested production behavior.

## Results actually obtained

Test host: Linux x86_64, Python 3.12. The pinned kit's Python SDK/gateway and
the adapter bridge were installed into isolated test environments. The complete
`scripts/ci.py` runner was executed successfully against a Git checkout of
`527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9`.

| Check | Result |
| --- | --- |
| Python adapter suite | 65 discovered: 64 passed, 1 optional integration skipped |
| Official kit gateway suite | 35 passed |
| Node core / subprocess / policy-proof suite | 26 passed |
| Total executed checks | **125 passed**, 1 explicitly skipped |
| GitHub workflow syntax/static checks | actionlint 1.7.12 passed |
| Workflow and issue-template YAML parsing | Passed |
| Local Markdown links | Resolved |
| Release ZIP contents | Checked; no local config, environments or dependencies |
| Release builder reproducibility and checksum fixtures | Passed within Python suite |
| CLI/setup help and Python compilation | Passed |

GitHub action references were resolved from the official action repositories
and pinned to immutable commit SHAs. This confirms the references used while
packaging; it does not claim that the workflows have run in your repository.

## What the tests exercise

- All eight added agent launch plans, alongside the dedicated Hermes adapter.
- Isolated provider configuration and removal of the billing key from agent
  environments; ZCode's required on-disk local token is removed on normal exit.
- Attestation failure preventing both gateway and agent launch.
- Successful fixture ordering: verification, gateway, agent, gateway cleanup.
- Real Node fixture subprocesses for the attestation wrapper, with credential
  scrubbing, argument restrictions, size limits and failed-verifier handling.
- Installed hardware-bridge entry points using fixture verifier scripts.
- Fresh/pinned proof checks, model/artifact/TLS-policy mismatches, timeout,
  cancellation, invalid verifier paths and output bounds.
- Actual local kit gateways: health, separate lifecycle, occupied-port fallback,
  owner exit and redirector-compatible startup/cleanup.
- YAML profile preservation, duplicate/invalid YAML rejection, safe errors and
  retained original bytes.
- Runtime path resolution after moving the adapter, different working dirs,
  spaces, current-user substitution, legacy-user migration and missing paths.
- Source packaging that excludes synthetic private data, installed dependencies
  and environments; tag/version validation and SHA-256 output.

The real process used for the CLI argument test is a local fixture executable,
not an installed production agent. Fake receipt/error/proof data are test inputs,
not production attestations.

## Optional Hermes integration

`test_exact_hermes_runtime.py` is skipped by default. It requires the actual
Hermes source at `d923a5eb487a17c0a68801bba9ef0f56c81040a8`, its import dependencies
and OpenAI SDK 2.24.0. When configured, it tests the real resolver and SDK against
local synthetic SSE/tool fixtures. It is not a full interactive CLI test.

## Not verified by this package build

- Execution of the provided Windows/Linux GitHub Actions matrix in your repository.
- Native Windows execution of this GitHub package or the user's exact Python 3.14.7.
- Real end-to-end inference in all nine installed agent CLIs.
- Live production attestation, external collateral exchange or billable inference.
- Maximum-context production requests for each model.
- Native slash commands/skills/status badges across all agents.
- Relocation of an installed Python venv as a portable runtime.

The configured CI matrix targets Windows/Linux and Python 3.12/3.14, with Node 22.
Its first real GitHub results must be reviewed before publishing. Passing local
fixtures or CI does not establish production compatibility for every CLI version.

## References

- https://adverserial.ai/documentation
- https://github.com/AdverserialAI/adverserial-confidential-kit
- Kit runtime pin: `527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9`.

No upstream kit sources, dependency binaries, model weights, real keys, production
prompts, user profiles or confidential evidence are included in this release.
