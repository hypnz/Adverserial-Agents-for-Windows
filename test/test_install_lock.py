import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = str(Path(__file__).resolve().parents[1]/'scripts')


class InstallLockTests(unittest.TestCase):
    def test_competing_installer_waits_and_crash_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            filename = str(Path(temp)/'install.lock')
            program = 'import sys,time;sys.path.insert(0,sys.argv[1]);from install_lock import installation_lock\nwith installation_lock(sys.argv[2]):\n print("locked",flush=True)\n time.sleep(20)'
            first = subprocess.Popen([sys.executable,'-c',program,SCRIPTS,filename],stdout=subprocess.PIPE,text=True)
            try:
                self.assertEqual(first.stdout.readline().strip(),'locked')
                probe = 'import sys;sys.path.insert(0,sys.argv[1]);from install_lock import installation_lock\nwith installation_lock(sys.argv[2],timeout=0.15):print("acquired")'
                second = subprocess.run([sys.executable,'-c',probe,SCRIPTS,filename],capture_output=True,text=True,timeout=3)
                self.assertNotEqual(second.returncode,0)
                first.terminate();first.wait(timeout=3)
                recovered = subprocess.run([sys.executable,'-c',probe,SCRIPTS,filename],capture_output=True,text=True,timeout=3)
                self.assertEqual(recovered.returncode,0,recovered.stderr)
                self.assertEqual(recovered.stdout.strip(),'acquired')
            finally:
                if first.poll() is None:first.kill();first.wait()
                first.stdout.close()


if __name__ == '__main__':unittest.main()
