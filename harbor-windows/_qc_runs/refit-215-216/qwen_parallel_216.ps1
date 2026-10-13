# qwen_parallel_216.ps1 —— 216 的 Qwen 轮并行补跑
#
# 与主编排 relaunch_all.ps1 并行运行：主编排继续按 kimi -> glm 推进，
# 本脚本同时把 216 的 Qwen x3 跑掉，缩短总时长。
#
# 为什么可以并行：QWEN 走阿里云百炼（llm-cz4pcezs463b102x...），
# KIMI/GLM 走火山方舟（ark.cn-beijing.volces.com），上游不是同一个，
# 不存在共用 key 互相饿死的问题。KIMI 与 GLM 同属火山，所以它们仍然串行。
#
# 为什么直接调 runner.py 而不用 run_rounds.ps1：后者靠"运行前后对比 runs 目录"
# 来判断自己产出了几轮，两进程并存时会互相把对方的轮次算进来。直接调
# runner.py --runs 3 没有这个歧义；若出现 INVALID，收尾时按 run_validity 补跑。
#
# 主编排走到 Qwen 那一步时会先统计已有有效轮次，发现已达标即自动跳过，
# 因此不会重复烧额度。

$ErrorActionPreference = 'Continue'

$env:DOCKER_CONTEXT = 'desktop-windows'
$dockerBin = 'C:\Program Files\Docker\Docker\resources\bin'
if (Test-Path -LiteralPath $dockerBin) { $env:Path = $dockerBin + ';' + $env:Path }

$py = 'C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$runner = 'C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-04_outside-harbor-win\runner'
$logDir = 'C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs\refit-215-216\relaunch-logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir 'qwen-parallel-216.log'

Set-Location $runner
Add-Content -LiteralPath $log -Value ("[{0}] qwen parallel 216 start pid={1}" -f (Get-Date -Format 'HH:mm:ss'), $PID) -Encoding UTF8

& $py -X utf8 runner.py --task wfflab__wchunk-216 --mode candidate --models QWEN --runs 3 *>&1 |
    Tee-Object -FilePath $log -Append

Add-Content -LiteralPath $log -Value ("[{0}] qwen parallel 216 exit={1}" -f (Get-Date -Format 'HH:mm:ss'), $LASTEXITCODE) -Encoding UTF8
