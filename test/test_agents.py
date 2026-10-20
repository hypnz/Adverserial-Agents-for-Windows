import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'bridge'))
import agents
import run
from runtime_paths import resolve_config


class AgentTests(unittest.TestCase):
    def fixture(self,temp):
        root=Path(temp);sdk=root/'kit/resources'
        for name in ('pi','oh-my-pi'):
            p=sdk/'plugins'/name/'adverserial-confidential.ts';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('// fixture')
        python=root/'kit/.venv-hermes/bin/python';python.parent.mkdir(parents=True)
        native=python.parent/('hermes-adverserial-attestation.exe' if os.name=='nt' else 'hermes-adverserial-attestation');native.write_text('fixture')
        config={'nodeBinary':sys.executable,'pythonBinary':str(python),'sdkDir':str(sdk)}
        env={**os.environ,'ADVERSERIAL_API_KEY':'local-fixture-token','ADVERSERIAL_MODEL':'lordx64/cyberglm',
             'ADVERSERIAL_GATEWAY_URL':'http://127.0.0.1:19091/v1','ADVERSERIAL_UPSTREAM_API_KEY':'fixture-BILLING-secret'}
        return config,env

    def test_all_eight_new_plans_use_local_token_and_isolated_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            for agent in agents.AGENTS:
                if agent=='hermes':continue
                with self.subTest(agent=agent):
                    home=Path(temp)/agent
                    command,child=agents.plan(agent,'/test/'+agents.AGENTS[agent],config,env,home)
                    self.assertNotIn('ADVERSERIAL_UPSTREAM_API_KEY',child)
                    self.assertNotIn('fixture-BILLING-secret',str(child))
                    self.assertEqual(child['OPENAI_BASE_URL'],env['ADVERSERIAL_GATEWAY_URL'])
                    self.assertEqual(child['OPENAI_API_KEY'],'local-fixture-token')
                    self.assertEqual(command[0],'/test/'+agents.AGENTS[agent])
                    saved=''.join(p.read_text() for p in home.rglob('*') if p.is_file())
                    self.assertNotIn('fixture-BILLING-secret',saved)
                    if agent!='zcode':self.assertNotIn('local-fixture-token',saved)
                    if agent in ('pi','oh-my-pi'):
                        self.assertTrue(child['ADVERSERIAL_VERIFY_COMMAND'].endswith('hermes-adverserial-attestation.exe' if os.name=='nt' else 'hermes-adverserial-attestation'))

    def test_failed_attestation_blocks_all_new_agents(self):
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            for agent in agents.AGENTS:
                if agent=='hermes':continue
                with self.subTest(agent=agent),patch.object(run,'bind_policy'),patch.object(run,'SessionGateway') as gateway,patch.object(run,'execute') as execute:
                    with self.assertRaisesRegex(ValueError,'Attestation did not verify'):
                        run.launch_agent_session(agent,'/fake',config,env,Path(temp)/agent,temp,verify=lambda *a,**k:1)
                    gateway.assert_not_called();execute.assert_not_called()

    def test_verified_session_orders_gateway_before_agent_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            for agent in agents.AGENTS:
                if agent=='hermes':continue
                events=[]
                class Gateway:
                    def __init__(self,*args):self.env=env
                    def __enter__(self):events.append('gateway');return self
                    def __exit__(self,*args):events.append('closed')
                def verified(*args,**kwargs):
                    self.assertNotIn('ADVERSERIAL_API_KEY',kwargs['env']);events.append('verified');return 0
                def execute(command,child,cwd,root):events.append('agent');return 0
                with self.subTest(agent=agent),patch.object(run,'bind_policy'),patch.object(run,'SessionGateway',Gateway),patch.object(run,'execute',execute):
                    self.assertEqual(run.launch_agent_session(agent,'/fake',config,env,Path(temp)/agent,temp,verify=verified),0)
                    self.assertEqual(events,['verified','gateway','agent','closed'])
                    if agent=='zcode':self.assertFalse((Path(temp)/agent/'providers.json').exists())

    def test_agent_error_still_closes_owned_gateway(self):
        events=[]
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            class Gateway:
                def __init__(self,*args):self.env=env
                def __enter__(self):return self
                def __exit__(self,*args):events.append('closed')
            with patch.object(run,'bind_policy'),patch.object(run,'SessionGateway',Gateway),patch.object(run,'execute',side_effect=OSError('fixture')):
                with self.assertRaises(OSError):run.launch_agent_session('codex','/fake',config,env,Path(temp)/'profile',temp,verify=lambda *a,**k:0)
            self.assertEqual(events,['closed'])

    def test_inventory_works_without_any_local_config_or_network(self):
        with patch('agents.shutil.which',return_value=None):
            rows=agents.inventory({'PATH':''},ROOT)
        self.assertEqual(len(rows),9);self.assertTrue(all(not x['installed'] for x in rows))

    def test_explicit_agent_path_is_anchored_to_adapter(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'a folder/cli.cmd';path.parent.mkdir();path.write_text('fixture')
            self.assertEqual(Path(agents.find_agent('pi',{},temp,'./a folder/cli.cmd')),path.resolve())

    def test_agent_profile_separation(self):
        one=agents.agent_home({'LOCALAPPDATA':'/user/data'},'pi','work')
        two=agents.agent_home({'LOCALAPPDATA':'/user/data'},'codex','work')
        self.assertNotEqual(one,two)
        with self.assertRaises(ValueError):agents.agent_home({},'pi','../default')

    def test_nonloopback_gateway_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp);env['ADVERSERIAL_GATEWAY_URL']='https://remote.example/v1'
            with self.assertRaises(ValueError):agents.plan('codex','/fake',config,env,Path(temp)/'home')

    def test_missing_windows_pi_wrapper_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            for path in Path(config['pythonBinary']).parent.glob('hermes-adverserial-attestation*'):path.unlink()
            with self.assertRaisesRegex(ValueError,'Update-Adapter'):agents.plan('pi','/fake',config,env,Path(temp)/'home')

    def test_actual_fixture_cli_receives_codex_flags_and_session_environment(self):
        if os.name=='nt':self.skipTest('POSIX fixture executable; Windows shim is inspected separately')
        with tempfile.TemporaryDirectory() as temp:
            config,env=self.fixture(temp)
            binary=Path(temp)/'cli with spaces'
            binary.write_text('#!'+sys.executable+'\nimport os,sys\nassert os.environ["OPENAI_API_KEY"]=="local-fixture-token"\nassert "ADVERSERIAL_UPSTREAM_API_KEY" not in os.environ\nassert "model_provider=\\"adverserial_confidential\\"" in sys.argv\n')
            binary.chmod(0o700)
            command,child=agents.plan('codex',binary,config,env,Path(temp)/'home')
            self.assertEqual(agents.execute(command,child,temp,ROOT),0)

if __name__=='__main__':unittest.main()
