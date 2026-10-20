# Third-party notices

The MIT license in this repository covers this adapter's own code and documentation.
It does not license Adverserial models, services, SDK code, agents, or dependencies.

## Adverserial Confidential Kit

- Source: https://github.com/AdverserialAI/adverserial-confidential-kit
- Runtime revision: `527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9` (ACK 0.2.5).
- The kit is downloaded separately by setup. Its sources, binaries, JavaScript
  dependencies, license and model artifacts are not included in this repository
  or the generated source release ZIP.
- Review and comply with the kit's own license and the service terms before use.
  This adapter does not grant permission to redistribute the kit or model weights.

## Other dependencies

`bridge/pyproject.toml` declares ruamel.yaml 0.18.16, installed separately under
its own license. Python, Node.js/npm, Git, agent CLIs and their dependencies retain
their own licenses. Python SDK/gateway dependencies come from the separately
installed kit. No dependency wheels or node_modules are bundled.

## Affiliation

This is an independent Windows adapter. It is not an official release of
Adverserial AI or any agent vendor. Product names identify compatibility targets.
