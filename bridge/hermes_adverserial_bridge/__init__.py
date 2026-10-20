"""Installed console entry point: pip generates a real .exe on Windows."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

MAX_INPUT = 4 * 1024 * 1024
MAX_OUTPUT = 64 * 1024


def command(env):
    node = Path(env.get('ADVERSERIAL_NODE_BINARY', ''))
    sdk = Path(env.get('ADVERSERIAL_SDK_DIR', ''))
    if not node.is_absolute() or not node.is_file():
        raise ValueError('ADVERSERIAL_NODE_BINARY must name an absolute Node executable.')
    if not sdk.is_absolute():
        raise ValueError('ADVERSERIAL_SDK_DIR must be an absolute directory.')
    verifier = sdk / 'typescript/adverserial-hardware-verify.mjs'
    if not verifier.is_file():
        verifier = sdk / 'typescript/bin/adverserial-hardware-verify.mjs'
    if not verifier.is_file():
        raise ValueError('The SDK hardware-verifier script is missing.')
    return [str(node.resolve()), str(verifier.resolve())]


def main():
    try:
        env = dict(os.environ)
        invocation = command(env)
        for name in ('ADVERSERIAL_API_KEY', 'ADVERSERIAL_UPSTREAM_API_KEY', 'ADVERSERIAL_LOCAL_GATEWAY_TOKEN', 'ADVERSERIAL_HERMES_SESSION_KEY', 'OPENAI_API_KEY'):
            env.pop(name, None)
        evidence = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(evidence) > MAX_INPUT:
            raise ValueError('Hardware evidence exceeds the input limit.')
        # File-backed capture bounds memory even if a broken verifier emits too much.
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            result = subprocess.run(invocation, input=evidence, stdout=stdout, stderr=stderr,
                                    env=env, shell=False, timeout=18,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
            if result.returncode:
                raise ValueError('SDK hardware verification failed.')
            stdout.seek(0)
            output = stdout.read(MAX_OUTPUT + 1)
            if len(output) > MAX_OUTPUT:
                raise ValueError('Hardware verifier output exceeds the limit.')
            sys.stdout.buffer.write(output)
            sys.stdout.buffer.flush()
        return 0
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        return 1
