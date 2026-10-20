#!/usr/bin/env python3
"""Adverserial multi-agent launcher for the confidential kit runtime on Windows/POSIX."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from runtime_paths import load_config
from agents import AGENTS, ALIASES, find_agent, inventory, agent_home, plan, execute
from policy import refresh_policy
from session_gateway import SessionGateway
from install_lock import installation_lock
from hermes_profile import EXPECTED_REVISION, profile_path, read_profile, write_profile, session_environment, launch_command

ROOT=Path(__file__).resolve().parents[1]
SECRET_NAMES=('ADVERSERIAL_API_KEY','ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN','ADVERSERIAL_HERMES_SESSION_KEY','OPENAI_API_KEY')


def public_env(env):return {key:value for key,value in env.items() if key not in SECRET_NAMES}


def configured_environment(config,incoming,model):
    env=dict(incoming)
    env.update(ADVERSERIAL_SDK_DIR=config['sdkDir'],ADVERSERIAL_NODE_BINARY=config['nodeBinary'],
               ADVERSERIAL_HARDWARE_VERIFIER_COMMAND=config['hardwareVerifier'],ADVERSERIAL_MODEL=model)
    env['PATH']=str(Path(config['nodeBinary']).parent)+os.pathsep+env.get('PATH','')
    remote=env.get('ADVERSERIAL_CC_API_URL') or env.get('ADVERSERIAL_API_URL') or 'https://api.adverserial.ai/v1'
    if env.get('ADVERSERIAL_CC_API_URL',remote).rstrip('/')!=env.get('ADVERSERIAL_API_URL',remote).rstrip('/'):
        raise ValueError('Remote endpoint variables disagree.')
    env['ADVERSERIAL_API_URL']=env['ADVERSERIAL_CC_API_URL']=remote
    for key in ('ADVERSERIAL_VERIFY_COMMAND','ADVERSERIAL_RECEIPT_KEYS_JSON','ADVERSERIAL_UPSTREAM_API_KEY','ADVERSERIAL_LOCAL_GATEWAY_TOKEN'):
        env.pop(key,None)
    return env


def bind_policy(env,directory):
    pins=refresh_policy(env['ADVERSERIAL_MODEL'],directory)
    env['ADVERSERIAL_RECEIPT_KEYS_FILE']=pins['keysFile']
    env['ADVERSERIAL_POLICY_FILE']=pins['policyFile']
    env['ADVERSERIAL_CACHE_FILE']=str(Path(directory)/'verdict-cache.json')


def hardware_preflight(config,env):
    script=Path(config['sdkDir'])/'typescript/adverserial-hardware-verify.mjs'
    result=subprocess.run([config['nodeBinary'],str(script),'--check-runtime'],env=public_env(env),capture_output=True,text=True,timeout=15)
    if result.returncode:raise ValueError('Kit hardware-verifier dependencies are incomplete. Rerun setup.')
    if not Path(config['hardwareVerifier']).is_file():raise ValueError('Native hardware bridge is missing. Rerun setup.')


def hermes_probe(config,env):
    with tempfile.TemporaryDirectory(prefix='hermes-probe-') as temp:
        home=Path(temp)/'profiles'/'probe';home.mkdir(parents=True)
        check_env=public_env(env);check_env['HERMES_HOME']=str(home)
        binary=config['hermesBin']
        if os.name=='nt' and Path(binary).suffix.lower() in ('.cmd','.bat','.ps1'):
            # Probe command shims through the same argument-array PowerShell relay.
            import shutil
            shell=shutil.which('pwsh') or shutil.which('powershell.exe')
            if not shell:raise ValueError('PowerShell is required for the installed Hermes shim.')
            cmd=[shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/Probe-Hermes.ps1'),'-HermesPath',binary]
        else:cmd=[binary,'--version']
        result=subprocess.run(cmd,env=check_env,capture_output=True,text=True,timeout=30)
        if result.returncode:raise ValueError('Existing Hermes version probe failed. Run hermes --version in your terminal.')
        text=result.stdout+result.stderr
        # Keep output concise; no provider credentials are passed to this probe.
        return next((line.strip() for line in text.splitlines() if 'Hermes Agent' in line),'Hermes launcher responded')


def doctor(config,env,agent='hermes'):
    if agent!='hermes':return agent_doctor(config,env,agent)
    errors=[];version=None;revision=None
    for key in ('hermesBin','nodeBinary','pythonBinary','hardwareVerifier'):
        if not Path(config.get(key,'')).is_file():errors.append(key+' is missing')
    try:hardware_preflight(config,env)
    except (ValueError,OSError,subprocess.SubprocessError) as error:errors.append(str(error))
    try:
        probe=subprocess.run([config['pythonBinary'],'-c','import adverserial_gateway.server; import hermes_adverserial_bridge'],env=public_env(env),capture_output=True,timeout=15)
        if probe.returncode:errors.append('Gateway/bridge Python import failed')
    except (OSError,subprocess.SubprocessError):errors.append('Python runtime probe failed')
    try:version=hermes_probe(config,env)
    except (ValueError,OSError,subprocess.SubprocessError) as error:errors.append(str(error))
    if config.get('hermesDir'):
        try:
            git=subprocess.run(['git','-C',config['hermesDir'],'rev-parse','HEAD'],capture_output=True,text=True,timeout=10)
            if git.returncode==0:revision=git.stdout.strip()
        except (OSError,subprocess.SubprocessError):pass
    warnings=[]
    if version and '0.22.2' not in version and revision!=EXPECTED_REVISION:warnings.append('Hermes version differs from the tested target 0.22.2.')
    if revision and revision!=EXPECTED_REVISION:warnings.append('Hermes source commit differs from the tested target; it was not modified.')
    print(json.dumps({'ready':not errors,'hermesVersion':version,'hermesRevision':revision,'kitRevision':config.get('sdkRevision'),
                      'apiKeyPresent':bool(env.get('ADVERSERIAL_API_KEY')),'warnings':warnings,'errors':errors},indent=2,ensure_ascii=False))
    return 1 if errors else 0


def agent_doctor(config,env,agent):
    errors=[];binary=None
    for key in ('nodeBinary','pythonBinary','hardwareVerifier'):
        if not Path(config.get(key,'')).is_file():errors.append(key+' is missing')
    try:hardware_preflight(config,env)
    except (ValueError,OSError,subprocess.SubprocessError) as error:errors.append(str(error))
    try:binary=find_agent(agent,env,ROOT)
    except ValueError as error:errors.append(str(error))
    try:
        probe=subprocess.run([config['pythonBinary'],'-c','import adverserial_gateway.server; import hermes_adverserial_bridge'],env=public_env(env),capture_output=True,timeout=15)
        if probe.returncode:errors.append('Gateway/bridge Python import failed')
    except (OSError,subprocess.SubprocessError):errors.append('Python runtime probe failed')
    if agent in ('pi','oh-my-pi'):
        wrapper=Path(config['pythonBinary']).parent/('hermes-adverserial-attestation.exe' if os.name=='nt' else 'hermes-adverserial-attestation')
        if not wrapper.is_file():errors.append('Native attestation wrapper missing; run Update-Adapter.ps1')
    print(json.dumps({'ready':not errors,'agent':agent,'launcher':binary,'errors':errors,
                      'validation':'Runtime preflight only; actual agent inference is not tested by doctor.'},indent=2))
    return 1 if errors else 0


def launch_session(config,env,home,workspace,extra,verify=subprocess.call):
    # One owner per persistent profile avoids racing its config and auth database.
    lock=Path(home).parent/(Path(home).name+'.launch.lock')
    with installation_lock(lock,timeout=0.2):
        read_profile(home,config['pythonBinary']) # Fail before attestation if profile parsing needs repair.
        with tempfile.TemporaryDirectory(prefix='hermes-policy-') as temp:
            bind_policy(env,temp)
            # Verification must succeed before Hermes starts. No billing/model request here.
            if verify([config['nodeBinary'],str(ROOT/'scripts/verify.mjs')],env=public_env(env)):
                raise ValueError('Attestation did not verify; Hermes was not started. Run diagnostics.')
            with SessionGateway(config['pythonBinary'],env) as gateway:
                write_profile(home,env['ADVERSERIAL_MODEL'],gateway.env['ADVERSERIAL_GATEWAY_URL'],config['pythonBinary'])
                child_env=session_environment(gateway.env,home)
                print('Hermes confidential profile: '+str(home),flush=True)
                return subprocess.call(launch_command(config['hermesBin'],env['ADVERSERIAL_MODEL'],extra),env=child_env,cwd=workspace)


def launch_agent_session(agent,binary,config,env,home,workspace,verify=subprocess.call):
    lock=Path(home).parent/(Path(home).name+'.launch.lock')
    with installation_lock(lock,timeout=0.2):
        with tempfile.TemporaryDirectory(prefix='agent-policy-') as temp:
            bind_policy(env,temp)
            if verify([config['nodeBinary'],str(ROOT/'scripts/verify.mjs')],env=public_env(env)):
                raise ValueError('Attestation did not verify; agent was not started.')
            with SessionGateway(config['pythonBinary'],env) as gateway:
                command,child_env=plan(agent,binary,config,gateway.env,home)
                print('Confidential agent: '+agent+'; profile: '+str(home),flush=True)
                try:
                    return execute(command,child_env,workspace,ROOT)
                finally:
                    # Only ZCode requires an on-disk local session token; remove
                    # its generated provider record as soon as the session ends.
                    if agent=='zcode':(Path(home)/'providers.json').unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=[*AGENTS,*ALIASES,'agents','doctor','verify','diagnostics','sync-policy','profile-path'])
    parser.add_argument('--for-agent',choices=list(AGENTS),default='hermes',help='Agent checked by doctor')
    parser.add_argument('--agent-bin',help='Explicit agent launcher; relative paths are based on the adapter')
    parser.add_argument('--model',choices=['lordx64/cyberglm','lordx64/cyberkimi'])
    parser.add_argument('--profile',default='adverserial')
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    args,extra=parser.parse_known_args()
    try:
        action=ALIASES.get(args.action,args.action)
        if action=='agents':
            print(json.dumps(inventory(os.environ,ROOT),indent=2));return 0
        config=load_config(ROOT,require_hermes=action=='hermes' or (action=='doctor' and args.for_agent=='hermes'))
        model=args.model or os.environ.get('ADVERSERIAL_MODEL','lordx64/cyberglm')
        if model not in ('lordx64/cyberglm','lordx64/cyberkimi'):raise ValueError('Unsupported model ID.')
        env=configured_environment(config,os.environ,model)
        home=profile_path(env,args.profile)
        if args.action=='profile-path':print(home);return 0
        if args.action=='doctor':return doctor(config,env,args.for_agent)
        if extra and action!='hermes':raise ValueError('Extra route arguments are only supported by the dedicated Hermes launcher.')
        binary=None
        if action in AGENTS and action!='hermes':binary=find_agent(action,env,ROOT,args.agent_bin)
        hardware_preflight(config,env)
        if action in AGENTS:
            if not env.get('ADVERSERIAL_API_KEY'):raise ValueError('Set ADVERSERIAL_API_KEY in this terminal.')
            workspace=args.workspace.expanduser().resolve()
            if not workspace.is_dir():raise ValueError('--workspace must be an existing directory.')
            if action=='hermes':return launch_session(config,env,home,workspace,extra)
            return launch_agent_session(action,binary,config,env,agent_home(env,action,args.profile),workspace)
        state=ROOT/'.state'/model.replace('/','-');bind_policy(env,state)
        if args.action=='sync-policy':print('Active policy and public keys refreshed.');return 0
        script=ROOT/'scripts/verify.mjs' if args.action=='verify' else Path(config['sdkDir'])/'plugins/adverserial-verify/bin/adverserial-verify.mjs'
        return subprocess.call([config['nodeBinary'],str(script)]+(['--json'] if args.action=='diagnostics' else []),env=public_env(env))
    except (ValueError,OSError,subprocess.SubprocessError,KeyError,TimeoutError) as error:
        print('Adverserial adapter error: '+str(error),file=sys.stderr);return 1
    except KeyboardInterrupt:return 130


if __name__=='__main__':raise SystemExit(main())
