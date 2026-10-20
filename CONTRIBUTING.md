# Development and contribution guide

## Repository layout

- `scripts/run.py`: shared verification gate and session orchestration.
- `scripts/agents.py`: generated commands, provider configuration and agent profiles.
- `scripts/hermes_profile.py`: dedicated persistent Hermes integration.
- `scripts/runtime_paths.py`: dynamic paths and compatibility with old local configs.
- `scripts/session_gateway.py`, `gateway_child.py`: owned gateway lifecycle.
- `bridge/`: pip-installed Windows console wrappers and YAML-reader dependency.
- `core.mjs`, `scripts/verify.mjs`: startup proof validation and verifier invocation.
- `test/`: local fixtures and optional exact-Hermes-source integration.
- `scripts/build_release.py`: allowlisted source ZIP and SHA-256 builder.
- `.github/workflows/`: CI and draft release automation.

## Run the CI-equivalent suite locally

Install Python, Node and Git. From the repository root:

```powershell
git init .upstream/kit
git -C .upstream/kit remote add origin https://github.com/AdverserialAI/adverserial-confidential-kit.git
git -C .upstream/kit fetch --depth 1 origin 527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9
git -C .upstream/kit checkout --detach FETCH_HEAD
python .\scripts\ci.py --kit-dir .upstream/kit
```

These initial Git setup commands assume a new `.upstream/kit` directory. For an
existing checkout, fetch/check out the pin without adding origin again.

The runner verifies the kit revision, creates `.ci-venv`, installs its Python
SDK/gateway and the adapter bridge, runs Python tests and the kit gateway suite,
runs Node tests, then builds a release. It removes billing/API key variables
from child environments. No production API key or prompt is required. Package
and source downloads still require internet access.

For the Node-only suite:

```powershell
node --test test/core.test.mjs test/policy-proof.test.mjs
```

The optional `test_exact_hermes_runtime.py` requires the exact Hermes source
commit `d923a5eb487a17c0a68801bba9ef0f56c81040a8`, its import dependencies and
OpenAI SDK 2.24.0 in the test environment. Set HERMES_TEST_SOURCE to that checkout
and run it separately. Standard CI deliberately reports it as skipped.

## Rules for changes

Preserve the verification-before-launch gate, strict loopback URLs, receipt
failure handling and session-only credentials passed to agents. Keep machine
paths and API keys out of tracked files. Test provider configurations against
local fixtures before testing real agents. Report actual CLI/platform versions
when claiming native compatibility.

A green fixture suite does not prove real CLI or production-service behavior.
Do not add production attestation/inference to ordinary pull-request CI. Changes
to the pinned upstream revision need a separate license, dependency and gateway
review; do not silently track main or bundle proprietary upstream sources.

## Pull requests

Describe the concrete problem and resulting behavior. Include relevant fixture
tests and state which platforms/CLIs you actually exercised. Use the pull-request
template. Update docs, validation notes and changelog when behavior changes.
