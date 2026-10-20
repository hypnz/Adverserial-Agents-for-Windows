#!/usr/bin/env python3
"""Build a reproducible, allowlisted source release without local credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'.gitignore','.gitattributes','README.md','README-AGENTS.md','VALIDATION.md',
            'LICENSE','THIRD_PARTY_NOTICES.md','SECURITY.md','CONTRIBUTING.md','CHANGELOG.md',
            'package.json','core.mjs','Start-Agent.ps1','Start-Hermes.ps1'}
DIRS={'scripts','bridge','test','docs','.github'}
EXTENSIONS={'.py','.mjs','.ps1','.md','.toml','.json','.yml','.yaml','.txt'}
EXCLUDED={'__pycache__','node_modules','dist','build','.git','.state','.sessions','.ci-venv','.upstream'}


def source_files(root=None):
    root=Path(ROOT if root is None else root)
    result=[]
    for directory,names,files in os.walk(root):
        directory=Path(directory)
        names[:]=sorted(name for name in names if name not in EXCLUDED and not name.startswith('.venv')
                        and not name.endswith('.egg-info') and (directory!=root or name in DIRS))
        for name in names:
            if (directory/name).is_symlink():raise ValueError('Release source must not contain symlink directories.')
        for name in sorted(files):
            path=directory/name;relative=path.relative_to(root)
            if path.is_symlink():raise ValueError(f'Release source must not contain symlinks: {relative}')
            if path.name=='local-config.json' or path.name.startswith('.env') or path.suffix in {'.key','.pem','.pyc'}:continue
            if len(relative.parts)==1:
                if path.name not in ROOT_FILES:continue
            elif relative.parts[0] not in DIRS or path.suffix not in EXTENSIONS:continue
            result.append(path)
    result.sort(key=lambda p:p.relative_to(root).as_posix())
    return result


def build(output,expected_tag=None):
    version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',version):raise ValueError('Invalid package version.')
    if expected_tag is not None and expected_tag!='v'+version:raise ValueError('Release tag must equal v'+version)
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    archive=output/f'adverserial-agents-windows-v{version}.zip'
    files=source_files()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for path in files:
            name='adverserial-agents-windows/'+path.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3
            info.external_attr=0o100644<<16
            data=path.read_bytes()
            # Normalize git checkout line endings for deterministic source bytes.
            data=data.replace(b'\r\n',b'\n')
            bundle.writestr(info,data)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    checksums=output/'SHA256SUMS.txt'
    checksums.write_text(f'{digest}  {archive.name}\n',encoding='utf-8')
    print(json.dumps({'archive':str(archive),'sha256':digest,'files':len(files),'checksums':str(checksums)},indent=2))
    return archive


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'dist')
    parser.add_argument('--expected-tag')
    args=parser.parse_args()
    try:build(args.output_dir,args.expected_tag)
    except (ValueError,OSError) as error:parser.exit(1,str(error)+'\n')
