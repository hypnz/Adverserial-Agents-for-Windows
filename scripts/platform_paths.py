"""Platform-specific paths and shell-free npm invocation."""
from pathlib import Path


def environment_paths(environment, windows):
    base = Path(environment) / ('Scripts' if windows else 'bin')
    return base / ('python.exe' if windows else 'python'), base / ('hermes-adverserial-hardware-verify.exe' if windows else 'hermes-adverserial-hardware-verify')


def npm_invocation(node, npm):
    node, npm = Path(node).resolve(), Path(npm).resolve()
    if npm.name.lower() == 'npm-cli.js':
        return [str(node), str(npm)]
    for directory in (npm.parent, node.parent):
        entry = directory / 'node_modules/npm/bin/npm-cli.js'
        if entry.is_file():
            return [str(node), str(entry)]
    if npm.suffix.lower() not in ('.cmd', '.bat', '.ps1'):
        return [str(npm)]
    raise ValueError('Cannot locate npm-cli.js. Use the standard Node.js installer with npm included.')
