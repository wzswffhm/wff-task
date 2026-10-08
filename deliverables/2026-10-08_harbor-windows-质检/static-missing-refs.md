# 甲方静态检查「referenced files are missing」逐条核对

核对方法：① 在交付包内按「相对路径后缀」匹配文件/目录；
② 未匹配到的，再在包内文本里搜索该字符串的出处（运行期路径 / 文档引用 / 解析噪声）。

## wfflab__wfmt-215

| 检查器报告缺失的引用 | 核对结论 | 证据 |
|---|---|---|
| `4/5.` | 运行期路径 / 文档引用，非交付件 | `test.ps1:49`<br>`test.ps1:49`<br>`test.ps1:49` |
| `Python312\python.exe` | 运行期路径 / 文档引用，非交付件 | `test.ps1:67`<br>`test.ps1:67`<br>`test.ps1:67` |
| `assets\sample.wfmt` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/assets/sample.wfmt` |
| `assets\sample_empty.wfmt` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/assets/sample_empty.wfmt` |
| `checks.json` | 运行期路径 / 文档引用，非交付件 | `adapter.toml:35`<br>`aggregate_results.ps1:22`<br>`run_tests.ps1:27` |
| `dev/null` | 运行期路径 / 文档引用，非交付件 | `test_patch.diff:4`<br>`patch.diff:4`<br>`patch.diff:4` |
| `logs\verifier` | 运行期路径 / 文档引用，非交付件 | `test.ps1:16`<br>`test.ps1:16`<br>`test.ps1:16` |
| `logs\verifier\reward-details.json` | **存在**（同名文件，检查器未按引用基准解析） | `extras/model_runs/_judge/opus_5_r2__verifier/reward-details.json`<br>`extras/model_runs/_judge/opus_5_r3__verifier/reward-details.json`<br>`extras/model_runs/_judge/qwen38_max_0902_r1__verifier/reward-details.json` |
| `logs\verifier\reward.json` | **存在**（同名文件，检查器未按引用基准解析） | `extras/model_runs/_judge/opus_5_r2__verifier/reward.json`<br>`extras/model_runs/_judge/opus_5_r3__verifier/reward.json`<br>`extras/model_runs/_judge/qwen38_max_0902_r1__verifier/reward.json` |
| `logs\verifier\reward.txt` | **存在**（同名文件，检查器未按引用基准解析） | `extras/model_runs/_judge/opus_5_r2__verifier/reward.txt`<br>`extras/model_runs/_judge/opus_5_r3__verifier/reward.txt`<br>`extras/model_runs/_judge/qwen38_max_0902_r1__verifier/reward.txt` |
| `pytest-results.json` | 运行期路径 / 文档引用，非交付件 | `run_tests.ps1:71`<br>`swelive_spec.json:14`<br>`swelive_spec.json:14` |
| `reference\wfmt` | **存在**（是目录，检查器按文件找） | `solution/reference/wfmt` |

## wfflab__wreparse-217

| 检查器报告缺失的引用 | 核对结论 | 证据 |
|---|---|---|
| `Audit.ps1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/Audit.ps1`<br>`solution/reference/WReparse/Audit.ps1` |
| `Model.ps1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/Model.ps1`<br>`solution/reference/WReparse/Model.ps1` |
| `PathSemantics.ps1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/PathSemantics.ps1`<br>`solution/reference/WReparse/PathSemantics.ps1` |
| `WReparse.psm1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/WReparse.psm1`<br>`solution/reference/WReparse/WReparse.psm1` |
| `WReparseCaseProbe\Sub` | 运行期路径 / 文档引用，非交付件 | `run_tests.ps1:135` |
| `WReparseTrail\Sub` | 运行期路径 / 文档引用，非交付件 | `run_tests.ps1:233` |
| `WReparseTrail\Sub\` | 运行期路径 / 文档引用，非交付件 | `run_tests.ps1:233` |
| `WReparse\WReparse.psd1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/WReparse.psd1`<br>`solution/reference/WReparse/WReparse.psd1` |
| `Walker.ps1` | **存在**（检查器查找层级/解析基准有误） | `environment/workspace/WReparse/Walker.ps1`<br>`solution/reference/WReparse/Walker.ps1` |
| `beta\zeta.txt` | 运行期路径 / 文档引用，非交付件 | `prepare.ps1:55`<br>`run_tests.ps1:314` |
| `checks.json` | **存在**（检查器查找层级/解析基准有误） | `jobs/_local_verification/checks.json` |
| `data\sample.bin` | 运行期路径 / 文档引用，非交付件 | `prepare.ps1:54` |
