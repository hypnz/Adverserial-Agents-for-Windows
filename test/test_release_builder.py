import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_release


class ReleaseBuilderTests(unittest.TestCase):
    def fixture(self,root):
        (root/'package.json').write_text(json.dumps({'version':'2.0.0'}))
        (root/'README.md').write_text('fixture\n')
        (root/'scripts').mkdir();(root/'scripts/run.py').write_text('print("fixture")\n')
        for name in ('local-config.json','.env','secret.key'):(root/name).write_text('fixture-private-data')
        for name in ('.ci-venv','.upstream','node_modules','.state','dist'):
            folder=root/name;folder.mkdir();(folder/'private.py').write_text('fixture-private-data')

    def test_release_excludes_credentials_and_installed_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir();self.fixture(root)
            with patch.object(build_release,'ROOT',root):archive=build_release.build(Path(temp)/'out')
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()),{'adverserial-agents-windows/package.json','adverserial-agents-windows/README.md','adverserial-agents-windows/scripts/run.py'})
                self.assertNotIn(b'fixture-private-data',b''.join(z.read(n) for n in z.namelist()))
            checksum=(archive.parent/'SHA256SUMS.txt').read_text().split()[0]
            self.assertEqual(checksum,hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_same_sources_produce_same_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir();self.fixture(root)
            with patch.object(build_release,'ROOT',root):
                first=build_release.build(Path(temp)/'one').read_bytes()
                second=build_release.build(Path(temp)/'two').read_bytes()
            self.assertEqual(first,second)

    def test_wrong_release_tag_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.fixture(root)
            with patch.object(build_release,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'Release tag'):build_release.build(root/'out','v9.9.9')
