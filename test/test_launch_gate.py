import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run


class LaunchGateTests(unittest.TestCase):
    def test_failed_attestation_never_starts_gateway_or_hermes(self):
        with tempfile.TemporaryDirectory() as temp:
            config={'nodeBinary':'/node','pythonBinary':'/python','hermesBin':'/hermes'}
            env={'ADVERSERIAL_API_KEY':'billing','ADVERSERIAL_MODEL':'lordx64/cyberglm','OPENAI_API_KEY':'old'}
            def rejected(args,env):
                self.assertNotIn('ADVERSERIAL_API_KEY',env)
                self.assertNotIn('OPENAI_API_KEY',env)
                return 1
            with patch.object(run,'bind_policy'),patch.object(run,'SessionGateway') as gateway,patch.object(run.subprocess,'call') as cli:
                with self.assertRaises(ValueError):run.launch_session(config,env,Path(temp)/'profiles'/'test',temp,[],verify=rejected)
                gateway.assert_not_called();cli.assert_not_called()

    def test_success_launches_with_local_credential_and_cleans_owned_gateway(self):
        events=[]
        class Gateway:
            def __init__(self,python,env):self.env={**env,'ADVERSERIAL_API_KEY':'temporary','ADVERSERIAL_GATEWAY_URL':'http://127.0.0.1:9011/v1'}
            def __enter__(self):events.append('gateway');return self
            def __exit__(self,*args):events.append('closed')
        with tempfile.TemporaryDirectory() as temp:
            config={'nodeBinary':'/node','pythonBinary':'/python','hermesBin':'/hermes'}
            env={'ADVERSERIAL_API_KEY':'billing','ADVERSERIAL_MODEL':'lordx64/cyberglm'}
            home=Path(temp)/'profiles'/'adverserial'
            def verified(args,env):events.append('verified');return 0
            def launched(args,env,cwd):
                events.append('hermes')
                self.assertEqual(env['ADVERSERIAL_HERMES_SESSION_KEY'],'temporary')
                self.assertNotIn('billing',str(env))
                self.assertEqual(args[1:4],['chat','--provider','adverserial-confidential'])
                self.assertEqual(cwd,temp)
                return 0
            with patch.object(run,'bind_policy'),patch.object(run,'SessionGateway',Gateway),patch.object(run.subprocess,'call',side_effect=launched):
                self.assertEqual(run.launch_session(config,env,home,temp,[],verify=verified),0)
            self.assertEqual(events,['verified','gateway','hermes','closed'])
            self.assertNotIn('temporary',(home/'config.yaml').read_text())


if __name__=='__main__':unittest.main()
