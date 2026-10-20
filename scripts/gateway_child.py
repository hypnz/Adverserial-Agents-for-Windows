"""Start the vendor gateway with a Windows-compatible owned readiness pipe."""
import json
import os
import sys
import threading
import time

owner = int(os.environ['HERMES_ADVERSERIAL_PARENT_PID'])


def watch_owner():
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x00100000, False, owner) # SYNCHRONIZE, no mutation rights.
        if not handle: os._exit(0)
        try:
            kernel.WaitForSingleObject(handle, 0xFFFFFFFF)
        finally:
            kernel.CloseHandle(handle)
        os._exit(0)
    else:
        while True:
            try:
                os.kill(owner, 0)
            except ProcessLookupError:
                os._exit(0)
            except PermissionError:
                pass
            time.sleep(0.5)


def watch_input():
    # An inherited pipe survives Windows venv redirectors. EOF means our owner
    # closed the session, even if terminating the redirector would leave us alive.
    try:
        while sys.stdin.buffer.read(1):
            pass
    finally:
        os._exit(0)


def run_gateway():
    output = sys.stdout
    # Reserve stdout for authenticated startup records; vendor logs go to stderr.
    sys.stdout = sys.stderr
    nonce = os.environ['HERMES_ADVERSERIAL_READY_NONCE']
    read_fd, write_fd = os.pipe()

    def relay():
        with os.fdopen(read_fd, 'r', encoding='utf-8') as stream:
            line = stream.readline(1025)
        try:
            record = json.loads(line)
            if not isinstance(record, dict):
                return
            record['nonce'] = nonce
            output.write(json.dumps(record) + '\n')
            output.flush()
        except (ValueError, OSError):
            pass

    threading.Thread(target=relay, daemon=True).start()
    sys.argv = [sys.argv[0], '--port', os.environ.get('HERMES_ADVERSERIAL_SESSION_PORT', '0'), '--fallback-port', '--ready-fd', str(write_fd)]
    try:
        from adverserial_gateway.server import main
        main()
    except BaseException as error:
        # Deliberately omit exception text, paths and environment values.
        record = {'nonce': nonce, 'error': type(error).__name__}
        if isinstance(error, OSError):
            record['errno'] = error.errno
            record['winerror'] = getattr(error, 'winerror', None)
        output.write(json.dumps(record) + '\n')
        output.flush()
        raise SystemExit(1)


if __name__ == '__main__':
    threading.Thread(target=watch_owner, daemon=True).start()
    threading.Thread(target=watch_input, daemon=True).start()
    run_gateway()
