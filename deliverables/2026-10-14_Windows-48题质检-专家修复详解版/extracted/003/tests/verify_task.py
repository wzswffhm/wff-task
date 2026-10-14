import sys; sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,json,hashlib,time,uuid,os,subprocess,ctypes,winreg
from ctypes import wintypes as W
import sandbox_base as base
CSC=base.CSC
def ck(s,i,fn,out):
 d=defs[i]; status='PASS'; evidence='Independent Windows state and public protocol observed'
 try: fn()
 except (AssertionError,KeyError,IndexError,ValueError,TypeError) as e: status='FAIL'; evidence=str(e)[:1000]
 except Exception as e: status='ERROR'; evidence=type(e).__name__+': '+str(e)[:1000]; out.append(evidence)
 s.release(); records.append(dict(id=i,group=d['group'],requirement=d['requirement'],status=status,evidence=evidence))
def compile_src(s,name,src):
 p=s.root/(name+'.cs');p.write_text(src,encoding='utf-8');exe=s.root/(name+'.exe')
 z=subprocess.run([CSC,'/nologo','/out:'+str(exe),str(p)],capture_output=True)
 if z.returncode: raise RuntimeError('fixture compile failed: '+z.stderr.decode('utf8','replace'))
 return exe
def tests_hardlink(s,out):
 def call(paths):return s.invoke({'paths':list(map(str,paths))})
 ck(s,'byte-twin',lambda:assert_byte_twin(s,call),out)
 ck(s,'hardlink',lambda:assert_hardlink(s,call),out)
 ck(s,'unicode-path',lambda:assert_unicode(s,call),out)
 ck(s,'multiple-links',lambda:assert_many_links(s,call),out)
 ck(s,'input-order',lambda:assert_many_links(s,call),out)
 ck(s,'repeat-path',lambda:assert_repeat(s,call),out)
 ck(s,'missing-path',lambda:assert_missing(s,call),out)
 ck(s,'empty',lambda:assert_empty(call),out)
 ck(s,'distinct-files',lambda:assert_distinct(s,call),out)
 ck(s,'directory-path',lambda:assert_directory(s,call),out)
def assert_byte_twin(s,c):
 a=s.root/'t1';b=s.root/'t2';a.write_bytes(b'z');b.write_bytes(b'z');r=c([a,b]);assert r['duplicates']==[],r
def assert_hardlink(s,c):
 a=s.root/'h1';b=s.root/'h2';a.write_bytes(b'v');os.link(a,b);assert c([a,b])['duplicates']==[str(b)]
def assert_unicode(s,c):
 a=s.root/'中文 [x]';b=s.root/'另一个';a.write_bytes(b'x');os.link(a,b);assert c([a,b])['duplicates']==[str(b)]
def assert_empty(c):assert c([])=={'status':'Completed','duplicates':[]}
def assert_many_links(s,c):
 tag=uuid.uuid4().hex;a=s.root/(tag+'-many-a');b=s.root/(tag+'-many-b');d=s.root/(tag+'-many-c');a.write_bytes(b'ordered');os.link(a,b);os.link(a,d);assert c([a,b,d])['duplicates']==[str(b),str(d)]
def assert_repeat(s,c):
 a=s.root/'repeat';a.write_bytes(b'r');assert c([a,a])['duplicates']==[str(a)]
def assert_missing(s,c):assert c([s.root/'missing-file'])=={'status':'Completed','duplicates':[]}
def assert_distinct(s,c):
 a=s.root/'distinct-a';b=s.root/'distinct-b';a.write_bytes(b'a');b.write_bytes(b'b');assert c([a,b])['duplicates']==[]
def assert_directory(s,c):
 a=s.root/'directory';a.mkdir();assert c([a])=={'status':'Completed','duplicates':[]}
def tests_mutex(s,out):
 name='OHB_'+uuid.uuid4().hex
 hold=compile_src(s,'hold',r'''using System;using System.IO;using System.Threading;class H{static void Main(string[]a){bool c;using(var m=new Mutex(true,@"Global\"+a[0],out c)){File.WriteAllText(a[1],"ready");Thread.Sleep(15000);}}}''')
 ready=s.root/'ready';p=subprocess.Popen([str(hold),name,str(ready)])
 try:
  until=time.time()+5
  while time.time()<until and not ready.exists():time.sleep(.02)
  assert ready.exists(),'mutex holder did not become ready'
 finally:p.terminate();p.wait(timeout=5)
 ck(s,'acquire-free',lambda:assert_free(s),out)
 ck(s,'contended',lambda:assert_contended(s,hold,name),out)
 ck(s,'release',lambda:assert_free(s),out)
 ck(s,'different-name',lambda:assert_different(s),out)
 ck(s,'same-name',lambda:assert_free(s),out)
 ck(s,'invalid-empty',lambda:assert_invalid(s,''),out)
 ck(s,'invalid-nul',lambda:assert_invalid(s,'bad\0name'),out)
 ck(s,'unicode-name',lambda:assert_named_free(s,'中文_'+uuid.uuid4().hex),out)
 ck(s,'repeat-acquire',lambda:assert_free(s),out)
 ck(s,'namespace-global',lambda:assert_named_free(s,'OHB_global_'+uuid.uuid4().hex),out)
def assert_free(s):assert s.invoke({'name':'OHB_free_'+uuid.uuid4().hex}).get('status')=='Acquired'
def assert_busy(s,n):assert s.invoke({'name':n}).get('status')=='Busy'
def assert_contended(s,hold,n):
 ready=hold.parent/('r'+uuid.uuid4().hex);p=subprocess.Popen([str(hold),n,str(ready)])
 try:
  end=time.time()+5
  while time.time()<end and not ready.exists():time.sleep(.02)
  assert ready.exists();assert_busy(s,n)
 finally:p.terminate();p.wait(timeout=5)
def assert_different(s):
 n='OHB_'+uuid.uuid4().hex; other='OHB_'+uuid.uuid4().hex
 assert s.invoke({'name':n}).get('status')=='Acquired' and s.invoke({'name':other}).get('status')=='Acquired'
def assert_invalid(s,n):assert s.invoke({'name':n}).get('status')=='Invalid'
def assert_named_free(s,n):assert s.invoke({'name':n}).get('status')=='Acquired'
def tests_registry(s,out):
 token=uuid.uuid4().hex;root='Software\\OutsideHarbor\\'+token;candidate=s.exe
 helper=compile_src(s,'registry-fixture',r'''using System;using System.Collections;using System.Collections.Generic;using System.Linq;using Microsoft.Win32;using System.Web.Script.Serialization;using System.Text;class F{static JavaScriptSerializer j=new JavaScriptSerializer();static void Main(){Console.InputEncoding=new UTF8Encoding(false);Console.OutputEncoding=new UTF8Encoding(false);var q=j.Deserialize<Dictionary<string,object>>(Console.In.ReadToEnd());string root=@"Software\OutsideHarbor\"+Convert.ToString(q["key"]);string op=Convert.ToString(q["op"]);if(op=="seed"){using(var k=Registry.CurrentUser.CreateSubKey(root)){foreach(var raw in (IEnumerable)q["values"]){var v=(Dictionary<string,object>)raw;string n=Convert.ToString(v["name"]);var kind=(RegistryValueKind)Enum.Parse(typeof(RegistryValueKind),Convert.ToString(v["kind"]));object data=v["value"];if(kind==RegistryValueKind.Binary)data=Convert.FromBase64String(Convert.ToString(data));else if(kind==RegistryValueKind.MultiString)data=((IEnumerable)data).Cast<object>().Select(Convert.ToString).ToArray();else if(kind==RegistryValueKind.DWord)data=Convert.ToInt32(data);else if(kind==RegistryValueKind.QWord)data=Int64.Parse(Convert.ToString(data));k.SetValue(n,data,kind);}}Console.WriteLine(j.Serialize(new {status="Seeded"}));return;}using(var k=Registry.CurrentUser.OpenSubKey(root,false)){if(k==null){Console.WriteLine(j.Serialize(new {status="Missing"}));return;}string n=Convert.ToString(q["name"]);try{object v=k.GetValue(n,null,RegistryValueOptions.DoNotExpandEnvironmentNames);string kind=k.GetValueKind(n).ToString();string val=kind=="Binary"?Convert.ToBase64String((byte[])v):kind=="MultiString"?j.Serialize(v):Convert.ToString(v,System.Globalization.CultureInfo.InvariantCulture);Console.WriteLine(j.Serialize(new {status="Value",kind=kind,value=val}));}catch{Console.WriteLine(j.Serialize(new {status="Missing"}));}}}}''')
 s.exe=helper
 seeded=s.invoke({'op':'seed','key':token,'values':[{'name':'Plain','kind':'String','value':'中文'},{'name':'Path','kind':'ExpandString','value':'%TEMP%\\raw'},{'name':'Bin','kind':'Binary','value':'AP8='},{'name':'Multi','kind':'MultiString','value':['a','中文']},{'name':'Dword','kind':'DWord','value':17},{'name':'Qword','kind':'QWord','value':'9876543210'},{'name':'','kind':'String','value':'default'}]})
 assert seeded=={'status':'Seeded'},seeded
 s.exe=candidate
 def call(n,action='snapshot',**extra):return s.invoke(dict({'key':token,'name':n,'action':action},**extra))
 ck(s,'string-raw',lambda:assert_reg(call('Plain'),'String','中文'),out)
 ck(s,'expand-raw',lambda:assert_reg(call('Path'),'ExpandString','%TEMP%\\raw'),out)
 ck(s,'binary-kind',lambda:assert_reg(call('Bin'),'Binary','AP8='),out)
 ck(s,'multi-kind',lambda:assert_reg(call('Multi'),'MultiString','["a","中文"]'),out)
 ck(s,'dword-kind',lambda:assert_reg(call('Dword'),'DWord','17'),out)
 ck(s,'qword-kind',lambda:assert_reg(call('Qword'),'QWord','9876543210'),out)
 ck(s,'default-name',lambda:assert_reg(call(''),'String','default'),out)
 ck(s,'missing-value',lambda:assert_missing_reg(call),out)
 ck(s,'preserve-expand',lambda:assert_reg(call('Path'),'ExpandString','%TEMP%\\raw'),out)
 ck(s,'restore-kind',lambda:restore_verify(s,call,token,helper,candidate),out)
def assert_reg(x,k,v):assert x=={'status':'Value','kind':k,'value':v},x
def assert_missing_reg(call):assert call('absent')=={'status':'Missing'}
def restore_verify(s,call,token,helper,candidate):
 r=call('Restored','restore',kind='Binary',value='AP8=');assert r=={'status':'Restored'},r
 s.exe=helper
 try:observed=s.invoke({'op':'read','key':token,'name':'Restored'})
 finally:s.exe=candidate
 assert observed=={'status':'Value','kind':'Binary','value':'AP8='},observed
def tests_share(s,out):
 path=s.root/'share.dat';path.write_bytes(b'xy')
 original_id=base.file_identity(path)
 ck(s,'exclusive-conflict',lambda:assert_share_conflict(s,path),out)
 ck(s,'compatible-read',lambda:assert_share_open(s,path),out)
 ck(s,'not-found',lambda:assert_not_found(s),out)
 ck(s,'write-mode',lambda:assert_write(s,path),out)
 ck(s,'deny-delete',lambda:assert_share_conflict(s,path),out)
 ck(s,'read-share',lambda:assert_share_open(s,path),out)
 ck(s,'write-share',lambda:assert_write(s,path),out)
 ck(s,'missing-parent',lambda:assert_not_found(s),out)
 ck(s,'exclusive-open',lambda:assert_share_conflict(s,path),out)
 ck(s,'delete-compatible',lambda:assert_share_open(s,path),out)
 ck(s,'read-share-allowed',lambda:assert_access_share_flag(s,path,0x80000000,'allowRead',True),out)
 ck(s,'read-share-denied',lambda:assert_access_share_flag(s,path,0x80000000,'allowRead',False),out)
 ck(s,'write-share-allowed',lambda:assert_access_share_flag(s,path,0x40000000,'allowWrite',True),out)
 ck(s,'write-share-denied',lambda:assert_access_share_flag(s,path,0x40000000,'allowWrite',False),out)
 ck(s,'delete-share-allowed',lambda:assert_access_share_flag(s,path,0x00010000,'allowDelete',True),out)
 ck(s,'delete-share-denied',lambda:assert_access_share_flag(s,path,0x00010000,'allowDelete',False),out)
 ck(s,'byte-range-overlap',lambda:assert_byte_range_conflict(s,path,original_id),out)
 ck(s,'byte-range-disjoint',lambda:assert_byte_range_disjoint(s,path,original_id),out)
 ck(s,'invalid-byte-range',lambda:assert_invalid_byte_range(s,path,original_id),out)

class NativeOverlapped(ctypes.Structure):
 _fields_=[('Internal',ctypes.c_void_p),('InternalHigh',ctypes.c_void_p),('Offset',W.DWORD),('OffsetHigh',W.DWORD),('hEvent',W.HANDLE)]

def range_apis():
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
 k.LockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(NativeOverlapped)];k.LockFileEx.restype=W.BOOL
 k.UnlockFileEx.argtypes=[W.HANDLE,W.DWORD,W.DWORD,W.DWORD,ctypes.POINTER(NativeOverlapped)];k.UnlockFileEx.restype=W.BOOL
 k.CloseHandle.argtypes=[W.HANDLE]
 return k

def lock_range(k,path,offset,length):
 h=k.CreateFileW(str(path),0xC0000000,7,None,3,0,None)
 if h==ctypes.c_void_p(-1).value:raise RuntimeError('byte-range holder CreateFileW failed: '+str(ctypes.get_last_error()))
 ov=NativeOverlapped();ov.Offset=offset&0xffffffff;ov.OffsetHigh=(offset>>32)&0xffffffff
 if not k.LockFileEx(h,3,0,length&0xffffffff,(length>>32)&0xffffffff,ctypes.byref(ov)):
  error=ctypes.get_last_error();k.CloseHandle(h);raise RuntimeError('fixture LockFileEx failed: '+str(error))
 return h,ov

def probe_range(s,path,offset,length):
 return s.invoke({'path':str(path),'write':True,'allowRead':True,'allowWrite':True,'allowDelete':True,'probeRange':{'offset':offset,'length':length}})

def assert_byte_range_conflict(s,path,original_id):
 k=range_apis();h,ov=lock_range(k,path,0,1)
 try:
  r=probe_range(s,path,0,1);assert r=={'status':'LockViolation','win32':33},r
  assert base.file_identity(path)==original_id
 finally:
  k.UnlockFileEx(h,0,1,0,ctypes.byref(ov));k.CloseHandle(h)

def assert_byte_range_disjoint(s,path,original_id):
 k=range_apis();h,ov=lock_range(k,path,0,1)
 try:
  r=probe_range(s,path,1,1);assert r=={'status':'Opened','win32':0},r
  assert base.file_identity(path)==original_id
 finally:
  k.UnlockFileEx(h,0,1,0,ctypes.byref(ov));k.CloseHandle(h)

def assert_invalid_byte_range(s,path,original_id):
 r=probe_range(s,path,0,0);assert r=={'status':'Invalid','win32':87},r
 assert base.file_identity(path)==original_id
def assert_access_share_flag(s,p,holder_access,flag,allowed):
 k=ctypes.WinDLL('kernel32',use_last_error=True)
 k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
 k.CreateFileW.restype=W.HANDLE
 k.CloseHandle.argtypes=[ctypes.c_void_p]
 holder=k.CreateFileW(str(p),holder_access,7,None,3,0,None)
 assert holder!=ctypes.c_void_p(-1).value,'holder CreateFileW failed: '+str(ctypes.get_last_error())
 try:
  q={'path':str(p),'write':False,'allowRead':True,'allowWrite':True,'allowDelete':True}
  q[flag]=allowed
  r=s.invoke(q)
  expected=('Opened',0) if allowed else ('SharingViolation',32)
  assert (r.get('status'),r.get('win32'))==expected,(expected,r)
 finally:k.CloseHandle(holder)
def assert_share_open(s,p):
 h=ctypes.WinDLL('kernel32',use_last_error=True);h.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];h.CreateFileW.restype=W.HANDLE
 x=h.CreateFileW(str(p),0x80000000,7,None,3,0,None);assert x!=ctypes.c_void_p(-1).value
 try:r=s.invoke({'path':str(p),'write':False,'allowRead':True,'allowWrite':True,'allowDelete':True});assert r.get('status')=='Opened',r
 finally:h.CloseHandle(x)
def assert_share_conflict(s,p):
 h=ctypes.WinDLL('kernel32',use_last_error=True);h.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,ctypes.c_void_p,W.DWORD,W.DWORD,W.HANDLE];h.CreateFileW.restype=W.HANDLE
 x=h.CreateFileW(str(p),0x80000000,0,None,3,0,None)
 try:assert s.invoke({'path':str(p),'write':False,'allowRead':False,'allowWrite':False,'allowDelete':False}).get('status')=='SharingViolation'
 finally:h.CloseHandle(x)
def assert_not_found(s):assert s.invoke({'path':str(s.root/'absent'),'write':False,'allowRead':False,'allowWrite':False,'allowDelete':False}).get('status')=='NotFound'
def assert_write(s,p):assert s.invoke({'path':str(p),'write':True,'allowRead':True,'allowWrite':True,'allowDelete':True}).get('status')=='Opened'
def tests_environment(s,out):
 worker=compile_src(s,'env-child',r'''using System;using System.IO;class E{static void Main(string[]a){string m=a[1];string raw=Environment.GetEnvironmentVariable(m);string v=m=="cwd"?Environment.CurrentDirectory:m=="arg"?a[2]:raw??(m=="OHB_UNREQUESTED"?"<null>":"");File.WriteAllText(a[0],v);}}''')
 ck(s,'unicode-vars',lambda:run_env(s,worker,'OHB_中文','值✓'),out)
 ck(s,'case-preserve',lambda:run_env(s,worker,'OHB_CASE','MiXeD'),out)
 ck(s,'empty-value',lambda:run_env(s,worker,'OHB_EMPTY',''),out)
 ck(s,'cwd',lambda:run_env(s,worker,'cwd',str(s.root)),out)
 ck(s,'multiple-vars',lambda:run_env(s,worker,'OHB_SECOND','two'),out)
 ck(s,'nonascii-value',lambda:run_env(s,worker,'OHB_中文','温度✓'),out)
 ck(s,'inherit-only-requested',lambda:run_env(s,worker,'OHB_UNREQUESTED','<null>'),out)
 ck(s,'missing-exe',lambda:assert_missing_exe(s),out)
 ck(s,'quoted-argument',lambda:run_env(s,worker,'arg','含空格 [1]'),out)
 ck(s,'case-collision',lambda:run_collision(s,worker),out)
def run_env(s,worker,var,value):
 path=s.root/('env-'+uuid.uuid4().hex+'.txt');env={'OHB_中文':'值✓','OHB_EMPTY':'','OHB_SECOND':'two',var:value}
 req={'exe':str(worker),'cwd':str(s.root),'arguments':[str(path),var,value],'environment':env}
 r=s.invoke(req);assert r.get('status')=='Exited' and r.get('exitCode')==0,r
 assert path.read_text(encoding='utf8')==value
def assert_missing_exe(s):
 r=s.invoke({'exe':str(s.root/'absent.exe'),'cwd':str(s.root),'arguments':[],'environment':{}});assert r.get('status')=='LaunchFailed',r
def run_collision(s,worker):
 path=s.root/('collision-'+uuid.uuid4().hex+'.txt');r=s.invoke({'exe':str(worker),'cwd':str(s.root),'arguments':[str(path),'OHB_CASE','second'],'environment':{'OHB_CASE':'first','ohb_case':'second'}})
 assert r.get('status')=='Exited' and path.read_text(encoding='utf8')=='second',r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--task-root',type=Path,required=True);ap.add_argument('--workspace',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--run-id',required=True);a=ap.parse_args()
 global defs,records
 rub=json.loads((a.task_root/'tests'/'rubric.json').read_text(encoding='utf-8-sig'));defs={x['id']:x for x in rub['testcases']};records=[];errors=[];t=time.monotonic();start=base.now();sb=None
 h=hashlib.sha256()
 for p in sorted(x for x in a.task_root.rglob('*') if x.is_file()):
  rel=p.relative_to(a.task_root).as_posix().encode('utf-8');data=p.read_bytes();h.update(len(rel).to_bytes(4,'big'));h.update(rel);h.update(len(data).to_bytes(8,'big'));h.update(data)
 try:
  exe=a.workspace/'bin'/'candidate.exe';exe.parent.mkdir(parents=True,exist_ok=True)
  if not exe.exists():
   z=subprocess.run([CSC,'/nologo','/r:System.Web.Extensions.dll','/out:'+str(exe),*map(str,a.workspace.glob('*.cs'))],capture_output=True)
   if z.returncode:raise RuntimeError('candidate build failed: '+z.stderr.decode('utf8','replace'))
  sb=base.Sandbox(a.workspace,rub['task_id'])
  fn={'hardlink':tests_hardlink,'mutex':tests_mutex,'registry':tests_registry,'share':tests_share,'env':tests_environment}[rub['task_id'].split('-')[1] if False else family(rub['task_id'])]
  fn(sb,errors)
 except Exception as e:errors.append(type(e).__name__+': '+str(e))
 finally:
  if sb:
   try:sb.close()
   except Exception as e:errors.append('cleanup: '+str(e))
 for x in rub['testcases']:
  if x['id'] not in {r['id'] for r in records}:records.append(dict(id=x['id'],group=x['group'],requirement=x['requirement'],status='NOT_RUN',evidence='verifier did not reach test'))
 valid=not errors and all(x['status'] in ('PASS','FAIL') for x in records);score=int(all(x['status']=='PASS' for x in records)) if valid else None
 res=dict(task_id=rub['task_id'],task_version=rub['task_version'],task_hash=h.hexdigest(),run_id=a.run_id,validity='VALID' if valid else 'INVALID',score=score,required=[x['id'] for x in rub['testcases']],testcases=records,testcase_pass_count=sum(x['status']=='PASS' for x in records),testcase_total=len(records),elapsed_sec=round(time.monotonic()-t,3),cleanup='PASS' if not any(x.startswith('cleanup') for x in errors) else 'FAIL',infrastructure_errors=errors,termination='completed' if valid else 'verifier_infrastructure_error',started_at=start,ended_at=base.now(),runner_health=getattr(sb,'health',None))
 base.save(a.output,res);print(json.dumps(res,ensure_ascii=True));return 0 if valid and score==1 else 2 if not valid else 1
def family(t):
 if 'hardlink' in t:return 'hardlink'
 if 'mutex' in t:return 'mutex'
 if 'hkcu' in t:return 'registry'
 if 'share' in t:return 'share'
 return 'env'
if __name__=='__main__':raise SystemExit(main())
