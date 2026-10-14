param([string]$WorkspaceRoot,[string]$OutputPath)
$ErrorActionPreference='Stop'
$candidate=Join-Path $WorkspaceRoot 'candidate.ps1';$rows=[Collections.Generic.List[object]]::new();$manifestDef=Get-Content (Join-Path $PSScriptRoot 'rubric.json') -Raw|ConvertFrom-Json
$active='preflight';$fixture=$null;$reg=$null;$shell=$null
function Infra([scriptblock]$body){try{&$body}catch{$_.Exception.Data['VerifierInfrastructure']=$true;throw}}
function Call([hashtable]$p){try{$r=@(&$candidate @p);if($r.Count-ne1){throw 'Exactly one result required'};$r[0]}catch{$_.Exception.Data['CandidateFailure']=$true;throw}}
function Rejected($r){$r.Status-ceq'rejected'-and-not[string]::IsNullOrWhiteSpace($r.Error)}
function Case($id,$group,[scriptblock]$body){
 $script:active=$id;$script:fixture=Join-Path $WorkspaceRoot ('fixture-'+[guid]::NewGuid().ToString('N'));$script:manifest=Join-Path $fixture '中文 [清单].json';$script:root=Join-Path $fixture '中文 [links]';$script:reg='Software\OutsideHarborEnvProfiles\'+[guid]::NewGuid().ToString('N')
 $status='FAIL';$detail=''
 try{Infra {[IO.Directory]::CreateDirectory($fixture)|Out-Null};if((&$body)-eq$true){$status='PASS'}}catch{$detail=$_.Exception.Message;if($_.Exception.Data['VerifierInfrastructure']-and-not$_.Exception.Data['CandidateFailure']){$status='ERROR'}}finally{try{CleanupFixture}catch{$status='ERROR';$detail='Fixture cleanup: '+$_.Exception.Message}}
 $rows.Add([pscustomobject]@{id=$id;group=$group;status=$status;detail=$detail})
}

function CleanupFixture{if($reg){[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($reg,$false)};if($fixture-and(Test-Path -LiteralPath $fixture)){Remove-Item -LiteralPath $fixture -Recurse -Force}}
function Save($vars){Infra {[ordered]@{version=1;variables=@($vars)}|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $manifest -Encoding utf8}}
function Variable($name='CACHE_HOME',$value='%USERPROFILE%\中文 缓存',$expand=$true){[pscustomobject]@{name=$name;value=$value;expand=$expand}}
function Native($name){Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{if(-not$k-or$k.GetValueNames()-inotcontains$name){return $null};[pscustomobject]@{Kind=$k.GetValueKind($name).ToString();Raw=$k.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)}}finally{if($k){$k.Dispose()}}}}
function Synced($r,$vars){if($r.Status-cne'synced'-or$r.Written-ne$vars.Count-or$r.Error-cne''-or@($r.Variables).Count-ne$vars.Count){return $false};for($i=0;$i-lt$vars.Count;$i++){$native=Native $vars[$i].name;$x=$r.Variables[$i];if($null-eq$native-or$x.Name-cne$vars[$i].name-or$x.Kind-cne$native.Kind-or$x.RawValue-cne$native.Raw){return $false}};$true}
function Reject($r){(Rejected $r)-and$r.Written-eq0-and@($r.Variables).Count-eq0}
function Sync{Call @{ProfileSubKey=$reg;ManifestPath=$manifest}}
function Snapshot{Infra {
  function Walk($path){$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($path);try{if(-not$k){'M:'+ $path;return};'K:'+ $path;foreach($n in @($k.GetValueNames()|Sort-Object)){$v=$k.GetValue($n,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames);$raw=if($v-is[byte[]]){[Convert]::ToHexString($v)}else{ConvertTo-Json -InputObject $v -Compress};'V:'+$path+'|'+$n+'|'+$k.GetValueKind($n)+'|'+$raw};foreach($sub in @($k.GetSubKeyNames()|Sort-Object)){Walk ($path+'\'+$sub)}}finally{if($k){$k.Dispose()}}};@(Walk $reg)-join"`n"
}}
function Seed{Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);try{$k.SetValue('CACHE_HOME','before','String');$k.SetValue('Keep',[byte[]]@(7,0,255),'Binary');$k.CreateSubKey('empty child').Dispose();$sub=$k.CreateSubKey('nested');try{$sub.SetValue('old',42,'DWord')}finally{$sub.Dispose()}}finally{$k.Dispose()}}}
try{
 Infra {$probe='Software\OutsideHarborEnvProfiles\preflight-'+[guid]::NewGuid().ToString('N');try{$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($probe);try{$k.SetValue('probe','%TEMP%\synthetic','ExpandString');if($k.GetValueKind('probe').ToString()-cne'ExpandString'-or$k.GetValue('probe',$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)-cne'%TEMP%\synthetic'){throw 'Registry cannot roundtrip native kind/raw'}}finally{$k.Dispose()}}finally{[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($probe,$false)}}
 Case native_kind_raw_and_report F2P {$a=Variable;$b=Variable 'LITERAL' '%TEMP%\literal' $false;$vars=@($a,$b);Save $vars;$r=Sync;$x=Native $a.name;$y=Native $b.name;(Synced $r $vars)-and$x.Kind-ceq'ExpandString'-and$x.Raw-ceq$a.value-and$y.Kind-ceq'String'-and$y.Raw-ceq$b.value}
 Case migration_repeat_empty_value F2P {Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($reg);try{$k.SetValue('cache_home',17,'DWord')}finally{$k.Dispose()}};$vars=@((Variable 'CACHE_HOME' '' $false));Save $vars;$r=Sync;$q=Sync;$x=Native 'cache_home';$names=Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{@($k.GetValueNames())}finally{$k.Dispose()}};(Synced $r $vars)-and(Synced $q $vars)-and$x.Kind-ceq'String'-and$x.Raw-ceq''-and@($names).Count-eq1}
 Case empty_manifest_no_key F2P {Save @();$r=Sync;$absent=Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg);try{$null-eq$k}finally{if($k){$k.Dispose()}}};$r.Status-ceq'synced'-and$r.Written-eq0-and$r.Error-ceq''-and@($r.Variables).Count-eq0-and$absent}
 Case unrelated_tree_preserved P2P {Seed;$keep=Native 'Keep';Save @(Variable);$null=Sync;$x=Native 'Keep';$sub=Infra {$k=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($reg+'\empty child');try{$null-ne$k}finally{if($k){$k.Dispose()}}};$x.Kind-ceq'Binary'-and[Convert]::ToHexString([byte[]]$x.Raw)-ceq'0700FF'-and$sub}
 Case duplicate_input_no_change P2P {Seed;$before=Snapshot;Save @((Variable 'CACHE_HOME'),(Variable 'cache_home' 'new'));$r=Sync;(Reject $r)-and$before-ceq(Snapshot)}
 Case invalid_namespace_no_real_environment_write P2P {Save @(Variable);$r=Call @{ProfileSubKey='Environment';ManifestPath=$manifest};Reject $r}
 Case invalid_manifest_no_partial_write P2P {Seed;$before=Snapshot;$a=Variable;$b=Variable 'SECOND';$b.expand='true';Save @($a,$b);$r=Sync;(Reject $r)-and$before-ceq(Snapshot)}
 Case all_declared_input_rejections P2P {
  Seed;$before=Snapshot;$a=Variable 'CACHE_HOME' 'must never apply';$variants=[Collections.Generic.List[object]]::new()
  foreach($n in @('','A=B',("A"+[char]0+"B"))){$variants.Add(@{version=1;variables=@($a,(Variable $n))})}
  foreach($field in @('name','value','expand')){$b=Variable 'SECOND';$b.PSObject.Properties.Remove($field);$variants.Add(@{version=1;variables=@($a,$b)});$b=Variable 'SECOND';$b.$field=17;$variants.Add(@{version=1;variables=@($a,$b)})}
  $variants.Add(@{version=2;variables=@($a)});$variants.Add(@{version=1;variables=@{name='wrong-array'}});$ok=$true
  foreach($doc in $variants){Infra {$doc|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $manifest -Encoding utf8};$r=Sync;$ok=$ok-and(Reject $r)-and$before-ceq(Snapshot)};$ok
 }

}catch{foreach($req in $manifestDef.required){if(-not@($rows|Where-Object id -eq $req.id).Count){$rows.Add([pscustomobject]@{id=$req.id;group=$req.group;status='ERROR';detail='Verifier preflight/outer infrastructure: '+$_.Exception.Message})}}}finally{if($shell){try{[Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell)|Out-Null}catch{foreach($r in $rows){$r.status='ERROR';$r.detail='COM cleanup failure'}}}}
$valid=$rows.Count-eq$manifestDef.required.Count
foreach($req in $manifestDef.required){$m=@($rows|Where-Object{$_.id-ceq$req.id-and$_.group-ceq$req.group});if($m.Count-ne1-or$m[0].status-notin@('PASS','FAIL')){$valid=$false}}
$validity=if($valid){'VALID'}else{'INVALID'};$score=if($valid){[int](@($rows|Where-Object status -ne 'PASS').Count-eq0)}else{$null}
$null=New-Item -ItemType Directory -Path (Split-Path -Parent ([IO.Path]::GetFullPath($OutputPath))) -Force
@{validity=$validity;score=$score;required=$manifestDef.required;testcases=$rows.ToArray();testcase_pass_count=@($rows|Where-Object status -eq 'PASS').Count;testcase_total=$manifestDef.required.Count;fixture_cleaned=(-not($fixture-and(Test-Path -LiteralPath $fixture)))}|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $OutputPath -Encoding utf8
if(-not$valid){exit 2};if($score){exit 0};exit 1
