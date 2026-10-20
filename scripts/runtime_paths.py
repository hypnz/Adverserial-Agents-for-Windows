"""Resolve configuration paths at launch, relative to this adapter or the current user."""
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil

from platform_paths import environment_paths
from hermes_profile import find_hermes

VARIABLE = re.compile(r'\$\{([A-Z_]+)\}|%([A-Z_]+)%', re.I)


def variables(root, env):
    home = env.get('USERPROFILE') or env.get('HOME') or str(Path.home())
    return {**env, 'ADAPTER_ROOT': str(Path(root).resolve()), 'USERPROFILE': home,
            'HOME': home, 'LOCALAPPDATA': env.get('LOCALAPPDATA', str(Path(home)/'AppData/Local'))}


def expand_path(value, root, env):
    if not isinstance(value, str) or not value.strip(): return None
    values = variables(root, env)
    def substitute(match):
        name = (match[1] or match[2]).upper()
        if name not in values: raise ValueError(f'Unknown path variable {name}.')
        return values[name]
    text = VARIABLE.sub(substitute, value)
    if text == '~' or text.startswith('~/') or text.startswith('~\\'):
        text = values['USERPROFILE'] + text[1:]
    path = Path(text)
    return (path if path.is_absolute() else Path(root)/path).resolve()


def path_reference(path, root, env):
    """Serialize without baking the current Windows user into managed paths."""
    path, root = Path(path).resolve(), Path(root).resolve()
    try: return './' + path.relative_to(root).as_posix()
    except ValueError: pass
    values = variables(root, env)
    for name in ('LOCALAPPDATA','USERPROFILE'):
        try: return '${' + name + '}/' + path.relative_to(Path(values[name]).resolve()).as_posix()
        except ValueError: pass
    try: return Path(os.path.relpath(path, root)).as_posix()
    except ValueError: return str(path) # A separate drive must remain explicitly addressed.


def legacy_user_path(value, root, env):
    """Rebase old C:/Users/<name>/... configs onto the current Windows profile."""
    if not value: return None
    parts = PureWindowsPath(value).parts
    if len(parts) >= 3 and parts[1].lower() == 'users':
        suffix = parts[3:]
        if len(suffix) >= 2 and tuple(x.lower() for x in suffix[:2]) == ('appdata','local'):
            return expand_path('${LOCALAPPDATA}',root,env).joinpath(*suffix[2:])
        return expand_path('${USERPROFILE}',root,env).joinpath(*suffix)
    return None


def resolve_config(config, root, env=None, require_hermes=True):
    env = dict(os.environ if env is None else env)
    root = Path(root).resolve()
    result = dict(config)
    def configured(name):
        value = config.get(name)
        return expand_path(value,root,env) if value and value != 'auto' else None
    def candidates(name):
        value = config.get(name)
        rebased = legacy_user_path(value,root,env) if value else None
        return [p for p in (rebased,configured(name)) if p is not None]
    kit_candidates = candidates('kitDir')
    kit_candidates += [p.parent for p in candidates('sdkDir')]
    # Bounded conventional locations, never a recursive scan of project files.
    kit_candidates += [root/'adverserial-kit-hermes', root.parent/'adverserial-kit-hermes',
                       root/'adverserial-confidential-kit', root.parent/'adverserial-confidential-kit',
                       expand_path('${USERPROFILE}/adverserial-kit-hermes',root,env)]
    kit = next((p for p in kit_candidates if (p/'resources/plugins/adverserial-verify/bin/adverserial-verify.mjs').is_file()),None)
    if kit is None:
        raise ValueError('Kit not found. Set kitDir in local-config.json relative to the adapter, or rerun setup.py --kit-dir <kit-folder>.')
    result['kitDir'], result['sdkDir'] = str(kit), str(kit/'resources')
    python, hardware = environment_paths(kit/'.venv-hermes',os.name=='nt')
    # All generated venv paths derive from the selected kit; never retain stale user paths.
    result['pythonBinary'], result['hardwareVerifier'] = str(python), str(hardware)
    node = configured('nodeBinary')
    if node is None or not node.is_file():
        found = shutil.which('node',path=env.get('PATH',''))
        node = Path(found).absolute() if found else None
    if node is None or not node.is_file(): raise ValueError('Node.js not found. Install Node.js or set nodeBinary in local-config.json.')
    result['nodeBinary'] = str(node)
    repos = candidates('hermesDir') + [expand_path('${LOCALAPPDATA}/hermes/hermes-agent',root,env)]
    repo = next((p for p in repos if p.is_dir()), None)
    result['hermesDir'] = str(repo) if repo else None
    binary = next((p for p in candidates('hermesBin') if p.is_file()),None)
    if binary is None:
        found = shutil.which('hermes',path=env.get('PATH',''))
        if found: binary = Path(found).absolute()
    result['hermesBin'] = str(binary) if binary else (find_hermes(repo) if require_hermes else None)
    result['configVersion'] = 2
    return result


def load_config(root, env=None, require_hermes=True):
    path = Path(root)/'local-config.json'
    try: config = json.loads(path.read_text(encoding='utf-8-sig'))
    except json.JSONDecodeError as error:
        raise ValueError(f'Invalid JSON in {path} at line {error.lineno}, column {error.colno}.') from None
    if not isinstance(config,dict): raise ValueError(f'{path} must contain an object.')
    return resolve_config(config,root,env,require_hermes=require_hermes)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--python-only',action='store_true')
    args=parser.parse_args()
    try:
        config=load_config(Path(__file__).resolve().parents[1],require_hermes=False)
        print(config['pythonBinary'] if args.python_only else json.dumps(config,indent=2))
    except (ValueError,OSError) as error:
        parser.exit(1,str(error)+'\n')
