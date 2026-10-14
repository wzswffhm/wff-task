"""Organizer verifier: real Windows children and pipes, never candidate internals."""
import argparse
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess as trusted
import sys
import threading
import time
import uuid

CASES = [
    ('stdout-capture', 'F2P', 'R1'), ('stderr-capture', 'F2P', 'R1'),
    ('stdout-timed', 'F2P', 'R1'), ('stderr-timed', 'F2P', 'R1'),
    ('merged-invalid', 'F2P', 'R1'), ('ascii-invalid', 'F2P', 'R1'),
    ('both-invalid', 'F2P', 'R2'), ('drain-peer', 'F2P', 'R2'),
    ('retry-invalid', 'F2P', 'R3'), ('retry-stderr', 'F2P', 'R3'),
    ('repeat-error', 'F2P', 'R3'), ('run-timeout-invalid', 'F2P', 'R4'),
    ('bytes-invalid', 'P2P', 'R5'), ('replace-errors', 'P2P', 'R5'),
    ('ignore-errors', 'P2P', 'R5'), ('backslash-errors', 'P2P', 'R5'),
    ('valid-newlines', 'P2P', 'R5'), ('empty-pipes', 'P2P', 'R5'),
    ('stdin-roundtrip', 'P2P', 'R5'), ('check-exit', 'P2P', 'R5'),
    ('single-pipe', 'P2P', 'R5'), ('retry-valid', 'P2P', 'R3'),
    ('run-timeout-bytes', 'P2P', 'R4'), ('uncaptured-stream', 'P2P', 'R5'),
    ('retry-both-invalid', 'F2P', 'R2'), ('run-check-invalid', 'F2P', 'R4'),
    ('utf16-invalid', 'F2P', 'R1'), ('stdin-invalid', 'F2P', 'R4'),
    ('repeat-valid', 'P2P', 'R3'), ('reader-baseexception', 'F2P', 'R2'),
    ('strict-errors', 'F2P', 'R4'), ('completion-order-error', 'F2P', 'R2'), ('completion-order-timeout-retry', 'F2P', 'R3'), ('completion-order-reversed', 'F2P', 'R2'), ('reader-close-baseexception', 'F2P', 'R2'),
]

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def load_candidate(workspace):
    spec = importlib.util.spec_from_file_location('candidate_subprocess', Path(workspace) / 'Lib' / 'subprocess.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def command(code):
    return [sys.executable, '-I', '-c', code]

def writer(stdout=b'', stderr=b'', exitcode=0):
    return command(f'import os,sys;os.write(1,{stdout!r});os.write(2,{stderr!r});sys.exit({exitcode})')

def expected_error(call, raw, encoding='utf-8'):
    try:
        raw.decode(encoding)
    except UnicodeDecodeError as oracle:
        expected = (oracle.encoding, oracle.object, oracle.start, oracle.end, oracle.reason)
    else:
        raise RuntimeError('invalid verifier fixture')
    try:
        call()
    except UnicodeDecodeError as actual:
        require((actual.encoding, actual.object, actual.start, actual.end, actual.reason) == expected,
                'decode exception does not retain its original attributes')
    else:
        raise AssertionError('caller did not receive UnicodeDecodeError')

class Event:
    """A real named Win32 event gates EOF for deterministic timeout/retry tests."""
    def __init__(self):
        self.name = 'Local\\harbor-pipe-' + uuid.uuid4().hex
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
        self.api.CreateEventW.restype = ctypes.c_void_p
        self.api.SetEvent.argtypes = [ctypes.c_void_p]
        self.api.CloseHandle.argtypes = [ctypes.c_void_p]
        self.handle = self.api.CreateEventW(None, True, False, self.name)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
    def release(self):
        if not self.api.SetEvent(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())
    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

def gated_writer(event, stdout, stderr):
    code = f'''import ctypes,os
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenEventW.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_wchar_p]
k.OpenEventW.restype=ctypes.c_void_p
k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint]
k.CloseHandle.argtypes=[ctypes.c_void_p]
h=k.OpenEventW(0x100000,False,{event.name!r})
if not h: raise ctypes.WinError(ctypes.get_last_error())
os.write(1,{stdout!r})
os.write(2,{stderr!r})
r=k.WaitForSingleObject(h,10000)
k.CloseHandle(h)
if r!=0: raise RuntimeError('fixture event never released')
'''
    return command(code)

def one_case(identifier, workspace):
    s = load_candidate(workspace)
    unhandled = []
    old_hook = threading.excepthook
    threading.excepthook = lambda args: unhandled.append(type(args.exc_value).__name__)
    before_threads = {id(t) for t in threading.enumerate()}
    children = []
    events = []
    def popen(argv, **kw):
        process = s.Popen(argv, **kw)
        children.append(process)
        return process
    def captured_error(stdout, stderr, **kw):
        p = popen(writer(stdout, stderr), stdout=s.PIPE, stderr=s.PIPE, encoding=kw.pop('encoding', 'utf-8'))
        raw = stdout if b'\xff' in stdout else stderr
        expected_error(lambda: p.communicate(**kw), raw)
        require(p.stdout.closed and p.stderr.closed, 'pipes were not closed on failure')
        require(p.wait(timeout=3) == 0, 'child did not finish normally')
    try:
        bad_out, bad_err = b'out:\xff\n', b'err:\xff\n'
        if identifier in ('stdout-capture', 'stderr-capture', 'stdout-timed', 'stderr-timed'):
            out = bad_out if identifier.startswith('stdout') else b'out:ok\n'
            err = bad_err if identifier.startswith('stderr') else b'err:ok\n'
            captured_error(out, err, **({'timeout': 5} if identifier.endswith('timed') else {}))
        elif identifier == 'merged-invalid':
            p = popen(writer(b'', bad_err), stdout=s.PIPE, stderr=s.STDOUT, encoding='utf-8')
            expected_error(lambda: p.communicate(timeout=5), bad_err)
            require(p.stdout.closed, 'merged pipe not closed')
        elif identifier == 'ascii-invalid':
            raw = b'ascii:\x80\n'
            p = popen(writer(raw), stdout=s.PIPE, stderr=s.PIPE, encoding='ascii')
            expected_error(lambda: p.communicate(timeout=5), raw, 'ascii')
        elif identifier == 'both-invalid':
            p = popen(writer(bad_out, bad_err), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object in (bad_out, bad_err), 'dual decode error lost original bytes')
            else:
                raise AssertionError('dual-invalid fixture did not raise')
            require(p.stdout.closed and p.stderr.closed, 'dual-invalid pipes remain open')
            require(p.wait(timeout=3) == 0, 'dual-invalid child did not finish')
        elif identifier == 'drain-peer':
            # A peer stream larger than the Windows pipe buffer must still finish.
            fixture = Path(workspace) / 'Tools' / 'large_peer_writer.py'
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_text("import os\nos.write(1,b'out:\\xff\\n')\nfor _ in range(128): os.write(2,b'x'*4096)\n", encoding='utf-8')
            p = popen([sys.executable, '-I', str(fixture)], stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            expected_error(lambda: p.communicate(timeout=5), bad_out)
            require(p.wait(timeout=3) == 0, 'peer stream did not drain')
            require(p.stdout.closed and p.stderr.closed, 'peer pipes remain open')
        elif identifier in ('retry-invalid', 'retry-stderr', 'retry-valid'):
            event = Event(); events.append(event)
            out = bad_out if identifier == 'retry-invalid' else b'out:ok\r\n'
            err = bad_err if identifier == 'retry-stderr' else b'err:ok\r\n'
            p = popen(gated_writer(event, out, err), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=0.1)
            except s.TimeoutExpired:
                pass
            else:
                raise AssertionError('unfinished gated writer did not time out')
            require(not p.stdout.closed and not p.stderr.closed, 'timeout closed retryable pipes')
            event.release()
            if identifier == 'retry-valid':
                require(p.communicate(timeout=5) == ('out:ok\n', 'err:ok\n'), 'retry lost or duplicated data')
            else:
                expected_error(lambda: p.communicate(timeout=5), out if identifier == 'retry-invalid' else err)
            require(p.wait(timeout=3) == 0, 'retry child did not exit')
            require(p.stdout.closed and p.stderr.closed, 'retry pipes remain open')
        elif identifier == 'repeat-error':
            p = popen(writer(bad_out), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            expected_error(lambda: p.communicate(timeout=5), bad_out)
            expected_error(lambda: p.communicate(timeout=5), bad_out)
        elif identifier == 'run-timeout-invalid':
            # run() reports the normal timeout, retaining undecoded diagnostic bytes.
            argv = command("import os,time;os.write(1,b'bad:\\xff');time.sleep(10)")
            try:
                s.run(argv, capture_output=True, encoding='utf-8', timeout=0.2)
            except UnicodeDecodeError as exc:
                require(exc.encoding == 'utf-8', 'run raised an unrelated decoding error')
            except s.TimeoutExpired as exc:
                require(exc.cmd == argv and exc.timeout == 0.2, 'original timeout identity changed')
                require(exc.stdout == b'bad:\\xff' and exc.stderr == b'', 'timeout must retain raw diagnostic bytes')
            else:
                raise AssertionError('run did not raise TimeoutExpired')
        elif identifier == 'bytes-invalid':
            result = s.run(writer(bad_out, bad_err), capture_output=True, timeout=5)
            require((result.stdout, result.stderr, result.returncode) == (bad_out, bad_err, 0), 'bytes were altered')
        elif identifier in ('replace-errors', 'ignore-errors', 'backslash-errors'):
            handler = {'replace-errors':'replace', 'ignore-errors':'ignore', 'backslash-errors':'backslashreplace'}[identifier]
            result = s.run(writer(bad_out, bad_err), capture_output=True, encoding='utf-8', errors=handler, timeout=5)
            require((result.stdout, result.stderr) == (bad_out.decode('utf-8', handler), bad_err.decode('utf-8', handler)), 'errors handler changed')
        elif identifier == 'valid-newlines':
            raw = '中文\r\nsecond\rlast\n'.encode('utf-8')
            result = s.run(writer(raw, raw), capture_output=True, text=True, encoding='utf-8', timeout=5)
            require((result.stdout, result.stderr) == ('中文\nsecond\nlast\n',)*2, 'text/newline conversion changed')
        elif identifier == 'empty-pipes':
            result = s.run(writer(), capture_output=True, encoding='utf-8', timeout=5)
            require((result.stdout, result.stderr) == ('',''), 'empty captured output must remain empty strings')
        elif identifier == 'stdin-roundtrip':
            argv = command('import sys;data=sys.stdin.buffer.read();sys.stdout.buffer.write(data);sys.stderr.buffer.write(data)')
            result = s.run(argv, input='输入\n'*20000, capture_output=True, encoding='utf-8', timeout=5)
            require((result.stdout,result.stderr) == ('输入\n'*20000,)*2, 'stdin/output roundtrip changed')
        elif identifier == 'check-exit':
            try:
                s.run(writer(b'out', b'err', 7), capture_output=True, check=True, timeout=5)
            except s.CalledProcessError as exc:
                require((exc.returncode,exc.stdout,exc.stderr)==(7,b'out',b'err'), 'check exception contract changed')
            else:
                raise AssertionError('nonzero check did not raise')
        elif identifier == 'single-pipe':
            result = s.run(writer(b'hello'), stdout=s.PIPE, encoding='utf-8')
            require((result.stdout,result.stderr)==('hello',None), 'single-pipe path changed')
        elif identifier == 'run-timeout-bytes':
            argv = command("import os,time;os.write(1,b'partial');time.sleep(10)")
            try:
                s.run(argv, capture_output=True, timeout=0.8)
            except s.TimeoutExpired as exc:
                require((exc.stdout, exc.stderr)==(b'partial',b''), 'timeout no longer collects binary output')
            else:
                raise AssertionError('missing timeout')
        elif identifier == 'uncaptured-stream':
            result = s.run(writer(b'hello'), stdout=s.PIPE, stderr=s.DEVNULL, timeout=5)
            require((result.stdout,result.stderr)==(b'hello',None), 'uncaptured stream should stay None')
        elif identifier == 'retry-both-invalid':
            event = Event(); events.append(event)
            out, err = b'out:\xff\n', b'err:\xfe\n'
            p = popen(gated_writer(event, out, err), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=0.1)
            except s.TimeoutExpired:
                pass
            else:
                raise AssertionError('unfinished dual-invalid writer did not time out')
            event.release()
            try:
                p.communicate(timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object in (out, err), 'dual-invalid retry lost original bytes')
            else:
                raise AssertionError('dual-invalid retry did not raise')
            require(p.wait(timeout=3) == 0, 'dual-invalid retry child did not exit')
            require(p.stdout.closed and p.stderr.closed, 'dual-invalid retry pipes remain open')
        elif identifier == 'run-check-invalid':
            try:
                s.run(writer(bad_out, b'err:ok\n'), capture_output=True, check=True,
                      encoding='utf-8', timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object == bad_out, 'check=True lost the original decode bytes')
            else:
                raise AssertionError('check=True did not propagate decode error')
        elif identifier == 'utf16-invalid':
            raw = b'A\x00\xff'
            p = popen(writer(raw), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-16-le')
            expected_error(lambda: p.communicate(timeout=5), raw, 'utf-16-le')
            require(p.stdout.closed and p.stderr.closed, 'utf-16 pipes remain open')
        elif identifier == 'stdin-invalid':
            argv = command('import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"bad:"+bytes([255])+b"\\n")')
            try:
                s.run(argv, input='输入\n'*30000, capture_output=True, encoding='utf-8', timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object == b'bad:\xff\n', 'stdin path lost decode exception bytes')
            else:
                raise AssertionError('stdin/output combination did not fail in caller')
        elif identifier == 'repeat-valid':
            p = popen(writer(b'out:ok\n', b'err:ok\n'), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            first = p.communicate(timeout=5)
            second = p.communicate(timeout=5)
            require(first == ('out:ok\n', 'err:ok\n') and second == first,
                    'repeat communicate changed completed output')
            require(p.stdout.closed and p.stderr.closed, 'repeat-valid pipes remain open')
        elif identifier == 'completion-order-error':
            # stderr reaches EOF first; the first completed reader error must win.
            code = ("import os,time;os.write(2,b'err:'+bytes([254])+b'\\n');os.close(2);"
                    "time.sleep(0.35);os.write(1,b'out:'+bytes([255])+b'\\n')")
            p = popen(command(code), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object == b'err:' + bytes([254]) + b'\n',
                        'decode error priority must follow reader completion order')
            else:
                raise AssertionError('completion-order fixture did not propagate decode error')
            require(p.wait(timeout=3) == 0, 'completion-order child did not exit')
            require(p.stdout.closed and p.stderr.closed, 'completion-order pipes remain open')
        elif identifier == 'completion-order-timeout-retry':
            # stderr completes during the first timed-out communicate; stdout finishes later.
            code = ("import os,time;os.write(2,b'err:'+bytes([254])+b'\\n');os.close(2);"
                    "time.sleep(0.45);os.write(1,b'out:'+bytes([255])+b'\\n')")
            p = popen(command(code), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=0.1)
            except s.TimeoutExpired:
                pass
            else:
                raise AssertionError('timeout fixture unexpectedly completed')
            require(not p.stdout.closed, 'timeout closed unfinished stdout pipe')
            try:
                p.communicate(timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object == b'err:' + bytes([254]) + b'\n',
                        'timeout retry did not preserve first completed reader error')
            else:
                raise AssertionError('timeout retry did not propagate decode error')
            require(p.wait(timeout=3) == 0, 'timeout retry child did not exit')
            require(p.stdout.closed and p.stderr.closed, 'timeout retry pipes remain open')
        elif identifier == 'completion-order-reversed':
            # stdout completes first in this mirror fixture, so stdout must be selected.
            code = ("import os,time;os.write(1,b'out:'+bytes([255])+b'\\n');os.close(1);"
                    "time.sleep(0.35);os.write(2,b'err:'+bytes([254])+b'\\n')")
            p = popen(command(code), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            try:
                p.communicate(timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.object == b'out:' + bytes([255]) + b'\n',
                        'reverse completion order selected the wrong reader error')
            else:
                raise AssertionError('reverse completion fixture did not raise')
            require(p.wait(timeout=3) == 0, 'reverse completion child did not exit')
            require(p.stdout.closed and p.stderr.closed, 'reverse completion pipes remain open')
        elif identifier == 'reader-close-baseexception':
            p = popen(writer(b'ok\n'), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            original = p.stdout
            class CloseExploder:
                closed = False
                calls = 0
                def read(self):
                    return original.read()
                def close(self):
                    self.calls += 1
                    self.closed = True
                    if not original.closed:
                        original.close()
                    if self.calls == 1:
                        raise KeyboardInterrupt()
            p.stdout = CloseExploder()
            try:
                p.communicate(timeout=5)
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError('BaseException from reader close was swallowed')
            require(p.stdout.closed and p.stderr.closed, 'close BaseException path left pipes open')
            require(p.wait(timeout=3) == 0, 'close BaseException child did not finish')
        elif identifier == 'reader-baseexception':
            p = popen(writer(b'ok\n'), stdout=s.PIPE, stderr=s.PIPE, encoding='utf-8')
            original = p.stdout
            class ExplodingReader:
                closed = False
                def read(self):
                    raise KeyboardInterrupt()
                def close(self):
                    self.closed = True
                    original.close()
            p.stdout = ExplodingReader()
            try:
                p.communicate(timeout=5)
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError('BaseException from reader was swallowed')
            require(p.stdout.closed and p.stderr.closed, 'BaseException path left pipes open')
        elif identifier == 'strict-errors':
            try:
                s.run(writer(bad_out, bad_err), capture_output=True, encoding='utf-8',
                      errors='strict', timeout=5)
            except UnicodeDecodeError as exc:
                require(exc.encoding == 'utf-8', 'strict handler changed exception encoding')
            else:
                raise AssertionError('explicit strict handler did not propagate error')
        else:
            raise RuntimeError('unknown testcase')
        require(not unhandled, 'unhandled reader thread exception: '+repr(unhandled))
        require(not [t.name for t in threading.enumerate() if id(t) not in before_threads], 'new reader thread survived completion')
        return {'status':'PASS', 'detail':'public API, real child process and Windows pipes verified'}
    except Exception as exc:
        return {'status':'FAIL', 'detail':type(exc).__name__+': '+str(exc)}
    finally:
        for event in events:
            event.release()
        for p in children:
            if p.poll() is None:
                p.kill()
            try:
                p.wait(timeout=3)
            except Exception:
                pass
            for stream in (p.stdin,p.stdout,p.stderr):
                if stream and not stream.closed:
                    stream.close()
        for event in events:
            event.close()
        threading.excepthook = old_hook

def score(rubric, results):
    expected = {item['id']:item for item in rubric['testcases'] if item.get('required', True)}
    ids = [item['id'] for item in results]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):
        return 'INVALID', None
    if any(item['status'] not in ('PASS','FAIL') for item in results):
        return 'INVALID', None
    if any(item['group'] != expected[item['id']]['group'] for item in results):
        return 'INVALID', None
    return 'VALID', int(all(item['status']=='PASS' for item in results))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--case')
    parser.add_argument('--rubric',default=str(Path(__file__).with_name('rubric.json')))
    args=parser.parse_args()
    if args.case:
        value=one_case(args.case,args.workspace)
        Path(args.output).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        return 0
    results=[]
    verifier_log=[]
    env=os.environ.copy()
    env['PYTHONIOENCODING']='utf-8'
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True)
    health=trusted.run(command('import os,sys;os.write(1,b"healthy");sys.exit(0)'),capture_output=True,timeout=5)
    if os.name!='nt' or sys.version_info[:3]!=(3,12,14) or health.stdout!=b'healthy':
        output.write_text(json.dumps({'validity':'INVALID','score':None,'reason':'Windows/Python/child health preflight failed'}),encoding='utf-8')
        return 2
    for identifier, group, requirement in CASES:
        path=output.parent/(identifier+'.json')
        if path.exists(): path.unlink()
        argv=[sys.executable,'-I',str(Path(__file__).resolve()),'--workspace',str(Path(args.workspace).resolve()),'--case',identifier,'--output',str(path.resolve())]
        started=time.monotonic()
        try:
            trial=trusted.run(argv,capture_output=True,timeout=15,env=env)
            if trial.returncode!=0 or not path.exists():
                item={'status':'ERROR','detail':'case worker failed: '+trial.stderr.decode('utf-8',errors='replace')[-2000:]}
            else:
                item=json.loads(path.read_text(encoding='utf-8'))
        except trusted.TimeoutExpired:
            item={'status':'ERROR','detail':'worker watchdog expired; requires infrastructure/candidate cause review'}
        except Exception as exc:
            item={'status':'ERROR','detail':type(exc).__name__+': '+str(exc)}
        item.update(id=identifier,group=group,requirement=requirement,elapsed_sec=round(time.monotonic()-started,3))
        results.append(item)
        line=f"{identifier} {item['status']} {item.get('detail','')}"
        verifier_log.append(line)
        print(line,flush=True)
    rubric=json.loads(Path(args.rubric).read_text(encoding='utf-8'))
    manifest=json.loads(Path(__file__).with_name('required_testcases.json').read_text(encoding='utf-8'))
    fixed={c['id']:(c['group'],c['requirement']) for c in manifest}
    declared={c['id']:(c['group'],c['requirement']) for c in rubric['testcases'] if c['required']}
    if len(manifest)!=len(fixed) or fixed!=declared:
        output.write_text(json.dumps({'validity':'INVALID','score':None,'reason':'required manifest/rubric mismatch'}),encoding='utf-8')
        return 2
    rubric=dict(rubric,testcases=manifest)
    validity,reward=score(rubric,results)
    value={'task_id':rubric['task_id'],'task_version':rubric['task_version'],'validity':validity,'status':validity,'score':reward,'required':[c['id'] for c in manifest],'testcase_pass_count':sum(r['status']=='PASS' for r in results),'testcases':results,'windows_runtime':sys.platform,'python_version':sys.version}
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    output.with_name('result.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    verifier_log.append(f'{validity} score={reward} pass={value["testcase_pass_count"]}/{len(CASES)}')
    output.with_name('verifier.log').write_text('\n'.join(verifier_log)+'\n',encoding='utf-8')
    output.with_name('reward.txt').write_text('' if reward is None else str(reward),encoding='utf-8')
    if validity=='VALID':
        output.with_name('reward.json').write_text(json.dumps({'reward':reward}),encoding='utf-8')
    print(f'{validity} score={reward} pass={value["testcase_pass_count"]}/{len(CASES)}')
    return 2 if validity=='INVALID' else (0 if reward==1 else 1)

if __name__=='__main__':
    raise SystemExit(main())
