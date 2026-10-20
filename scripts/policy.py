"""Public policy discovery. HTTPS registry trust is explicit; no API key is used."""
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import urllib.request

REGISTRY = 'https://verify.adverserial.ai'


def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=20) as response:
        if response.geturl().split('/', 3)[:3] != url.split('/', 3)[:3]:
            raise ValueError('Policy registry redirected to a different origin.')
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError('Registry response is too large.')
        return json.loads(data)


def validate_policy(policy, model):
    if not isinstance(policy, dict):
        raise ValueError('Policy must be a JSON object.')
    if policy.get('status') != 'active' or policy.get('model_id') != model:
        raise ValueError('An active matching model policy is required.')
    keys = policy.get('receipt_keys')
    if not isinstance(keys, dict) or not keys:
        raise ValueError('Policy has no pinned receipt keys.')
    for kid, key in keys.items():
        if not isinstance(kid, str) or not kid or not isinstance(key, dict) or key.get('kty') != 'EC' or key.get('crv') != 'P-256' or 'd' in key:
            raise ValueError('Policy receipt keys must be public P-256 JWKs.')
        for axis in ('x', 'y'):
            value = key.get(axis, '')
            if not isinstance(value, str) or len(base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)) != 32:
                raise ValueError('Invalid receipt-key coordinate.')
    return policy


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.policy-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def refresh_policy(model, state_dir, fetch=fetch_json):
    if model == 'lordx64/cyberglm':
        url = REGISTRY + '/policies/production.json'
    else:
        models = fetch(REGISTRY + '/registry/models.json')
        if not isinstance(models, dict) or not isinstance(models.get('models'), list):
            raise ValueError('Invalid model registry.')
        entry = next((m for m in models.get('models', []) if isinstance(m, dict) and m.get('id') == model), None)
        ref = entry.get('policy_ref', '') if entry else ''
        if not ref.startswith('policies/') or '..' in ref or '?' in ref or '#' in ref:
            raise ValueError('Model has no acceptable policy in the public registry.')
        url = REGISTRY + '/' + ref
    policy = validate_policy(fetch(url), model)
    state_dir = Path(state_dir)
    policy_path = state_dir / 'policy.json'
    keys_path = state_dir / 'receipt-keys.json'
    # Both files are public. Write the complete policy last as the activation marker.
    write_json(keys_path, policy['receipt_keys'])
    write_json(policy_path, policy)
    return {'policyFile': str(policy_path.resolve()), 'keysFile': str(keys_path.resolve()), 'policyURL': url}
