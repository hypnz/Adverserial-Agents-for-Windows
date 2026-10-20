#!/usr/bin/env python3
"""Reproduce offline-fixture CI after downloading the public pinned kit source."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parents[1]
PIN='527b9f4942d2ea1a26fdfaeebb8bddbba404bdc9'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-dir',type=Path,required=True)
    args=parser.parse_args();kit=args.kit_dir.resolve()
    if not (kit/'resources/gateway').is_dir():parser.error('Supply the pinned kit source checkout.')
    revision=subprocess.check_output(['git','-C',str(kit),'rev-parse','HEAD'],text=True).strip()
    if revision!=PIN:parser.error('Kit checkout must be '+PIN)
    env={k:v for k,v in os.environ.items() if k not in ('ADVERSERIAL_API_KEY','ADVERSERIAL_UPSTREAM_API_KEY',
         'ADVERSERIAL_LOCAL_GATEWAY_TOKEN','ADVERSERIAL_HERMES_SESSION_KEY','OPENAI_API_KEY','HERMES_TEST_SOURCE')}
    def run(command):subprocess.run([str(x) for x in command],cwd=ROOT,env=env,check=True)
    environment=ROOT/'.ci-venv';venv.EnvBuilder(with_pip=True).create(environment)
    python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    run([python,'-m','pip','install',kit/'resources/python',kit/'resources/gateway',ROOT/'bridge'])
    run([python,'-m','unittest','discover','-s','test','-p','test_*.py','-v'])
    run([python,'-m','unittest','discover','-s',kit/'resources/gateway/tests','-q'])
    run(['node','--test',*sorted((ROOT/'test').glob('*.test.mjs'))])
    run([python,ROOT/'scripts/build_release.py'])


if __name__=='__main__':main()
