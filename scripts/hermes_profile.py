"""Hermes 0.22.2 named provider configuration; credentials stay in the environment."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

PROVIDER = 'adverserial-confidential'
EXPECTED_REVISION = 'd923a5eb487a17c0a68801bba9ef0f56c81040a8'


def find_hermes(repo=None, explicit=None):
    if explicit:
        target = Path(explicit).expanduser().resolve()
        if not target.is_file(): raise ValueError('--hermes-bin must name an existing Hermes launcher.')
        return str(target)
    found = shutil.which('hermes')
    if found: return str(Path(found).resolve())
    candidates = []
    if repo:
        root=Path(repo)
        for name in ('hermes.exe','hermes.cmd','hermes.ps1','hermes'):
            candidates += [root/'.hermes/bin'/name,root.parent/'bin'/name]
    for candidate in candidates:
        if candidate.is_file():return str(candidate.resolve())
    raise ValueError('Hermes launcher not found. Supply --hermes-bin with the path to your existing hermes.exe/cmd.')


def profile_root(env):
    if env.get('LOCALAPPDATA'):
        return Path(env['LOCALAPPDATA']) / 'adverserial-hermes' / 'profiles'
    return Path(env.get('XDG_CONFIG_HOME', str(Path.home()/'.config'))) / 'adverserial-hermes' / 'profiles'


def profile_path(env, name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',name):
        raise ValueError('Profile name must contain only letters, digits, underscore or hyphen (1-64 characters).')
    return profile_root(env) / name


def build_config(model, url, prior=None):
    result=copy.deepcopy(prior or {})
    chosen=result.setdefault('model',{})
    if not isinstance(chosen,dict):chosen={};result['model']=chosen
    chosen.update(default=model,provider=PROVIDER)
    for field in ('base_url','api_key','api','key_env','api_key_env','openai_runtime'):
        chosen.pop(field,None)
    providers=result.setdefault('providers',{})
    if not isinstance(providers,dict):raise ValueError('Profile providers must be a JSON/YAML object.')
    providers[PROVIDER]={'base_url':url,'key_env':'ADVERSERIAL_HERMES_SESSION_KEY',
                         'api_mode':'chat_completions','context_length':1048576}
    auxiliary=result.setdefault('auxiliary',{})
    if not isinstance(auxiliary,dict):raise ValueError('Profile auxiliary configuration must be an object.')
    for task in ('compression','session_search','web_extract'):
        auxiliary.setdefault(task,{})['provider']='main'
    auxiliary.setdefault('title_generation',{}).update(provider='main',model_upgrade_enabled=False)
    result['fallback_providers']=[]
    result.pop('fallback_model',None)
    return result


def read_profile(home, python=None):
    config = Path(home)/'config.yaml'
    if not config.exists(): return {}
    content = config.read_text(encoding='utf-8-sig')
    try:
        prior = json.loads(content)
    except json.JSONDecodeError:
        env = {k:v for k,v in os.environ.items() if k not in (
            'ADVERSERIAL_API_KEY','ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN',
            'ADVERSERIAL_HERMES_SESSION_KEY','OPENAI_API_KEY')}
        parsed = subprocess.run([str(python or sys.executable), str(Path(__file__).with_name('profile_yaml.py'))],
                                input=content, capture_output=True, text=True, encoding='utf-8',
                                env=env, timeout=15)
        try:
            message = json.loads(parsed.stdout)
        except ValueError:
            raise ValueError(f'Cannot read Hermes profile {config}: YAML parser failed; config was preserved.') from None
        if message.get('error') == 'missing_parser':
            raise ValueError(f'Hermes profile {config} uses YAML. Run scripts/Update-Adapter.ps1 once to install the isolated YAML reader.')
        if parsed.returncode or 'config' not in message:
            line, column = message.get('line', 0), message.get('column', 0)
            raise ValueError(f'Invalid YAML in Hermes profile {config} (line {line}, column {column}); config was preserved.')
        prior = message['config']
    if not isinstance(prior,dict):
        raise ValueError(f'Hermes profile {config} must contain a mapping; config was preserved.')
    return prior


def write_profile(home, model, url, python=None):
    home=Path(home)
    marker=home/'.adverserial-adapter.json'
    config=home/'config.yaml'
    if home.exists() and config.exists() and not marker.exists():
        raise ValueError('Refusing to overwrite an unrelated Hermes profile. Choose another --profile name.')
    home.mkdir(parents=True,exist_ok=True)
    prior=read_profile(home,python)
    result=build_config(model,url,prior)
    # Preserve the original bytes once, including YAML comments, before migration.
    if config.exists():
        backup = home/'config.yaml.pre-yaml-fix.bak'
        try:
            with backup.open('xb') as stream: stream.write(config.read_bytes())
        except FileExistsError:
            pass
    temp=config.with_suffix('.yaml.tmp')
    temp.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    os.replace(temp,config)
    marker.write_text(json.dumps({'adapter':'adverserial-hermes','version':'2.0.0'})+'\n',encoding='utf-8')
    return result


def session_environment(base, home):
    env=dict(base)
    env['HERMES_HOME']=str(Path(home).resolve())
    env['ADVERSERIAL_HERMES_SESSION_KEY']=env['ADVERSERIAL_API_KEY']
    env['OPENAI_BASE_URL']=env['ADVERSERIAL_GATEWAY_URL']
    env['OPENAI_API_KEY']=env['ADVERSERIAL_API_KEY']
    for key in ('ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN',
                'HERMES_PROFILE','HERMES_CONFIG','HERMES_ENV','HERMES_CONFIG_PATH','HERMES_ENV_PATH'):
        env.pop(key,None)
    return env


def launch_command(binary, model, extra=(), windows=None):
    windows=os.name=='nt' if windows is None else windows
    args=['chat','--provider',PROVIDER,'--model',model]
    # These can override the route or profile already validated by this launcher.
    forbidden=('--provider','--model','--base-url','--base_url','--api-key','--api_key','--profile','-p','-m')
    for item in extra:
        if any(item==flag or item.startswith(flag+'=') or (flag in ('-m','-p') and item.startswith(flag)) for flag in forbidden):
            raise ValueError('Use this adapter\'s --model/--profile settings; route overrides are not accepted as Hermes arguments.')
    if windows and Path(binary).suffix.lower() in ('.cmd','.bat','.ps1'):
        shell=shutil.which('pwsh') or shutil.which('powershell.exe')
        if not shell:raise ValueError('PowerShell is required for this Hermes command shim.')
        return [shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(__file__).with_name('Invoke-Hermes.ps1')),
                '-HermesPath',str(binary),'-Model',model,*extra]
    return [str(binary),*args,*extra]
