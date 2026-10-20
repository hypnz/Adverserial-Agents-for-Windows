import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from hermes_profile import build_config, read_profile, write_profile, session_environment, profile_path, launch_command


class HermesProfileTests(unittest.TestCase):
    def test_named_provider_uses_environment_pointer_not_secret(self):
        config=build_config('lordx64/cyberglm','http://127.0.0.1:9011/v1')
        provider=config['providers']['adverserial-confidential']
        self.assertEqual(provider['key_env'],'ADVERSERIAL_HERMES_SESSION_KEY')
        self.assertEqual(provider['api_mode'],'chat_completions')
        self.assertEqual(provider['context_length'],1048576)
        self.assertNotIn('api_key',provider)
        self.assertEqual(config['fallback_providers'],[])
        self.assertFalse(config['auxiliary']['title_generation']['model_upgrade_enabled'])

    def test_existing_tool_settings_survive_profile_refresh(self):
        old={'terminal':{'timeout':91},'providers':{'other':{'enabled':False},'adverserial-confidential':{'context_length':131072}},'model':{'api_key':'old','base_url':'https://old'}}
        saved=copy.deepcopy(old)
        result=build_config('lordx64/cyberglm','http://127.0.0.1:9011/v1',old)
        self.assertEqual(old,saved)
        self.assertEqual(result['terminal']['timeout'],91)
        self.assertEqual(result['providers']['adverserial-confidential']['context_length'],1048576)
        self.assertIn('other',result['providers'])
        self.assertNotIn('api_key',result['model'])
        self.assertNotIn('base_url',result['model'])

    def test_hermes_yaml_refresh_preserves_settings_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)/'profiles'/'adverserial';home.mkdir(parents=True)
            (home/'.adverserial-adapter.json').write_text('{}')
            original = '# Hermes rewrites YAML\nmodel: {default: old}\nterminal: {timeout: 91}\ncustom: {enabled: off, label: "Ελληνικά"}\n'
            config=home/'config.yaml';config.write_text(original,encoding='utf-8')
            result=write_profile(home,'lordx64/cyberglm','http://127.0.0.1:9011/v1',sys.executable)
            self.assertEqual(result['terminal']['timeout'],91)
            self.assertIs(result['custom']['enabled'],False)
            self.assertEqual(result['custom']['label'],'Ελληνικά')
            backup=home/'config.yaml.pre-yaml-fix.bak'
            self.assertEqual(backup.read_text(encoding='utf-8'),original)
            write_profile(home,'lordx64/cyberglm','http://127.0.0.1:9012/v1',sys.executable)
            self.assertEqual(backup.read_text(encoding='utf-8'),original)

    def test_invalid_yaml_is_preserved_with_path_and_safe_location(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);config=home/'config.yaml'
            (home/'.adverserial-adapter.json').write_text('{}')
            original='secret_value: fixture-private-value\nbroken: [\n'
            config.write_text(original)
            with self.assertRaises(ValueError) as failure:
                write_profile(home,'lordx64/cyberglm','http://127.0.0.1:9011/v1',sys.executable)
            self.assertIn(str(config),str(failure.exception))
            self.assertNotIn('fixture-private-value',str(failure.exception))
            self.assertEqual(config.read_text(),original)

    def test_duplicate_yaml_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'config.yaml').write_text('terminal: {timeout: 1}\nterminal: {timeout: 2}\n')
            with self.assertRaises(ValueError):read_profile(temp,sys.executable)

    def test_unrelated_profile_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp)/'profiles'/'default';home.mkdir(parents=True)
            path=home/'config.yaml';path.write_text('original')
            with self.assertRaises(ValueError):write_profile(home,'lordx64/cyberglm','http://127.0.0.1:9011/v1')
            self.assertEqual(path.read_text(),'original')

    def test_profile_parent_prevents_sticky_profile_takeover(self):
        target=profile_path({'LOCALAPPDATA':'C:/Users/fixture/AppData/Local'},'adverserial')
        self.assertEqual(target.parent.name,'profiles')
        for name in ('../default','a/b','','bad name'):
            with self.assertRaises(ValueError):profile_path({},name)

    def test_hermes_receives_only_session_key_and_profile_route(self):
        env=session_environment({'ADVERSERIAL_API_KEY':'temporary','ADVERSERIAL_UPSTREAM_API_KEY':'billing','OPENAI_API_KEY':'old','ADVERSERIAL_GATEWAY_URL':'http://127.0.0.1:9011/v1','HERMES_PROFILE':'old'},Path('/tmp/profiles/test'))
        self.assertEqual(env['OPENAI_API_KEY'],'temporary')
        self.assertEqual(env['ADVERSERIAL_HERMES_SESSION_KEY'],'temporary')
        self.assertNotIn('ADVERSERIAL_UPSTREAM_API_KEY',env)
        self.assertNotIn('HERMES_PROFILE',env)

    def test_cli_matches_supported_hermes_chat_options(self):
        cmd=launch_command('/a path/hermes.exe','lordx64/cyberglm',[],windows=False)
        self.assertEqual(cmd,['/a path/hermes.exe','chat','--provider','adverserial-confidential','--model','lordx64/cyberglm'])
        self.assertNotIn('--base-url',cmd)

    def test_hermes_route_overrides_are_rejected(self):
        for extra in (['--provider','openrouter'],['--base-url=https://other'],['--profile','default']):
            with self.assertRaises(ValueError):launch_command('/hermes','lordx64/cyberglm',extra,windows=False)

    def test_windows_shim_is_an_argument_array(self):
        with patch('shutil.which',return_value='C:/Windows/powershell.exe'):
            cmd=launch_command('C:/Program Files/Hermes/hermes.cmd','lordx64/cyberglm',windows=True)
        self.assertIn('-File',cmd)
        self.assertIn('C:/Program Files/Hermes/hermes.cmd',cmd)
        self.assertFalse(any(' -Command ' in item for item in cmd))


if __name__=='__main__':unittest.main()
