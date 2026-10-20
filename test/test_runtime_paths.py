import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_paths import resolve_config, path_reference, expand_path


class RuntimePathTests(unittest.TestCase):
    def fixture(self, base):
        root=base/'adapter with spaces';root.mkdir()
        kit=root/'adverserial-kit-hermes'
        marker=kit/'resources/plugins/adverserial-verify/bin/adverserial-verify.mjs'
        marker.parent.mkdir(parents=True);marker.write_text('// fixture')
        node=base/'node.exe';node.write_text('fixture')
        hermes=base/'hermes.exe';hermes.write_text('fixture')
        env={'USERPROFILE':str(base/'new-user'),'LOCALAPPDATA':str(base/'new-user/AppData/Local'),'PATH':''}
        config={'kitDir':'./adverserial-kit-hermes','nodeBinary':str(node),'hermesBin':str(hermes)}
        return root,kit,env,config

    def test_adapter_and_relative_kit_move_independent_of_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,kit,env,config=self.fixture(base)
            moved=base/'moved adapter';shutil.move(root,moved)
            previous=Path.cwd()
            try:
                os.chdir(base.parent)
                result=resolve_config(config,moved,env)
            finally: os.chdir(previous)
            self.assertEqual(result['kitDir'],str(moved/'adverserial-kit-hermes'))
            self.assertTrue(result['pythonBinary'].startswith(str(moved)))
            self.assertTrue(result['hardwareVerifier'].startswith(str(moved)))
            self.assertEqual(result['sdkDir'],str(moved/'adverserial-kit-hermes/resources'))

    def test_old_windows_user_config_is_rebased(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,kit,env,config=self.fixture(base)
            destination=Path(env['USERPROFILE'])/'adverserial-kit-hermes'
            destination.parent.mkdir(parents=True);shutil.move(kit,destination)
            config.update(kitDir=r'C:\Users\legacy-user\adverserial-kit-hermes',sdkDir=r'C:\Users\legacy-user\adverserial-kit-hermes\resources',pythonBinary=r'C:\Users\legacy-user\old\Scripts\python.exe')
            result=resolve_config(config,root,env)
            self.assertEqual(result['kitDir'],str(destination))
            self.assertNotIn('legacy-user',result['pythonBinary'])

    def test_current_user_hermes_discovered_when_stored_launcher_is_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,kit,env,config=self.fixture(base)
            launcher=Path(env['LOCALAPPDATA'])/'hermes/hermes-agent/.hermes/bin/hermes.exe'
            launcher.parent.mkdir(parents=True);launcher.write_text('fixture')
            config.update(hermesBin=r'C:\Users\legacy-user\old\hermes.exe',hermesDir=r'C:\Users\legacy-user\AppData\Local\hermes\hermes-agent')
            with patch('hermes_profile.shutil.which',return_value=None):
                result=resolve_config(config,root,env)
            self.assertEqual(result['hermesBin'],str(launcher))

    def test_new_references_use_current_user_variables(self):
        with tempfile.TemporaryDirectory() as temp:
            root,kit,env,config=self.fixture(Path(temp))
            value=Path(env['LOCALAPPDATA'])/'hermes/hermes-agent'
            reference=path_reference(value,root,env)
            self.assertEqual(reference,'${LOCALAPPDATA}/hermes/hermes-agent')
            self.assertEqual(expand_path(reference,root,env),value)
            self.assertEqual(path_reference(kit,root,env),'./adverserial-kit-hermes')

    def test_path_lookup_uses_runtime_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root,kit,env,config=self.fixture(Path(temp))
            node=config['nodeBinary'];hermes=config['hermesBin']
            config.update(nodeBinary='auto',hermesBin='auto')
            with patch('runtime_paths.shutil.which',side_effect=lambda name,path=None:node if name=='node' else hermes):
                result=resolve_config(config,root,env)
            self.assertEqual(result['nodeBinary'],node)
            self.assertEqual(result['hermesBin'],hermes)

    def test_missing_kit_reports_repair_and_never_uses_stale_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root,kit,env,config=self.fixture(Path(temp));shutil.rmtree(kit)
            with self.assertRaisesRegex(ValueError,'Kit not found'):
                resolve_config(config,root,env)

    def test_other_agents_do_not_require_a_hermes_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            root,kit,env,config=self.fixture(Path(temp))
            config.pop('hermesBin')
            with patch('runtime_paths.shutil.which',return_value=None):
                result=resolve_config(config,root,env,require_hermes=False)
            self.assertIsNone(result['hermesBin'])
            self.assertEqual(result['kitDir'],str(kit))

    def test_unrecognized_variable_is_not_silently_used(self):
        with self.assertRaisesRegex(ValueError,'Unknown path variable'):
            expand_path('${MISSING_PATH}/file',ROOT,{})

    def test_runtime_cli_finds_config_beside_itself_from_another_cwd(self):
        with tempfile.TemporaryDirectory() as temp:
            root,kit,env,config=self.fixture(Path(temp))
            shutil.copytree(ROOT/'scripts',root/'scripts')
            (root/'local-config.json').write_text(json.dumps(config))
            result=subprocess.run([sys.executable,str(root/'scripts/runtime_paths.py'),'--python-only'],cwd=Path(temp),env={**os.environ,**env},capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn(str(kit/'.venv-hermes'),result.stdout)

if __name__=='__main__':unittest.main()
