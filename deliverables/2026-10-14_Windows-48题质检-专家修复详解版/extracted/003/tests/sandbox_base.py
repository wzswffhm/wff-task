"""Independent Windows state verifier. Candidate runs as a scoped standard user."""
import argparse, base64, ctypes, hashlib, json, os, secrets, shutil, subprocess, time, uuid, winreg
from ctypes import wintypes as W
from datetime import datetime, timezone
from pathlib import Path

CSC = r'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
PS = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
HOST_PS = shutil.which('pwsh.exe') or PS
HOST = Path(os.environ['USERPROFILE'])/'.outside-harbor-host'/'sandboxes'
K = ctypes.WinDLL('kernel32', use_last_error=True)
A = ctypes.WinDLL('advapi32', use_last_error=True)

class Startup(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),('x',W.DWORD),('y',W.DWORD),('xs',W.DWORD),('ys',W.DWORD),('xc',W.DWORD),('yc',W.DWORD),('fill',W.DWORD),('flags',W.DWORD),('show',W.WORD),('res2',W.WORD),('ptr',ctypes.c_void_p),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class ProcessInfo(ctypes.Structure):
    _fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',W.DWORD),('tid',W.DWORD)]
class Basic(ctypes.Structure):
    _fields_=[('procTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',W.DWORD),('min',ctypes.c_size_t),('max',ctypes.c_size_t),('active',W.DWORD),('affinity',ctypes.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class Limits(ctypes.Structure):
    _fields_=[('basic',Basic),('io',ctypes.c_ulonglong*6),('procMemory',ctypes.c_size_t),('jobMemory',ctypes.c_size_t),('peakProc',ctypes.c_size_t),('peakJob',ctypes.c_size_t)]
K.CreateJobObjectW.argtypes=[ctypes.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD]
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
K.CloseHandle.argtypes=[W.HANDLE]
K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
K.ResumeThread.argtypes=[W.HANDLE]
K.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
A.CreateProcessWithLogonW.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,W.DWORD,W.LPCWSTR,W.LPWSTR,W.DWORD,ctypes.c_void_p,W.LPCWSTR,ctypes.POINTER(Startup),ctypes.POINTER(ProcessInfo)]

def now(): return datetime.now(timezone.utc).isoformat()
def save(path,obj):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def ps(script,*args,timeout=120):
    p=subprocess.run([HOST_PS,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),*map(str,args)],capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr.decode('utf-8','replace')[-3000:])
    return p.stdout.decode('utf-8-sig','replace').strip()
def alive(pid):
    h=K.OpenProcess(0x1000|0x100000,False,int(pid))
    if not h:return False
    try:return K.WaitForSingleObject(h,0)==258
    finally:K.CloseHandle(h)

class Sandbox:
    def __init__(self,workspace,task_id):
        self.id=uuid.uuid4().hex;self.user='ohb_'+self.id[:12]
        self.root=Path('C:/OutsideHarborRuns')/self.id;self.jobs=[];self.invocation=0
        self.script=Path(__file__).with_name('sandbox.ps1')
        HOST.mkdir(parents=True,exist_ok=True);self.descriptor=HOST/(self.id+'.json')
        password='[REDACTED]'+secrets.token_urlsafe(24)
        encrypted=subprocess.run([HOST_PS,'-NoProfile','-Command',"$p=[Console]::In.ReadToEnd(); ConvertFrom-SecureString (ConvertTo-SecureString $p -AsPlainText -Force)"],input=password.encode(),capture_output=True,check=True).stdout.decode().strip()
        self.password=[REDACTED]
        self.regroot='SOFTWARE\\OutsideHarborBench\\'+self.id if 'registry' in task_id else None
        save(self.descriptor,dict(user=self.user,passwordDpapi=encrypted,root=str(self.root),registryRoot=self.regroot))
        self.created=False
        try:
            ps(self.script,'-Action','create','-Descriptor',self.descriptor);self.created=True
            self.sid=json.loads(self.descriptor.read_text(encoding='utf-8-sig'))['sid']
            # Only public candidate assets go into the account-accessible directory.
            shutil.copytree(workspace,self.root/'candidate',dirs_exist_ok=True)
            self.exe=self.root/'candidate'/'bin'/'candidate.exe'
            self.wrapper=self.root/'invoke.ps1'
            self.wrapper.write_text(r'''param([string]$Exe,[string]$Request,[string]$Output)
$ErrorActionPreference='Stop'
try {
 $info=[Diagnostics.ProcessStartInfo]::new($Exe)
 $info.UseShellExecute=$false; $info.CreateNoWindow=$true
 $info.RedirectStandardInput=$true; $info.RedirectStandardOutput=$true; $info.RedirectStandardError=$true
 $info.StandardOutputEncoding=[Text.UTF8Encoding]::new($false); $info.StandardErrorEncoding=[Text.UTF8Encoding]::new($false)
 $p=[Diagnostics.Process]::Start($info)
 $outTask=$p.StandardOutput.ReadToEndAsync(); $errTask=$p.StandardError.ReadToEndAsync()
 $raw=[Text.Encoding]::UTF8.GetBytes([IO.File]::ReadAllText($Request,[Text.Encoding]::UTF8))
 $p.StandardInput.BaseStream.Write($raw,0,$raw.Length); $p.StandardInput.Close()
 $p.WaitForExit()
 [IO.File]::WriteAllText($Output,$outTask.Result,[Text.UTF8Encoding]::new($false))
 [IO.File]::WriteAllText(($Output+'.stderr'),$errTask.Result,[Text.UTF8Encoding]::new($false))
 [IO.File]::WriteAllText(($Output+'.exit'),[string]$p.ExitCode)
 exit $p.ExitCode
} catch {
 [IO.File]::WriteAllText(($Output+'.runner-error'),($_ | Out-String),[Text.UTF8Encoding]::new($false))
 exit 126
}
''',encoding='utf-8-sig')
            # A trusted, separate program establishes transport and access isolation before scoring.
            health_source=self.root/'runner-health.cs';health_exe=self.root/'runner-health.exe'
            health_source.write_text(r'''using System;using System.IO;using System.Security.Principal;using System.Text;using System.Web.Script.Serialization;
class Health {static void Main(){Console.InputEncoding=new UTF8Encoding(false);Console.OutputEncoding=new UTF8Encoding(false);
var json=new JavaScriptSerializer();var request=json.Deserialize<System.Collections.Generic.Dictionary<string,object>>(Console.In.ReadToEnd());
bool denied=false;try{File.ReadAllText((string)request["protected"]);}catch(UnauthorizedAccessException){denied=true;}
Console.WriteLine(json.Serialize(new {status="Healthy",echo=request["echo"],admin=new WindowsPrincipal(WindowsIdentity.GetCurrent()).IsInRole(WindowsBuiltInRole.Administrator),hostDenied=denied,noApiEnvironment=Environment.GetEnvironmentVariable("OPENAI_API_KEY")==null}));}}
''',encoding='utf-8')
            built=subprocess.run([CSC,'/nologo','/r:System.Web.Extensions.dll','/out:'+str(health_exe),str(health_source)],capture_output=True)
            if built.returncode:raise RuntimeError('Independent runner health fixture failed to compile')
            protected=HOST/(self.id+'.protected');protected.write_text('host-only access witness',encoding='utf-8')
            actual_exe=self.exe;self.exe=health_exe
            try:health=self.invoke({'echo':'中文 UTF-8 ✓','protected':str(protected)})
            finally:self.exe=actual_exe;protected.unlink(missing_ok=True);self.release()
            if health!=dict(status='Healthy',echo='中文 UTF-8 ✓',admin=False,hostDenied=True,noApiEnvironment=True):raise RuntimeError('Independent runner health/isolation check failed: '+str(health))
            self.health=health
        except:
            self.close();raise
    def release(self):
        for job in self.jobs:K.CloseHandle(job)
        self.jobs=[]
    def invoke(self,request,timeout=18):
        self.release();self.invocation+=1
        req=self.root/f'request-{self.invocation}.json';out=self.root/f'output-{self.invocation}.json'
        save(req,request)
        command=subprocess.list2cmdline([PS,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.wrapper),'-Exe',str(self.exe),'-Request',str(req),'-Output',str(out)])
        env={'SystemRoot':r'C:\Windows','WINDIR':r'C:\Windows','PATH':r'C:\Windows\System32;C:\Windows','TEMP':str(self.root),'TMP':str(self.root)}
        environment=ctypes.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items()))+'\0\0')
        si=Startup();si.cb=ctypes.sizeof(si);pi=ProcessInfo()
        success=A.CreateProcessWithLogonW(self.user,'.',self.password,0,PS,ctypes.create_unicode_buffer(command),0x08000404,environment,str(self.root),ctypes.byref(si),ctypes.byref(pi))
        if not success:raise RuntimeError('Low-privilege process launch failed: WinError '+str(ctypes.get_last_error()))
        job=K.CreateJobObjectW(None,None)
        limits=Limits();limits.basic.flags=0x2000|0x100|0x10;limits.procMemory=1024*1024*1024;limits.basic.affinity=3
        try:
            if not job or not K.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)) or not K.AssignProcessToJobObject(job,pi.process):
                K.TerminateProcess(pi.process,125);raise RuntimeError('Outer isolation Job Object setup failed: '+str(ctypes.get_last_error()))
            self.jobs.append(job);job=None
            K.ResumeThread(pi.thread)
            wait=K.WaitForSingleObject(pi.process,int(timeout*1000))
            if wait==258:
                self.release();return {'status':'CandidateDeadlineExceeded'}
            if wait!=0:raise RuntimeError('Runner wait failure')
            runner_error=Path(str(out)+'.runner-error')
            if runner_error.exists():raise RuntimeError('Low-privilege wrapper failed: '+runner_error.read_text(encoding='utf-8-sig')[:1200])
            if not out.exists():return {'status':'CandidateNoResponse'}
            try:return json.loads(out.read_text(encoding='utf-8-sig'))
            except (ValueError,UnicodeError):return {'status':'CandidateMalformedResponse'}
        finally:
            if job:K.CloseHandle(job)
            K.CloseHandle(pi.thread);K.CloseHandle(pi.process)
    def close(self):
        self.release()
        if self.descriptor.exists():
            ps(self.script,'-Action','cleanup','-Descriptor',self.descriptor)
            self.descriptor.unlink()
        self.password=''

def file_identity(path):
    class Info(ctypes.Structure):
        _fields_=[('attributes',W.DWORD),('creation',W.FILETIME),('access',W.FILETIME),('write',W.FILETIME),('serial',W.DWORD),('sizehigh',W.DWORD),('sizelow',W.DWORD),('links',W.DWORD),('indexhigh',W.DWORD),('indexlow',W.DWORD)]
    K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
    K.GetFileInformationByHandle.argtypes=[W.HANDLE,ctypes.POINTER(Info)]
    h=K.CreateFileW(str(path),0,7,None,3,0,None)
    if h==ctypes.c_void_p(-1).value:raise RuntimeError('File identity probe failed')
    try:
        info=Info()
        if not K.GetFileInformationByHandle(h,ctypes.byref(info)):raise RuntimeError('File identity unavailable')
        return [info.serial,info.indexhigh,info.indexlow]
    finally:K.CloseHandle(h)
def marker(path):return Path(str(path)+':Zone.Identifier')
def fixture(s,name='a.bin',zone=True):
    p=s.root/(uuid.uuid4().hex+'-'+name);p.write_bytes(b'primary\x00payload\xff')
    Path(str(p)+':AuditTrail').write_bytes(b'keep-other-stream\x00')
    if zone:marker(p).write_bytes(b'[ZoneTransfer]\r\nZoneId=3\r\n')
    os.utime(p,ns=(1600000000000000000,1600000001234567800))
    return p
def ads_tests(s,check):
    def call(paths,atomic=False):return s.invoke({'paths':list(map(str,paths)),'atomic':atomic})
    def clean():
        p=fixture(s);r=call([p]);assert r['status']=='Completed' and r['results'][0]['status']=='Removed' and not marker(p).exists()
    check('clean-marker',clean)
    def literal():
        p=fixture(s,'安装 [1] 空格.bin');neighbor=fixture(s,'安装 1 空格.bin');r=call([p]);assert r['results'][0]['status']=='Removed' and not marker(p).exists() and marker(neighbor).exists()
    check('literal-unicode',literal)
    def preserve(what):
        p=fixture(s);before=p.read_bytes() if what=='bytes' else Path(str(p)+':AuditTrail').read_bytes() if what=='streams' else file_identity(p) if what=='id' else p.stat()
        call([p]);after=p.read_bytes() if what=='bytes' else Path(str(p)+':AuditTrail').read_bytes() if what=='streams' else file_identity(p) if what=='id' else p.stat()
        if what=='metadata':assert (before.st_ctime_ns,before.st_mtime_ns,before.st_atime_ns,before.st_file_attributes)==(after.st_ctime_ns,after.st_mtime_ns,after.st_atime_ns,after.st_file_attributes)
        else:assert before==after
    for id,what in [('preserve-bytes','bytes'),('preserve-streams','streams'),('preserve-file-id','id'),('preserve-metadata','metadata')]:check(id,lambda what=what:preserve(what))
    def already():
        p=fixture(s,zone=False);r=call([p]);assert r['results'][0]['status']=='AlreadyClean' and p.exists()
    check('already-clean',already)
    def repeat():
        p=fixture(s);r=call([p]);r2=call([p]);assert r['results'][0]['status']=='Removed' and r2['results'][0]['status']=='AlreadyClean'
    check('repeat-clean',repeat)
    def duplicate(normalized):
        p=fixture(s);alt=str(p.parent/'..'/p.parent.name/p.name) if normalized else str(p).upper();r=call([p,alt]);assert [v['status'] for v in r['results']]==['Removed','Duplicate']
    check('duplicate-case',lambda:duplicate(False));check('duplicate-normalized',lambda:duplicate(True))
    def atomic(kind):
        p=fixture(s);bad=s.root/(uuid.uuid4().hex+'-missing');lock=None
        if kind=='directory':bad.mkdir()
        if kind=='locked':
            bad=fixture(s);K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
            lock=K.CreateFileW(str(marker(bad)),0x80000000,0,None,3,0,None)
            if lock==ctypes.c_void_p(-1).value:raise RuntimeError('Locked ADS fixture unavailable')
        try:
            r=call([p,bad],True);assert r['status']=='Rejected' and [v['status'] for v in r['results']]==['Skipped','Failed'] and marker(p).exists()
        finally:
            if lock:K.CloseHandle(lock)
    for kind in ['missing','directory','locked']:check('atomic-'+kind,lambda kind=kind:atomic(kind))
    def reparse():
        target=fixture(s);link=s.root/(uuid.uuid4().hex+'-link.bin');os.symlink(target,link);r=call([link]);assert r['results'][0]['status']=='Failed' and marker(target).exists()
    check('reject-reparse',reparse)
    def stream_path():
        p=fixture(s);r=call([Path(str(p)+':AuditTrail')]);assert r['results'][0]['status']=='Failed' and Path(str(p)+':AuditTrail').read_bytes()==b'keep-other-stream\x00'
    check('reject-stream-path',stream_path)
    def readonly():
        p=fixture(s);K.SetFileAttributesW.argtypes=[W.LPCWSTR,W.DWORD];K.SetFileAttributesW(str(p),1)
        try:r=call([p]);assert r['results'][0]['status']=='Failed' and marker(p).exists()
        finally:K.SetFileAttributesW(str(p),128)
    check('reject-readonly',readonly)
    def non_atomic():
        p=fixture(s);r=call([s.root/'missing',p]);assert [v['status'] for v in r['results']]==['Failed','Removed'] and not marker(p).exists()
    check('non-atomic-progress',non_atomic)
    check('empty-batch',lambda:equal(call([]),{'status':'Completed','results':[]}))

def equal(a,b):assert a==b,(a,b)
def registry_tests(s,check):
    def reset():
        for view in [winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY]:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot,0,winreg.KEY_ALL_ACCESS|view) as k:
                while winreg.QueryInfoKey(k)[1]:winreg.DeleteValue(k,winreg.EnumValue(k,0)[0])
                winreg.SetValueEx(k,'Unrelated',0,winreg.REG_BINARY,b'keep\x00')
                with winreg.CreateKeyEx(k,'KeepChild',0,winreg.KEY_ALL_ACCESS) as child:winreg.SetValueEx(child,'value',0,winreg.REG_SZ,'untouched')
    def call(changes,view='64',op='apply',root=None):return s.invoke({'op':op,'root':root or s.regroot,'view':view,'changes':changes})
    def read(name,view='64'):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot,0,winreg.KEY_READ|(winreg.KEY_WOW64_32KEY if view=='32' else winreg.KEY_WOW64_64KEY)) as k:return winreg.QueryValueEx(k,name)
        except FileNotFoundError as e:
            raise AssertionError('Candidate left expected registry key/value missing: '+name) from e
    def typed(kind,value,expected,regkind):
        reset();r=call([dict(name='Target',action='set',kind=kind,value=value)]);assert r['status']=='Applied' and read('Target')==(expected,regkind)
    check('basic-string',lambda:typed('String','值', '值',winreg.REG_SZ))
    def snapshot():
        reset()
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot,0,winreg.KEY_ALL_ACCESS|winreg.KEY_WOW64_64KEY) as k:winreg.SetValueEx(k,'Path',0,winreg.REG_EXPAND_SZ,'%WINDIR%\\中文')
        r=call([],op='snapshot');v=next((v for v in r['values'] if v['name']=='Path'),None);assert r['status']=='Snapshot' and v is not None and v['kind']=='ExpandString' and v['value']=='%WINDIR%\\中文'
    check('snapshot-raw',snapshot)
    for id,kind,value,expected,regkind in [('typed-dword','DWord',123,123,winreg.REG_DWORD),('typed-qword','QWord','9223372036854775806',9223372036854775806,winreg.REG_QWORD),('typed-binary','Binary','AP8BCg==',b'\x00\xff\x01\x0a',winreg.REG_BINARY),('typed-multi','MultiString',['中文','C:\\with space','third'],['中文','C:\\with space','third'],winreg.REG_MULTI_SZ),('expand-unexpanded','ExpandString','%WINDIR%\\dir','%WINDIR%\\dir',winreg.REG_EXPAND_SZ)]:check(id,lambda kind=kind,value=value,expected=expected,regkind=regkind:typed(kind,value,expected,regkind))
    def default():reset();r=call([dict(name='',action='set',kind='String',value='default')]);assert r['status']=='Applied' and read('')==('default',winreg.REG_SZ)
    check('default-value',default)
    def views():
        reset();call([dict(name='Different',action='set',kind='DWord',value=32)],'32');call([dict(name='Different',action='set',kind='DWord',value=64)],'64');assert read('Different','32')==(32,winreg.REG_DWORD) and read('Different','64')==(64,winreg.REG_DWORD)
    check('view-isolation',views)
    def invalid():
        reset();r=call([dict(name='First',action='set',kind='String',value='new'),dict(name='Second',action='set',kind='DWord',value='wrong')]);assert r['status']=='Invalid'
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as k:
            try:winreg.QueryValueEx(k,'First');raise AssertionError('Partially written')
            except FileNotFoundError:pass
    check('invalid-batch',invalid)
    def duplicate():reset();r=call([dict(name='Foo',action='set',kind='String',value='one'),dict(name='fOO',action='set',kind='String',value='two')]);assert r['status']=='Invalid';assert read('Unrelated')==(b'keep\x00',winreg.REG_BINARY)
    check('duplicate-names',duplicate)
    def expectation(mode):
        reset()
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot,0,winreg.KEY_ALL_ACCESS|winreg.KEY_WOW64_64KEY) as k:winreg.SetValueEx(k,'Target',0,winreg.REG_SZ,'old')
        exp=dict(exists=True,kind='String',value='old')
        if mode=='conflict':exp['value']='OLD'
        elif mode=='missing':exp={'exists':False}
        elif mode=='kind':exp['kind']='ExpandString'
        r=call([dict(name='Target',action='set',kind='String',value='new',expected=exp)])
        assert r['status']==('Applied' if mode=='success' else 'Conflict') and read('Target')==(('new' if mode=='success' else 'old'),winreg.REG_SZ)
    for mode in ['conflict','missing','kind','success']:check('expected-'+mode,lambda mode=mode:expectation(mode))
    def preserve():
        reset();call([dict(name='Target',action='set',kind='String',value='new')]);assert read('Unrelated')==(b'keep\x00',winreg.REG_BINARY)
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,s.regroot+'\\KeepChild',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as k:assert winreg.QueryValueEx(k,'value')[0]=='untouched'
    check('preserve-others',preserve)
    def delete_missing():reset();r=call([dict(name='Absent',action='delete')]);assert r['status']=='NoChange'
    check('delete-missing',delete_missing)
    def idempotent():reset();changes=[dict(name='Target',action='set',kind='String',value='same')];call(changes);assert call(changes)['status']=='NoChange'
    check('idempotent',idempotent)
    check('missing-root',lambda:equal(call([],root=s.regroot+'\\DoesNotExist')['status'],'MissingRoot'))

WORKER = r'''
using System; using System.IO; using System.Diagnostics; using System.Threading; using System.Text; using System.Web.Script.Serialization;
class Worker {
 static int Main(string[] a) {
  Console.OutputEncoding=new UTF8Encoding(false);
  string mode=a[0];
  if(mode=="echo") { Console.Write(new JavaScriptSerializer().Serialize(new {args=System.Linq.Enumerable.ToArray(System.Linq.Enumerable.Skip(a,1)),cwd=Environment.CurrentDirectory})); return 0; }
  if(mode=="exit") { Console.Write(a[2]); Console.Error.Write(a[3]); return Int32.Parse(a[1]); }
  if(mode=="flood") { Console.Write(new string('a',150000)); Console.Error.Write(new string('b',120000)); return 0; }
  if(mode=="sleep") { Thread.Sleep(Int32.Parse(a[1])); return 0; }
  if(mode=="child") { File.WriteAllText(a[1],Process.GetCurrentProcess().Id.ToString()); for(int i=0;i<600;i++) { File.WriteAllText(a[2],i.ToString()); Thread.Sleep(50); } return 0; }
  if(mode=="tree") {
   string exe=Process.GetCurrentProcess().MainModule.FileName;
   var p=Process.Start(new ProcessStartInfo(exe,"child \""+a[1]+"\" \""+a[2]+"\""){UseShellExecute=false,CreateNoWindow=true});
   File.WriteAllText(a[3],p.Id.ToString());
   var watch=Stopwatch.StartNew(); while(!File.Exists(a[1])&&watch.ElapsedMilliseconds<3000) Thread.Sleep(5);
   if(!File.Exists(a[1])) return 77;
   if(a[4]=="wait") Thread.Sleep(30000);
   return 0;
  }
  return 88;
 }
}
'''
def job_tests(s,check):
    source=s.root/'worker.cs';source.write_text(WORKER,encoding='utf-8');worker=s.root/'worker.exe'
    p=subprocess.run([CSC,'/nologo','/r:System.Web.Extensions.dll','/out:'+str(worker),str(source)],capture_output=True)
    if p.returncode:raise RuntimeError('Worker fixture compilation failed '+p.stdout.decode('utf-8','replace'))
    def call(arguments,timeout=3000,exe=None,cwd=None):return s.invoke(dict(exe=str(exe or worker),arguments=arguments,cwd=str(cwd or s.root),timeoutMs=timeout),timeout=timeout/1000+10)
    def exit_test(code=0,out='ok',err=''):
        r=call(['exit',str(code),out,err]);assert r==dict(status='Exited',exitCode=code,stdout=out,stderr=err),r
    check('simple-exit',lambda:exit_test());check('nonzero-exit',lambda:exit_test(17));check('unicode-output',lambda:exit_test(0,'中文 UTF-8 ✓'));check('stderr-separate',lambda:exit_test(3,'out','err'))
    def flood():r=call(['flood']);assert r['status']=='Exited' and r['stdout']=='a'*150000 and r['stderr']=='b'*120000
    check('large-pipes',flood)
    def echo(args):
        r=call(['echo',*args]);assert r['status']=='Exited',r
        received=json.loads(r['stdout']);assert received['args']==args,(received,args)
    check('argument-empty',lambda:echo(['','two words']));check('argument-quotes',lambda:echo(['say "hi"','x\\\\"y']));check('argument-trailing-slash',lambda:echo(['C:\\folder with space\\','next']));check('argument-unicode',lambda:echo(['中文 参数','[1]']))
    def cwd():
        target=s.root/'中文 cwd';target.mkdir();r=call(['echo'],cwd=target);assert json.loads(r['stdout'])['cwd'].lower()==str(target).lower()
    check('cwd',cwd)
    def root_timeout():r=call(['sleep','30000'],timeout=250);assert r['status']=='TimedOut' and r['exitCode'] is None
    check('timeout-root',root_timeout)
    def tree(wait):
        token=uuid.uuid4().hex;ready=s.root/(token+'.ready');tick=s.root/(token+'.tick');receipt=s.root/(token+'.pid')
        r=call(['tree',str(ready),str(tick),str(receipt),'wait' if wait else 'exit'],timeout=1200 if wait else 4000)
        assert receipt.exists() and ready.exists(),'Independent worker readiness/child PID receipt absent'
        pid=int(receipt.read_text());assert int(ready.read_text())==pid
        assert r['status']==('TimedOut' if wait else 'Exited'),r
        assert not alive(pid),'Child process still alive after candidate returned'
        before=tick.read_bytes() if tick.exists() else None;time.sleep(.15);assert (tick.read_bytes() if tick.exists() else None)==before
    check('timeout-grandchild',lambda:tree(True));check('exit-child-cleanup',lambda:tree(False));check('fast-child-containment',lambda:tree(False))
    def launchfail(**kwargs):r=call([],**kwargs);assert r==dict(status='LaunchFailed',exitCode=None,stdout='',stderr=''),r
    check('missing-exe',lambda:launchfail(exe=s.root/'missing.exe'));check('invalid-timeout',lambda:launchfail(timeout=0));check('bad-cwd',lambda:launchfail(cwd=s.root/'missing-dir'))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--task-root',type=Path,required=True);ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--run-id',required=True);args=ap.parse_args()
    started=now();clock=time.monotonic();rubric=json.loads((args.task_root/'tests'/'rubric.json').read_text(encoding='utf-8-sig'))
    digest=hashlib.sha256()
    for path in sorted(p for p in args.task_root.rglob('*') if p.is_file()):
        rel=path.relative_to(args.task_root).as_posix().encode('utf-8');data=path.read_bytes()
        digest.update(len(rel).to_bytes(4,'big'));digest.update(rel);digest.update(len(data).to_bytes(8,'big'));digest.update(data)
    task_hash=digest.hexdigest()
    required=rubric['testcases'];definitions={t['id']:t for t in required};results=[];infra=[];sandbox=None
    def check(id,fn):
        definition=definitions[id];status='PASS';detail='Observed native Windows state satisfies public contract'
        try:fn()
        except (AssertionError,KeyError,IndexError,ValueError,TypeError) as e:status='FAIL';detail=str(e)[:1200] or type(e).__name__
        except Exception as e:status='ERROR';detail=type(e).__name__+': '+str(e)[:1200];infra.append(detail)
        finally:
            if sandbox:sandbox.release()
        results.append(dict(id=id,group=definition['group'],requirement=definition['requirement'],status=status,evidence=detail))
    try:
        exe=args.workspace/'bin'/'candidate.exe'
        exe.parent.mkdir(parents=True,exist_ok=True)
        if not exe.exists():
            build=subprocess.run([CSC,'/nologo','/r:System.Web.Extensions.dll','/out:'+str(exe),*map(str,args.workspace.glob('*.cs'))],capture_output=True)
            if build.returncode:raise RuntimeError('Candidate build failed before verifier; harness must report build attribution')
        sandbox=Sandbox(args.workspace,rubric['task_id'])
        if 'ntfs' in rubric['task_id']:ads_tests(sandbox,check)
        elif 'registry' in rubric['task_id']:registry_tests(sandbox,check)
        elif 'job' in rubric['task_id']:job_tests(sandbox,check)
        else:raise RuntimeError('Unknown task family')
    except Exception as e:infra.append(type(e).__name__+': '+str(e)[:2000])
    finally:
        if sandbox:
            try:sandbox.close()
            except Exception as e:infra.append('Cleanup failure: '+str(e)[:2000])
    seen={r['id'] for r in results}
    for d in required:
        if d['id'] not in seen:results.append(dict(id=d['id'],group=d['group'],requirement=d['requirement'],status='NOT_RUN',evidence='Verifier did not reach required test'))
    valid=not infra and all(r['status'] in ['PASS','FAIL'] for r in results) and len(results)==len(required)
    score=int(all(r['status']=='PASS' for r in results)) if valid else None
    record=dict(task_id=rubric['task_id'],task_version=rubric['task_version'],run_id=args.run_id,validity='VALID' if valid else 'INVALID',score=score,required=[r['id'] for r in required],testcases=results,testcase_pass_count=sum(r['status']=='PASS' for r in results),testcase_total=len(required),termination='completed' if valid else 'verifier_infrastructure_error',infrastructure_errors=infra,started_at=started,ended_at=now(),elapsed_sec=round(time.monotonic()-clock,3),cleanup='PASS' if not any('Cleanup failure' in x for x in infra) else 'FAIL',sandbox='unique standard local user; scoped NTFS/registry ACL; per-user outbound firewall; outer Job Object memory/affinity/cleanup')
    record['task_hash']=task_hash
    record['runner_health']=getattr(sandbox,'health',None)
    save(args.output,record);print(json.dumps({k:record[k] for k in ['task_id','validity','score','testcase_pass_count','testcase_total','elapsed_sec','infrastructure_errors']},ensure_ascii=True))
    return 2 if not valid else 0 if score==1 else 1
if __name__=='__main__':raise SystemExit(main())
