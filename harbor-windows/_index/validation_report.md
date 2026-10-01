# validation_report —— harbor-windows 题包目录

目录：`harbor-windows/`　｜　题数：9　｜　报告日期：2026-10-01

> 本目录**不设批次层**。9 个题包各自独立、自包含，平铺于本目录下；
> 跨题汇总材料集中于 `_index/`。

## 一、题级验收状态

| task_id | 反事实 | 五件套 | 题面↔测试映射 | 二值判分 | 身份一致 | 对照验证 | 模型区分度 | 结论 |
|---|---|---|---|---|---|---|---|---|
| wfflab__wsync-142 | PASS | PASS | PASS | PASS | PASS | 未执行 | **FLAG（待补 K1/K3）** |
| wfflab__wreserved-201 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wads-202 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wacl-203 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wpathext-204 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wreg-205 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wencoding-206 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wps-207 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |
| wfflab__wrotate-208 | PASS | PASS | PASS | PASS | 未执行 | 未执行 | **FLAG（待补 K1–K3）** |

> 静态检查项（反事实判定、五件套、题面↔测试映射、二值判分、身份一致性）全部通过。
> `wfflab__wsync-142` 已完成本机对照验证；其余 8 题按要求「先不跑测试」，
> **对照验证与模型区分度未执行**，故整体结论为 FLAG 而非 PASS。

## 二、对照验证实测结果

| 场景 | 运行次数 | score | 结论 |
|---|---|---|---|
| no-change（wsync-142） | 3 | 0.0 / 0.0 / 0.0 | 稳定 0 |
| Golden（wsync-142） | 3 | 1.0 / 1.0 / 1.0 | 稳定 1 |
| 反例 / 等价实现（wsync-142） | 5 变体 | 0×4 / 1×1 | 通过 |
| 其余 8 题全部场景 | 0 | — | 未执行 |

## 三、静态结构校验

机器报告见 `_index/validate-report.json`（由 `skills/harbor-windows/scripts/validate_package.py` 生成）。

## 四、方向覆盖

| 主方向 | 题数 | task_id |
|---|---|---|
| 文件系统与路径 | 4 | wfflab__wsync-142, wfflab__wreserved-201, wfflab__wads-202, wfflab__wrotate-208 |
| Shell 与自动化 | 2 | wfflab__wpathext-204, wfflab__wps-207 |
| 安全与身份 | 1 | wfflab__wacl-203 |
| 系统管理 | 1 | wfflab__wreg-205 |
| 编码与区域 | 1 | wfflab__wencoding-206 |

共覆盖 12 个 Windows 主流方向中的 5 个。

## 五、整体验收结论

**暂不通过，待补齐 K1（镜像 Digest）、K2（对照验证）与 K3（多模型区分度）。**

题包本体（结构、题面、判分逻辑、身份三元组）已完成并通过静态检查；
缺口均为「尚未执行」而非「执行失败」，补齐后须升级对应题的 `task_version` 并重跑受影响环节。
