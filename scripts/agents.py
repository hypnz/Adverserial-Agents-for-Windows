"""Agent-specific launch plans over one owned confidential gateway."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit

from hermes_profile import profile_path
from runtime_paths import expand_path

AGENTS={'claude':'claude','codex':'codex','opencode':'opencode','pi':'pi','oh-my-pi':'omp',
        'zcode':'zcode','deepseek-harness':'dsh','hermes':'hermes','kimi':'kimi'}
ALIASES={'omp':'oh-my-pi','dsh':'deepseek-harness','deepseek':'deepseek-harness'}
CONTEXT=1048576


def agent_home(env,agent,profile):
    return profile_path(env,profile).parent.parent/'agents'/agent/'profiles'/profile


def find_agent(agent,env,root,explicit=None):
    binary=AGENTS[agent]
    override=explicit or env.get('ADVERSERIAL_'+binary.upper()+'_BIN') or env.get('ACK_'+binary.upper()+'_BIN')
    if override:
        path=expand_path(override,root,env)
        if not path.is_file(): raise ValueError(f'{agent} executable does not exist: {path}')
        return str(path)
    found=shutil.which(binary,path=env.get('PATH',''))
    if not found: raise ValueError(f'{agent} is not installed/on PATH. Install its official CLI or use --agent-bin <launcher>.')
    return str(Path(found).absolute())


def inventory(env,root):
    result=[]
    for name in AGENTS:
        try: path=find_agent(name,env,root)
        except ValueError: path=None
        result.append({'agent':name,'installed':path is not None,'path':path})
    return result


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    os.replace(temporary,path)


def plan(agent,binary,config,gateway_env,home):
    """No long-lived billing key is available here: gateway_env holds a local token."""
    env=dict(gateway_env);home=Path(home).resolve();home.mkdir(parents=True,exist_ok=True)
    for key in ('ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN',
                'HERMES_PROFILE','HERMES_CONFIG','HERMES_ENV','HERMES_CONFIG_PATH','HERMES_ENV_PATH'):
        env.pop(key,None)
    model=env['ADVERSERIAL_MODEL'];url=env['ADVERSERIAL_GATEWAY_URL'];token=env['ADVERSERIAL_API_KEY']
    parsed=urlsplit(url)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or parsed.path!='/v1' or parsed.query or parsed.fragment or parsed.username or not parsed.port:
        raise ValueError('Agent launch requires the owned IPv4 loopback gateway URL.')
    env.update(OPENAI_API_KEY=token,OPENAI_BASE_URL=url,ADVERSERIAL_NODE_EXECUTABLE=config['nodeBinary'])
    args=[];sdk=Path(config['sdkDir'])
    if agent=='claude':
        for key in tuple(env):
            if key.startswith('ANTHROPIC_') or key.startswith('CLAUDE_CODE_USE_'):env.pop(key,None)
        env.update(CLAUDE_CONFIG_DIR=str(home),ANTHROPIC_BASE_URL=url[:-3],ANTHROPIC_AUTH_TOKEN=token,
                   ANTHROPIC_API_KEY='',ANTHROPIC_MODEL=model,ANTHROPIC_SMALL_FAST_MODEL=model,
                   CLAUDE_CODE_MAX_CONTEXT_TOKENS=str(CONTEXT),CLAUDE_CODE_ENABLE_FINE_GRAINED_TOOL_STREAMING='1')
        for tier in ('OPUS','SONNET','HAIKU','FABLE'):env['ANTHROPIC_DEFAULT_'+tier+'_MODEL']=model
        args=['--model',model]
    elif agent=='codex':
        env['CODEX_HOME']=str(home)
        provider='model_providers.adverserial_confidential={name="Adverserial Confidential",base_url='+json.dumps(url)+',env_key="ADVERSERIAL_API_KEY",wire_api="responses",requires_openai_auth=false,supports_websockets=false}'
        args=['-c','model_provider="adverserial_confidential"','-c',provider,'-c','model='+json.dumps(model)]
    elif agent in ('pi','oh-my-pi'):
        extension=sdk/'plugins'/agent/'adverserial-confidential.ts'
        if not extension.is_file():raise ValueError(f'{agent} extension missing from the installed kit. Rerun setup.')
        env['PI_CODING_AGENT_DIR']=str(home)
        if agent=='oh-my-pi':env['OMP_CODING_AGENT_DIR']=str(home)
        verifier=Path(config['pythonBinary']).parent/('hermes-adverserial-attestation.exe' if os.name=='nt' else 'hermes-adverserial-attestation')
        if not verifier.is_file():raise ValueError('Run scripts/Update-Adapter.ps1 once to install the native Pi/OMP verifier wrapper.')
        env['ADVERSERIAL_VERIFY_COMMAND']=str(verifier)
        args=['--extension',str(extension),'--model','adverserial-confidential/'+model]
    elif agent=='opencode':
        # Force a complete isolated provider configuration, including discovery homes.
        env['XDG_CONFIG_HOME']=str(home/'config');env['XDG_DATA_HOME']=str(home/'data')
        env['OPENCODE_CONFIG']=str(home/'opencode.json')
        value={'$schema':'https://opencode.ai/config.json','model':'adverserial-confidential/'+model,
               'small_model':'adverserial-confidential/'+model,'enabled_providers':['adverserial-confidential'],
               'provider':{'adverserial-confidential':{'npm':'@ai-sdk/openai-compatible','name':'Adverserial Confidential',
               'options':{'baseURL':url,'apiKey':'{env:ADVERSERIAL_API_KEY}'},
               'models':{model:{'name':model,'limit':{'context':CONTEXT,'output':65536}}}}}}
        env.pop('OPENCODE_CONFIG_CONTENT',None);env.pop('OPENCODE_CONFIG_DIR',None)
        write_json(home/'opencode.json',value)
        args=['--model','adverserial-confidential/'+model]
    elif agent=='kimi':
        env['KIMI_CODE_HOME']=str(home)
        text='default_model = "adverserial_confidential"\n\n[providers.adverserial_confidential]\ntype = "openai"\nbase_url = '+json.dumps(url)+'\napi_key_env = "ADVERSERIAL_API_KEY"\n\n[models.adverserial_confidential]\nprovider = "adverserial_confidential"\nmodel = '+json.dumps(model)+'\nmax_context_size = 1048576\ncapabilities = ["thinking", "always_thinking", "tool_use"]\n'
        (home/'config.toml').write_text(text,encoding='utf-8')
        args=['--model','adverserial_confidential']
    elif agent=='zcode':
        env['ZCODE_DATA_BASE_DIR']=str(home/'data');env['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']=str(home/'providers.json')
        provider={'providerId':'adverserial-confidential','providerName':'Adverserial Confidential',
                  'config':{'group':'standard-personal','access':{'type':'api-key','apiKey':token},
                            'api':{'type':'openai-chat-completions','baseUrl':url},'personalModelIds':[model],'modelOrder':[model]}}
        write_json(home/'providers.json',{'schemaVersion':1,'config':{'providerOrder':['adverserial-confidential'],
          'providerConfigRules':{'providerRules':[provider]},'modelConfigRules':{'providerModelRules':[
          {'providerId':'adverserial-confidential','modelId':model,'config':{'properties':{'contextWindow':CONTEXT}}}],
          'manualProviderModelRules':[]},'defaultModelSelection':{'providerId':'adverserial-confidential','modelId':model}}})
    elif agent=='deepseek-harness':
        env['DSH_HOME']=str(home)
        patch=home/'cordis.patch.yml'
        # JSON is valid YAML. The official harness uses --patch for provider wiring.
        write_json(patch,[{'id':'agent-default-model','config':{'provider':'adverserial-confidential','model':model}},
          {'id':'llm-pi-ai','config':{'providers':{'adverserial-confidential':{'apiKeyEnv':'ADVERSERIAL_API_KEY',
          'api':'openai-completions','baseURL':url,'compat':{'supportsDeveloperRole':False},'models':[
          {'id':model,'name':model,'input':['text'],'contextWindow':CONTEXT,'maxTokens':65536}]}}}}])
        args=['--profile','web','--patch',str(patch),'--port','0']
    else:raise ValueError('Use the dedicated Hermes adapter for Hermes.')
    return [str(binary),*args],env


def execute(command,env,workspace,root):
    if os.name!='nt' or Path(command[0]).suffix.lower() not in ('.cmd','.bat','.ps1'):
        return subprocess.call(command,env=env,cwd=workspace)
    shell=shutil.which('pwsh') or shutil.which('powershell.exe')
    if not shell:raise ValueError('PowerShell is required for this Windows command shim.')
    # JSON argument file keeps spaces/metacharacters out of command strings.
    with tempfile.TemporaryDirectory(prefix='adverserial-agent-args-') as temp:
        path=Path(temp)/'arguments.json';path.write_text(json.dumps(command),encoding='utf-8')
        return subprocess.call([shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(root)/'scripts/Invoke-Agent.ps1'),'-ArgumentFile',str(path)],env=env,cwd=workspace)
