"""One owned vendor gateway per Hermes process. No health-check adoption or shared port."""
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import threading


def stop_child(child):
    if child.stdin is not None and not child.stdin.closed:
        child.stdin.close()
    if child.poll() is None:
        try:
            child.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            pass
        child.terminate()
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill(); child.wait(timeout=5)


class SessionGateway:
    def __init__(self, python, env, command=None, timeout=15):
        self.token = secrets.token_urlsafe(32)
        self.child = None
        self.env = dict(env)
        if self.env.get('ADVERSERIAL_GATEWAY_HOST', '127.0.0.1') != '127.0.0.1':
            raise ValueError('Automatic sessions currently require IPv4 loopback (127.0.0.1).')
        key = self.env.get('ADVERSERIAL_API_KEY', '')
        if not key: raise ValueError('Set ADVERSERIAL_API_KEY in your terminal.')
        child_env = dict(self.env)
        child_env.update(ADVERSERIAL_LOCAL_GATEWAY_TOKEN=self.token, ADVERSERIAL_UPSTREAM_API_KEY=key, ADVERSERIAL_API_KEY=self.token)
        # The gateway chooses/binds the port. No find-free-port/rebind race.
        nonce = secrets.token_urlsafe(32)
        child_env['HERMES_ADVERSERIAL_READY_NONCE'] = nonce
        child_env['HERMES_ADVERSERIAL_PARENT_PID'] = str(os.getpid())
        child_env['HERMES_ADVERSERIAL_SESSION_PORT'] = self.env.get('ADVERSERIAL_GATEWAY_PORT', '0')
        child_env['ADVERSERIAL_GATEWAY_PORT'] = '8787' # Config requires positive; CLI overrides it with 0.
        command = command or [python, str(Path(__file__).with_name('gateway_child.py'))]
        self.child = subprocess.Popen(command, env=child_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                                      creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
        ready = queue.Queue(maxsize=1)
        child = self.child
        def read_ready():
            try:
                line = child.stdout.readline(1025)
                message = json.loads(line)
                ready.put(message)
                # Drain shape-only gateway logs; neither prompts nor credentials are forwarded.
                for _line in child.stdout: pass
            except (ValueError, OSError):
                try: ready.put_nowait({})
                except queue.Full: pass
            finally:
                child.stdout.close()
        self.reader = threading.Thread(target=read_ready, daemon=True)
        self.reader.start()
        try:
            try:
                result = ready.get(timeout=timeout)
            except queue.Empty:
                raise ValueError('Gateway startup timed out before readiness.') from None
            if not isinstance(result, dict) or result.get('nonce') != nonce:
                raise ValueError('Gateway child returned invalid readiness (missing session authentication).')
            if 'error' in result:
                kind = result['error']
                if not isinstance(kind, str) or not kind.isidentifier(): kind = 'StartupError'
                codes = ', '.join(f'{key}={result[key]}' for key in ('errno', 'winerror') if type(result.get(key)) is int)
                raise ValueError(f'Gateway startup failed: {kind}' + (f' ({codes})' if codes else '') + '. Run doctor and report this error.')
            port = result.get('port')
            # Windows venv python.exe may be a redirector: its child emits the
            # readiness record. Authenticate the private session, not Popen.pid.
            if type(result.get('pid')) is not int or result['pid'] <= 0 or type(port) is not int or not 1 <= port <= 65535 or child.poll() is not None:
                raise ValueError('Gateway child returned invalid readiness (invalid port/process or early exit).')
            host = child_env.get('ADVERSERIAL_GATEWAY_HOST', '127.0.0.1')
            if host not in ('127.0.0.1', '::1'): raise ValueError('Session gateways require literal loopback.')
            origin_host = '[' + host + ']' if host == '::1' else host
            self.env.update(ADVERSERIAL_GATEWAY_URL=f'http://{origin_host}:{port}/v1', ADVERSERIAL_GATEWAY_PORT=str(port), ADVERSERIAL_API_KEY=self.token)
            self.env.pop('ADVERSERIAL_UPSTREAM_API_KEY', None)
            self.env.pop('ADVERSERIAL_LOCAL_GATEWAY_TOKEN', None)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.child is not None:
            stop_child(self.child)
            self.reader.join(timeout=2)

    def __enter__(self): return self
    def __exit__(self, *_args): self.close()
