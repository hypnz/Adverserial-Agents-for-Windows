import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from platform_paths import environment_paths, npm_invocation


class WindowsPathsTests(unittest.TestCase):
    def test_windows_uses_real_exe_entrypoint(self):
        python, verifier = environment_paths(Path('SDK with spaces') / '.venv-omp', True)
        self.assertEqual(python.name, 'python.exe')
        self.assertEqual(python.parent.name, 'Scripts')
        self.assertEqual(verifier.name, 'hermes-adverserial-hardware-verify.exe')

    def test_posix_entrypoint_is_preserved(self):
        python, verifier = environment_paths(Path('/sdk/.venv-omp'), False)
        self.assertEqual(python.as_posix(), '/sdk/.venv-omp/bin/python')
        self.assertEqual(verifier.name, 'hermes-adverserial-hardware-verify')

    def test_windows_npm_cmd_is_replaced_with_node_script_argv(self):
        with tempfile.TemporaryDirectory(prefix='node with spaces ') as temp:
            base = Path(temp)
            node = base / 'node.exe'; node.touch()
            npm = base / 'npm.cmd'; npm.touch()
            entry = base / 'node_modules/npm/bin/npm-cli.js'
            entry.parent.mkdir(parents=True); entry.touch()
            self.assertEqual(npm_invocation(node, npm), [str(node.resolve()), str(entry.resolve())])

    def test_missing_windows_npm_entry_does_not_fall_back_to_shell(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                npm_invocation(Path(temp)/'node.exe', Path(temp)/'npm.cmd')


class InstalledBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='SDK with spaces ')
        self.sdk = Path(self.temp.name)
        self.script = self.sdk / 'typescript/bin/adverserial-hardware-verify.mjs'
        self.script.parent.mkdir(parents=True)
        self.env = dict(os.environ)
        self.env.update(ADVERSERIAL_SDK_DIR=str(self.sdk), ADVERSERIAL_NODE_BINARY=shutil.which('node'), ADVERSERIAL_API_KEY='fixture-secret-do-not-forward')
        self.entry = Path(sys.executable).parent / ('hermes-adverserial-hardware-verify.exe' if os.name == 'nt' else 'hermes-adverserial-hardware-verify')
        self.assertTrue(self.entry.is_file(), 'Install ./bridge into the test environment first')

    def tearDown(self):
        self.temp.cleanup()

    def run_bridge(self, data):
        return subprocess.run([str(self.entry)], input=data, capture_output=True, env=self.env, timeout=22)

    def test_actual_executable_forwards_stdin_and_scrubs_key(self):
        self.script.write_text("let data=''; for await(const c of process.stdin)data+=c; if(process.env.ADVERSERIAL_API_KEY)process.exit(9);const x=JSON.parse(data);console.log(JSON.stringify({verified:true,verifier:'FIXTURE ONLY',nonce:x.nonce}));")
        r = self.run_bridge(b'{"nonce":"fixture-nonce"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['nonce'], 'fixture-nonce')

    def test_kit_resources_layout_supported(self):
        target = self.sdk / 'typescript/adverserial-hardware-verify.mjs'
        target.write_text('console.log(JSON.stringify({verified:true,verifier:"FIXTURE ONLY"}));')
        r = self.run_bridge(b'{}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['verifier'], 'FIXTURE ONLY')

    def test_child_rejection_is_nonzero_with_no_stdout(self):
        self.script.write_text("console.error('reject');process.exit(2);")
        r = self.run_bridge(b'{}')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b'')

    def test_missing_script_is_rejected(self):
        r = self.run_bridge(b'{}')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b'')

    def test_excess_output_is_rejected(self):
        self.script.write_text("process.stdout.write('x'.repeat(65537));")
        r = self.run_bridge(b'{}')
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b'')

    def test_excess_input_is_rejected_before_execution(self):
        self.script.write_text("process.stdout.write('unexpected');")
        r = self.run_bridge(b'x' * (4*1024*1024+1))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b'')


if __name__ == '__main__':
    unittest.main()
