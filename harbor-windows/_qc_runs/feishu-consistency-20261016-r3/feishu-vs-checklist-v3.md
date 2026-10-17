# 飞书返修原因 vs《Windows 评测待修复清单 v3》对照（2026-10-16 r3）

本轮执行时间：2026-10-16 15:57 之后。执行内容：

1. `git pull`（走 127.0.0.1:7897 代理，`git@github.com:` 临时重写为 HTTPS + PAT）→
   快进到 `c35062ce`（远端新增 `1bb259cf`、`c35062ce` 两个 221/218 过程记录提交）。
2. 从飞书重新拉取 4 条记录的「作业压缩包」附件并逐文件 SHA256 比对本地题包。
3. 重新读取 4 条记录的「返修原因」全文（快照见 `raw/`、`wff-reasons-r3.md`）。
4. 与桌面《Windows评测待修复清单_20261016_v3.md》（28 项）做覆盖与类别对照。

---

## 一、结论（一句话）

**不是一回事。** 飞书的返修原因是甲方对我们 **wfflab 的 215/216/219/220 四个包**（甲方ID 12/11）的质检反馈；
清单 v3 是甲方对**另外 9 个题包**（zq-id 3/30/31/32/48/49/95/96/97）的整改单。
**两边题包零重叠**，只有**问题类别约 5 类重合**；且 **216 的“Task 校验值对不上”这一类问题清单里根本没有**。

---

## 二、包级覆盖对比：完全不重叠

| 来源 | 覆盖题包 | 条目数 |
|---|---|---|
| 飞书返修原因 | `wfflab__wsparse-215`（甲方ID 12）、`wfflab__wvas-216`（甲方ID 11）、`wfflab__wcancel-219`、`wfflab__wciocp-220` | 4 包共 **17 条** |
| 清单 v3 | `delivery-12-win-agent-orchestrator-5018…`、`delivery-30-momentum-windows-launcher-key-0152…`、`delivery-31-…quote-0171…`、`delivery-35-win-registry-atomic-1.5x…`、`delivery-39-win-global-mutex-lease-1.5x…`、`windows-registry-view-reader-001…`、`credman-scope-reconcile`、`powershell__powershell-6232`、`windows-d6-002` | 9 包共 **28 项** |

核对方式：清单全文检索 `wsparse|wvas|wcancel|wciocp|wfflab|IOCP` 与 zq-id 列表，**无一条命中我们的包**；
清单的 zq-id 集合 `{3,30,31,32,48,49,95,96,97}` 也不含我们的甲方ID `11/12`。

---

## 三、类别对照：约 5 类重合，方向有差异

| 问题类别 | 清单 v3 条目 | 飞书返修条目 | 是否同类 |
|---|---|---|---|
| 候选代码与隐藏测试同进程 / 测试耦合实现 | 3-1（隐藏测试直接调私有 `spawnDetached`）、31-2（临时目录清理测试限定实现命名） | **四包第 1 条**（候选与隐藏测试同进程，权限与评分端未隔离，需补“读写测试/评分目录被拒”反例） | **同类** |
| 评分链路缺陷 | 30-1（“至少20字符”判分条件未公开）、96-3（两个评分入口规则不同） | **四包第 2 条**（基础设施故障被当普通失败，依赖缺失时仍输出 `VALID/0`，应记 `INVALID` 且正式分数为空） | **同类**（不同侧面） |
| 断言没验到题面要求 / 漏测 | 30-2、32-1、32-2、48-2、49-2、95-3、97-2 | 215-3（`regions` 实际 8192 vs 候选 8193 仍 PASS）、216-4（`file_backed_regions=[]` 仍 PASS，违反题面 B.4）、219-3（`wait` 返回 `completed` 仍 PASS，未验 cancelled 终态）、220-3（未覆盖挂起读取消/重复 close/超时窗口已完成项） | **同类** |
| 证据与对照缺失 | 31-1（失败只剩布尔值，缺逐 case 证据）、97-1（缺 golden 与空跑对照）、97-4（异常未形成有效评分） | **四包第 4 条**（缺作者写测试前的用例设计、可核验的造测可见会话，94 项里“先设计用例/不看分数改测试”无法判通过） | **同类** |
| F2P/P2P 分组与基线稳定性 | 48-1（一项 F2P 在空跑基线上已通过，分类错误） | **220-5**（第三轮 NOP 的 `p2p-keys-distinguish-handles-on-one-port` 失败：预期键 `0x22`、实际 `None`；不能宣称基线三轮 P2P 全过，也不许删用例凑通过） | **同类** |
| 环境/脚手架异常 | 97-4 | 四包第 2 条（同一类根因） | **同类** |
| 断言越界造成假阴性 | 95-1（题面外 UserName 限制）、95-2（把 target 当秘密）、96-2（指定错误 ID 的额外断言） | 无（我方问题是断言**偏弱**，方向相反） | 否 |
| 模型区分度不足 | 3-3、32-3、48-3、49-3（Qwen 与 Opus5 同为 0 分） | 无。甲方明确“原始主模型分差已检查；GLM/Kimi 免跑” | 否 |
| 镜像 OS 过旧（Server Core 2004 / 19041） | 49-1 | 无（我方已换 `windows/server:ltsc2022`，且甲方不因 `未 pin digest` 驳回） | 否 |
| 题面文字不准 / 混入模板 | 49-4、96-4 | 无 | 否 |
| 模型联网取回上游答案污染评测 | 96-1 | 无 | 否 |
| 对照模型配置不是 Opus5 | 97-3 | 无 | 否 |
| **Task 校验值与运行记录对不上** | **清单无此项** | **216-1**（独有） | 清单未覆盖 |

---

## 四、飞书返修原因逐条清点（17 条）

| 包 | 条数 | 条目 |
|---|---|---|
| 215 `wsparse` | 4 | 1 同进程隔离；2 infra→INVALID；3 `regions` 范围未与独立测量比较；4 作者证据缺失 |
| 216 `wvas` | 5 | 1 **Task 校验值与 12 份原始运行记录对不上**；2 同进程；3 infra→INVALID；4 `file_backed_regions=[]` 仍 PASS；5 作者证据缺失 |
| 219 `wcancel` | 4 | 1 同进程；2 infra→INVALID；3 未要求 cancelled 终态；4 作者证据缺失 |
| 220 `wciocp` | 5 | 1 同进程；2 infra→INVALID；3 题面 F 的取消终态/重复 close/超时窗口未覆盖；4 作者证据缺失；5 **NOP#3 P2P 不稳定** |

四包的共同末句：「目录和原始主模型分差已检查；GLM/Kimi 免跑，不因缺 evidence/metadata、source.json 或未 pin digest 驳回。」

---

## 五、216-1（“Task 校验值对不上”）根因已定位并复现

**根因：飞书附件里的 216 交付 ZIP 缺少 2 个参与身份计算的文件。**

- 缺失文件：`REFIT-2026-10-14.md`（11,623 B）、`verifier/WINDOWS_VALUE.md`（6,175 B）
- 飞书 216 ZIP：259 文件；含这两个文件的版本是 261 文件
- 甲方 `validate_model_jobs` 用包当前身份比对 12 份 job 记录，得到：

| 项 | 值 |
|---|---|
| 216 包当前 `harbor_dirhash` | `80ae0a3db4c9f9141003f6a9be8f15b3d047f846c48623a820cb5fe5fcfead8a` |
| 12 份 job 记录的身份 | `253161fb10921f9744388a4530f5559dd1f828c8660516d8249ac91c7b6b0306` |
| 结论 | **不一致** → `ctl-nop-1/2/3 was run against a different Task checksum`（甲方 QC `jobs` 门禁 FAIL） |

对照：215/219/220 三包身份与 jobs **完全一致**（`a7fbb55b…`、`032b0ec7…`、`6c128407…`），不存在该问题。

修复方向（未执行，待确认）：把这两个文件放回 216 包目录 → `harbor_dirhash` 回到 `253161fb…` 与 12 份 jobs 记录对齐 →
重新打 ZIP（= 261 文件版本）后重新上传飞书。**不得**改写 job 记录里的 Hash（甲方明令禁止）。

---

## 六、本轮“用飞书最新包替换本地题包”的执行结果

| 包 | ZIP SHA256 | ZIP 文件数 | 本地文件数 | 仅本地 | 仅 ZIP | 异内容 | 本地是否已与飞书逐字节一致 |
|---|---|---|---|---|---|---|---|
| `wfflab__wsparse-215-v1.0.0-delivery` | `a83f3622468897fa…` | 273 | 273 | 0 | 0 | 0 | ✔ |
| `wfflab__wvas-216-v1.0.0-delivery` | `edea432cacf6b3f6…` | 259 | 259 | 0 | 0 | 0 | ✔ |
| `wfflab__wcancel-219-v1.0.0-delivery` | `0ebe199eeaef5761…` | 260 | 260 | 0 | 0 | 0 | ✔ |
| `wfflab__wciocp-220-v1.0.0-delivery` | `d637d595533368b3…` | 258 | 258 | 0 | 0 | 0 | ✔ |

四个 ZIP 的 SHA256 与本会话早前下载的完全一致 → **飞书端自 2026-10-16 08:01 以来没有新版本**，
本地题包已是“飞书最新包”，替换为空操作（no-op，未改磁盘）。
附件 token 亦未变：215 `WRgRbLbrGoiZ7CxpCaKc6HaVnad`、216 `RWLzbe64voPantxxB0kcEUBMnph`、
219 `SxwFblbU7oP9dfxGj4ucaMiGnJh`、220 `GQ2cbIazfovdVDx8r45ctJnYnRf`。

---

## 七、产物

- `raw/*.json`：4 条记录的飞书原始返回（`record-get`）
- `wff-records-r3.json` / `wff-reasons-r3.md`：解析后的字段与返修原因全文
- `zip/`：本轮重新下载的 4 个飞书附件
- `compare_and_replace.py` / `r3-compare-result.json` / `r3-compare-result.md`：逐文件比对 + 身份复核
- 本文件：飞书返修原因 vs 清单 v3 对照
