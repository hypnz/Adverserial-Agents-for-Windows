"""Native console entry for Pi/OMP verifier invocation on Windows."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    try:
        env=dict(os.environ)
        node=Path(env.get('ADVERSERIAL_NODE_BINARY',''))
        sdk=Path(env.get('ADVERSERIAL_SDK_DIR',''))
        script=sdk/'plugins/adverserial-verify/bin/adverserial-verify.mjs'
        if not node.is_absolute() or not node.is_file() or not sdk.is_absolute() or not script.is_file():
            raise ValueError('Configured Node/verifier path is missing or not absolute.')
        if any(arg!='--json' for arg in sys.argv[1:]):
            raise ValueError('Only --json is supported by the attestation wrapper.')
        for name in ('ADVERSERIAL_API_KEY','ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN','ADVERSERIAL_HERMES_SESSION_KEY','OPENAI_API_KEY'):
            env.pop(name,None)
        with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
            result=subprocess.run([str(node),str(script),*sys.argv[1:]],stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                                  env=env,shell=False,timeout=35,
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0)
            out.seek(0);data=out.read(262145)
            if len(data)>262144:raise ValueError('Attestation output exceeded limit.')
            sys.stdout.buffer.write(data);sys.stdout.buffer.flush()
            if result.returncode:print('Adverserial verifier failed; see structured verdict.',file=sys.stderr)
            return result.returncode
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        print(str(error),file=sys.stderr);return 1
