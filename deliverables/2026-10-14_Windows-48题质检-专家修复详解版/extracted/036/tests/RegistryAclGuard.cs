using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Threading;

// Native NT registry notification and ACL fault fixture. No candidate functions are hooked.
public sealed class RegistryAclGuard : IDisposable {
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode)] static extern int RegOpenKeyEx(IntPtr hive,string sub,int options,int access,out IntPtr handle);
    [DllImport("advapi32.dll")] static extern int RegCloseKey(IntPtr handle);
    [DllImport("advapi32.dll")] static extern int RegGetKeySecurity(IntPtr key,int info,byte[] descriptor,ref uint length);
    [DllImport("advapi32.dll")] static extern int RegSetKeySecurity(IntPtr key,int info,byte[] descriptor);
    [DllImport("advapi32.dll", EntryPoint="RegSetKeySecurity")] static extern int RegSetKeySecurityPtr(IntPtr key,int info,IntPtr descriptor);
    [DllImport("advapi32.dll", CharSet=CharSet.Unicode,SetLastError=true)] static extern bool ConvertStringSecurityDescriptorToSecurityDescriptor(string sddl,int revision,out IntPtr descriptor,out uint length);
    [DllImport("advapi32.dll")] static extern int RegNotifyChangeKeyValue(IntPtr key,bool subtree,int filter,IntPtr signal,bool asynchronous);
    [DllImport("kernel32.dll")] static extern IntPtr LocalFree(IntPtr memory);
    readonly IntPtr key;
    readonly byte[] original;
    readonly ManualResetEvent cancel=new ManualResetEvent(false);
    readonly AutoResetEvent changed=new AutoResetEvent(false);
    Thread worker;
    public volatile bool Applied;
    public Exception Error;
    static void Check(int code){if(code!=0)throw new Win32Exception(code);}
    public RegistryAclGuard(string sub){
        Check(RegOpenKeyEx(new IntPtr(unchecked((int)0x80000001)),sub,0,0x60010,out key));
        uint length=0;int status=RegGetKeySecurity(key,4,null,ref length);
        if(status!=122)Check(status);
        original=new byte[length];Check(RegGetKeySecurity(key,4,original,ref length));
    }
    public void DenyWrites(){
        string sid=WindowsIdentity.GetCurrent().User.Value;
        IntPtr descriptor;uint length;
        string sddl="D:(D;;0x2;;;"+sid+")(A;;KA;;;"+sid+")(A;;KA;;;SY)(A;;KA;;;BA)";
        if(!ConvertStringSecurityDescriptorToSecurityDescriptor(sddl,1,out descriptor,out length))throw new Win32Exception(Marshal.GetLastWin32Error());
        try{Check(RegSetKeySecurityPtr(key,4,descriptor));Applied=true;}finally{LocalFree(descriptor);}
    }
    public void AfterNextWrite(){
        Check(RegNotifyChangeKeyValue(key,false,4,changed.SafeWaitHandle.DangerousGetHandle(),true));
        worker=new Thread(()=>{try{if(WaitHandle.WaitAny(new WaitHandle[]{changed,cancel})==0)DenyWrites();}catch(Exception e){Error=e;}});
        worker.IsBackground=true;worker.Start();
    }
    public void Stop(){cancel.Set();if(worker!=null && !worker.Join(5000))throw new Exception("Registry notification worker did not finish");if(Error!=null)throw new Exception("Registry ACL fixture failed",Error);}
    public void Dispose(){try{Stop();Check(RegSetKeySecurity(key,4,original));}finally{RegCloseKey(key);changed.Dispose();cancel.Dispose();}}
}
