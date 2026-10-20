#!/usr/bin/env python3
"""Prepare a separately licensed vendor SDK; never writes API keys or modifies the existing Hermes installation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv
from platform_paths import environment_paths, npm_invocation
from install_lock import installation_lock
from runtime_paths import path_reference
from hermes_profile import find_hermes
from agents import AGENTS

ROOT = Path(__file__).resolve().parents[1]
REVISION = '527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9'

def run(args, cwd=None):
    env = {key: value for key, value in os.environ.items() if key not in ('ADVERSERIAL_API_KEY', 'ADVERSERIAL_UPSTREAM_API_KEY', 'ADVERSERIAL_LOCAL_GATEWAY_TOKEN', 'ADVERSERIAL_HERMES_SESSION_KEY', 'OPENAI_API_KEY')}
    subprocess.run([str(x) for x in args], cwd=cwd, env=env, check=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-dir', '--sdk-dir', dest='kit_dir', type=Path, required=True, help='Kit checkout or a new destination for --download')
    parser.add_argument('--download', action='store_true', help='Download the pinned vendor SDK revision into a new directory')
    parser.add_argument('--skip-deps', action='store_true', help='Only write integration config; dependencies already installed')
    parser.add_argument('--agent',choices=list(AGENTS),default='hermes',help='Agent to prepare for; other agents need not install Hermes')
    parser.add_argument('--hermes-dir', type=Path, help='Existing Hermes git checkout (not modified)')
    parser.add_argument('--hermes-bin', type=Path, help='Existing Hermes executable or command shim')
    args = parser.parse_args()
    hermes_repo = args.hermes_dir or (Path(os.environ['LOCALAPPDATA'])/'hermes/hermes-agent' if os.environ.get('LOCALAPPDATA') else None)
    hermes_bin = find_hermes(hermes_repo, args.hermes_bin) if args.agent == 'hermes' or args.hermes_bin else None
    sdk = args.kit_dir.expanduser().resolve()
    node = shutil.which('node')
    npm = shutil.which('npm')
    if not node or not npm:
        raise SystemExit('Install Node.js 20+ and npm first.')
    if args.download:
        if sdk.exists():
            raise SystemExit('--download requires a new destination directory.')
        run(['git', 'init', sdk])
        run(['git', 'remote', 'add', 'origin', 'https://github.com/AdverserialAI/adverserial-confidential-kit.git'], sdk)
        run(['git', 'fetch', '--depth', '1', 'origin', REVISION], sdk)
        run(['git', 'checkout', '--detach', 'FETCH_HEAD'], sdk)
    kit = sdk
    sdk = kit / 'resources'
    bundle = sdk / 'plugins/adverserial-verify/bin/adverserial-verify.mjs'
    if not bundle.is_file():
        raise SystemExit('Kit verifier not found. Supply adverserial-confidential-kit or --download to a NEW directory.')
    environment = kit / '.venv-hermes'
    python, hardware = environment_paths(environment, os.name == 'nt')
    npm_command = npm_invocation(node, npm)
    with installation_lock(kit / '.hermes-adapter-install.lock'):
        if not args.skip_deps:
            venv.EnvBuilder(with_pip=True).create(environment)
            run([python, '-m', 'pip', 'install', sdk / 'python', sdk / 'gateway', ROOT / 'bridge'])
            run([*npm_command, 'ci'], kit)
        run([node, sdk / 'typescript/adverserial-hardware-verify.mjs', '--check-runtime'])
    if not args.skip_deps and not hardware.is_file():
        raise SystemExit('The hardware bridge executable was not installed.')
    config = {'hermesBin': hermes_bin, 'hermesDir': str(hermes_repo.resolve()) if hermes_repo else None, 'kitDir': str(kit), 'sdkDir': str(sdk), 'nodeBinary': str(Path(node).resolve()),
              'pythonBinary': str(python), 'hardwareVerifier': str(hardware),
              'sdkRevision': subprocess.check_output(['git','rev-parse','HEAD'],cwd=kit,text=True).strip()}
    config['configVersion'] = 2
    for key in ('kitDir','sdkDir','hermesDir','hermesBin','nodeBinary','pythonBinary','hardwareVerifier'):
        if config.get(key): config[key] = path_reference(config[key],ROOT,os.environ)
    config['nodeBinary'] = 'auto'
    if not args.hermes_bin: config['hermesBin'] = 'auto'
    (ROOT / 'local-config.json').write_text(json.dumps(config, indent=2) + '\n')
    print('Ready. Set ADVERSERIAL_API_KEY in your terminal; public policy and pins refresh at launch.')
    print('Check: python scripts/run.py doctor --for-agent '+args.agent)
    print('Launch: python scripts/run.py '+args.agent)

if __name__ == '__main__':
    main()
