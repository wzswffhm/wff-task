# validation_report —— harbor-windows 题包目录

目录：`harbor-windows/`　｜　题数：**2**　｜　报告日期：2026-10-08

> **范围声明**：本目录当前实际交付 2 个题包（`wfflab__wfmt-215`、`wfflab__wreparse-217`）。
> 历史版本的 `_index/` 材料曾按完整仓库的 9 / 16 题范围编写，与本目录实物不符，已于 2026-10-08 按实物重新对齐。

## 一、题级验收状态

| task_id | 结构合规 | 五件套 | 题面↔测试映射 | 二值判分 | 身份一致 | 对照验证 | 多模型区分度 | Harbor 加载/构建 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| wfflab__wfmt-215 | PASS | PASS | PASS | PASS | PASS | PASS（no-change ×3 = 0.0 / Golden ×3 = 1.0） | PASS | PASS（`harbor run --path <题包>` 单题直跑，镜像由 Dockerfile 构建） | **PASS** |
| wfflab__wreparse-217 | PASS | PASS | PASS | PASS | PASS | PASS（no-change ×3 = 0.0 / Golden ×3 = 1.0） | PASS | PASS（`harbor run --path <题包>` 单题直跑，镜像由 Dockerfile 构建） | **PASS** |

## 二、对照验证实测结果

| 题 | 场景 | 运行次数 | score | 结论 |
|---|---|---|---|---|
| wfflab__wfmt-215 | no-change | 3 | 0 / 0 / 0 | 稳定 0 |
| wfflab__wfmt-215 | Golden | 3 | 1 / 1 / 1 | 稳定 1 |
| wfflab__wreparse-217 | no-change | 3 | 0 / 0 / 0 | 稳定 0 |
| wfflab__wreparse-217 | Golden | 3 | 1 / 1 / 1 | 稳定 1 |

## 三、多模型区分度

| task_id | Qwen score_sum | Opus score_sum | 准入 |
|---|---|---|---|
| wfflab__wfmt-215 | 0 | 2 | PASS |
| wfflab__wreparse-217 | 2 | 3 | PASS |

## 四、方向覆盖

| 主方向 | 题数 | task_id |
|---|---|---|
| 文件系统与路径 | 1 | wfflab__wreparse-217 |
| 编码与区域 | 1 | wfflab__wfmt-215 |

> 12 个方向中覆盖 2 个；其余 10 个方向本目录无题包（历史材料中的 9/16 题属于完整仓库范围）。

## 五、整体验收结论

**2 题均通过题级验收**（结构、判分、身份、对照验证、多模型区分度、Harbor 加载与构建）。

> 镜像 Digest：本地构建镜像尚无 registry RepoDigest，`_index/EXTERNAL_IMAGES.json` 中记录的是
> 本机 `docker images --no-trunc` 的 Image ID（`sha256:...`），作为不可变身份使用；
> 若平台要求 registry digest，需 push 后回填。

