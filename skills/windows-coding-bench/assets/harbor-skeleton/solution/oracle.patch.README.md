# solution/oracle.patch —— 参考解补丁（骨架占位）

<!--
============================================================
solution/ 目录规范
============================================================

【用途】
  - 提供**可执行的参考解**，仅用于 Golden 验证（Golden 必须稳定得 1）
  - **严禁**进入 Agent 可见环境、评测镜像、Git 历史或任何被测工作区

【形态】
  - 首选：`oracle.patch`（标准 git diff，可 `git apply` 回放到 base commit）
  - 备选：`golden_output/`（参考输出产物）+ `README.md` 说明应用方式
  - 无论哪种，都必须能被**独立复现**：干净环境 + base commit + 本补丁 = Golden 通过

【硬性要求】
  1. Golden 必须有**直接证据**证明参考解已实际应用，
     不能只依赖环境变量、任务名或日志标题。
  2. Golden 与题面冲突时 → 修题目/测试/参考解，**不得改题意凑 Golden=1**。
  3. 补丁与 test_patch 必须**相互独立审查**。
  4. Golden 3 次独立运行均为 1，无 SKIP / MISSING / ERROR / 旧产物复用。

【生成方式】
  cd <repo-checkout-at-base-commit>
  # 手工或脚本实现参考解 ...
  git diff > oracle.patch
  # 或分类产出产物：
  #   git diff > solution/oracle.patch
  #   cp -r <产出目录> solution/golden_output/

【自检】
  - [ ] oracle.patch 能在干净 base 上 `git apply --check` 通过
  - [ ] 应用后所有 required F2P 全过、P2P 全过
  - [ ] 与 instruction.md 描述的行为一致（不多做、不少做）
  - [ ] 未泄漏到 environment/ 或 tests/
============================================================
-->

此文件为骨架占位，请替换为真实的 `oracle.patch`，或删除本文件并放入 `golden_output/`。
