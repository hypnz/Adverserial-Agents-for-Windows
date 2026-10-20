import base64
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from policy import validate_policy, refresh_policy
from session_gateway import SessionGateway
from run import configured_environment


def policy():
    coordinate = base64.urlsafe_b64encode(b'0' * 32).decode().rstrip('=')
    return {'status':'active', 'model_id':'lordx64/cyberglm', 'receipt_keys':{'fixture':{'kty':'EC','crv':'P-256','x':coordinate,'y':coordinate}}}


class PolicyTests(unittest.TestCase):
    def test_public_policy_is_split_into_bom_free_key_file(self):
        with tempfile.TemporaryDirectory() as temp:
            result = refresh_policy('lordx64/cyberglm', temp, fetch=lambda url:policy())
            data = Path(result['keysFile']).read_bytes()
            self.assertFalse(data.startswith(b'\xef\xbb\xbf'))
            self.assertEqual(json.loads(data), policy()['receipt_keys'])
            self.assertNotIn('apiKey', Path(result['policyFile']).read_text())

    def test_inactive_or_other_model_refused(self):
        for changes in ({'status':'inactive'}, {'model_id':'other'}, {'receipt_keys':{}}):
            with self.assertRaises(ValueError):validate_policy({**policy(), **changes}, 'lordx64/cyberglm')

    def test_private_receipt_key_is_refused(self):
        p=policy();p['receipt_keys']['fixture']['d']='private'
        with self.assertRaises(ValueError):validate_policy(p, 'lordx64/cyberglm')

    def test_unpublished_model_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):refresh_policy('lordx64/cyberkimi',temp,fetch=lambda url:{'models':[]})

    def test_registry_policy_cannot_escape_origin(self):
        with tempfile.TemporaryDirectory() as temp:
            bad={'models':[{'id':'lordx64/cyberkimi','policy_ref':'https://other/policy.json'}]}
            with self.assertRaises(ValueError):refresh_policy('lordx64/cyberkimi',temp,fetch=lambda url:bad)

    def test_network_failure_never_silently_uses_cached_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            refresh_policy('lordx64/cyberglm', temp, fetch=lambda url:policy())
            def unavailable(url): raise OSError('offline fixture')
            with self.assertRaises(OSError):refresh_policy('lordx64/cyberglm',temp,fetch=unavailable)

    def test_environment_removes_conflicting_and_upstream_credentials(self):
        config={'sdkDir':'/resources','nodeBinary':'/node','hardwareVerifier':'/bridge'}
        env=configured_environment(config,{'ADVERSERIAL_RECEIPT_KEYS_JSON':'old','ADVERSERIAL_VERIFY_COMMAND':'/old','ADVERSERIAL_UPSTREAM_API_KEY':'raw'},'lordx64/cyberglm')
        self.assertNotIn('ADVERSERIAL_RECEIPT_KEYS_JSON',env)
        self.assertNotIn('ADVERSERIAL_VERIFY_COMMAND',env)
        self.assertNotIn('ADVERSERIAL_UPSTREAM_API_KEY',env)


class GatewaySessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        keys=Path(self.temp.name)/'keys.json';keys.write_text(json.dumps(policy()['receipt_keys']))
        entry=Path(sys.executable).parent/('hermes-adverserial-hardware-verify.exe' if os.name=='nt' else 'hermes-adverserial-hardware-verify')
        self.env=dict(os.environ)
        self.env.update(ADVERSERIAL_API_KEY='fixture-billing-key',ADVERSERIAL_RECEIPT_KEYS_FILE=str(keys),ADVERSERIAL_HARDWARE_VERIFIER_COMMAND=str(entry),ADVERSERIAL_GATEWAY_HOST='127.0.0.1')
        self.env.pop('ADVERSERIAL_GATEWAY_PORT',None)

    def tearDown(self):self.temp.cleanup()

    def healthy(self, session):
        url=session.env['ADVERSERIAL_GATEWAY_URL'].replace('/v1','/healthz')
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url,timeout=3) as response:
            self.assertEqual(json.load(response)['status'],'ok')

    def test_two_real_kit_gateways_have_independent_lifecycle(self):
        first=SessionGateway(sys.executable,self.env)
        try:
            with SessionGateway(sys.executable,self.env) as second:
                self.assertNotEqual(first.env['ADVERSERIAL_GATEWAY_URL'],second.env['ADVERSERIAL_GATEWAY_URL'])
                self.assertNotEqual(first.env['ADVERSERIAL_API_KEY'],second.env['ADVERSERIAL_API_KEY'])
                self.assertNotEqual(first.env['ADVERSERIAL_API_KEY'],'fixture-billing-key')
                self.assertNotIn('ADVERSERIAL_UPSTREAM_API_KEY',first.env)
                self.healthy(first);self.healthy(second)
                first.close();self.healthy(second)
        finally:first.close()

    def test_occupied_preferred_port_is_not_adopted_or_stopped(self):
        with socket.socket() as unrelated:
            unrelated.bind(('127.0.0.1',0));unrelated.listen()
            port=unrelated.getsockname()[1]
            with SessionGateway(sys.executable,{**self.env,'ADVERSERIAL_GATEWAY_PORT':str(port)}) as session:
                self.assertNotEqual(session.env['ADVERSERIAL_GATEWAY_PORT'],str(port));self.healthy(session)
            self.assertEqual(unrelated.getsockname()[1],port)

    def test_gateway_exits_when_owner_process_dies(self):
        program = 'import os,sys;sys.path.insert(0,sys.argv[1]);from session_gateway import SessionGateway;s=SessionGateway(sys.executable,os.environ);print(s.env["ADVERSERIAL_GATEWAY_PORT"],flush=True);sys.stdin.readline();os._exit(0)'
        owner = subprocess.Popen([sys.executable,'-c',program,str(ROOT/'scripts')],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            port = int(owner.stdout.readline().strip())
            owner.stdin.write('exit\n');owner.stdin.flush();owner.wait(timeout=3)
            end=time.monotonic()+5
            while True:
                with socket.socket() as probe:
                    probe.settimeout(0.2)
                    alive=probe.connect_ex(('127.0.0.1',port))==0
                if not alive:break
                self.assertLess(time.monotonic(),end,'Gateway survived owner exit')
                time.sleep(0.1)
        finally:
            if owner.poll() is None:owner.kill();owner.wait()
            owner.stdin.close();owner.stdout.close();owner.stderr.close()

    def test_redirector_pid_differs_and_owned_gateway_still_stops(self):
        # Model the Windows venv launcher: Popen owns a redirector, which
        # inherits the private pipes into the actual Python gateway process.
        program = 'import subprocess,sys;sys.exit(subprocess.call([sys.executable,sys.argv[1]]))'
        session = SessionGateway(sys.executable, self.env, command=[
            sys.executable, '-c', program, str(ROOT/'scripts/gateway_child.py')])
        port = int(session.env['ADVERSERIAL_GATEWAY_PORT'])
        try:
            self.healthy(session)
        finally:
            session.close()
        with socket.socket() as probe:
            probe.settimeout(1)
            self.assertNotEqual(probe.connect_ex(('127.0.0.1', port)), 0)

    def test_authenticated_startup_failure_reports_safe_error_code(self):
        program = 'import os,json;print(json.dumps({"nonce":os.environ["HERMES_ADVERSERIAL_READY_NONCE"],"error":"OSError","winerror":10013,"detail":"fixture-secret"}),flush=True)'
        with self.assertRaisesRegex(ValueError, r'Gateway startup failed: OSError \(winerror=10013\)') as failure:
            SessionGateway(sys.executable,self.env,command=[sys.executable,'-c',program])
        self.assertNotIn('fixture-secret', str(failure.exception))

    def test_forged_readiness_is_rejected(self):
        with self.assertRaises(ValueError):
            SessionGateway(sys.executable,self.env,command=[sys.executable,'-c','print(\'{"pid":-1,"port":8787}\',flush=True)'])

    def test_early_gateway_exit_is_rejected(self):
        with self.assertRaises(ValueError):SessionGateway(sys.executable,self.env,command=[sys.executable,'-c','pass'])


if __name__ == '__main__':unittest.main()
