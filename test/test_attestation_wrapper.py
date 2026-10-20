import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class AttestationWrapperTests(unittest.TestCase):
    def invoke(self,temp,source,args=()):
        sdk=Path(temp)/'resources';script=sdk/'plugins/adverserial-verify/bin/adverserial-verify.mjs'
        script.parent.mkdir(parents=True,exist_ok=True);script.write_text(source)
        env={**os.environ,'ADVERSERIAL_NODE_BINARY':shutil.which('node'),'ADVERSERIAL_SDK_DIR':str(sdk),
             'ADVERSERIAL_API_KEY':'fixture-billing','OPENAI_API_KEY':'fixture-openai'}
        code='import sys;sys.path.insert(0,sys.argv.pop(1));from hermes_adverserial_bridge.attestation import main;sys.exit(main())'
        return subprocess.run([sys.executable,'-c',code,str(ROOT/'bridge'),*args],env=env,capture_output=True,timeout=40)

    def test_real_node_verifier_invocation_scrubs_keys_and_forwards_json(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.invoke(temp,'if(process.env.ADVERSERIAL_API_KEY||process.env.OPENAI_API_KEY)process.exit(7);console.log(JSON.stringify({fixture:true,json:process.argv.includes("--json")}));',['--json'])
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout),{'fixture':True,'json':True})

    def test_invalid_arguments_never_invoke_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.invoke(temp,'console.log("must-not-run");',['--endpoint=https://other'])
            self.assertNotEqual(result.returncode,0);self.assertNotIn(b'must-not-run',result.stdout)

    def test_oversized_output_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.invoke(temp,'console.log("x".repeat(262145));')
            self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,b'')

    def test_failed_verifier_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            result=self.invoke(temp,'console.log(JSON.stringify({verified:false}));process.exit(3);',['--json'])
            self.assertEqual(result.returncode,3);self.assertFalse(json.loads(result.stdout)['verified'])

if __name__=='__main__':unittest.main()
