## 反模式（质检挂 / 空耗时间）

1. **上传 zip 不含 baseline/oracle**（校准硬伤）——必须跑通且进包；**smoke 可不跑**。
2. 手册写「quality.toml 不用编写」就提交 `[quality] version=1`（同题质检 P0-2）。
3. `test.sh` 只 `pytest` 写 reward，从未 `uvx ... rewardkit`。
4. 先跑完全部难度门，再补 rewardkit → 轨迹与最终 tests 不一致，证据作废。
5. 只看 `qwen-code.txt` 体积判断卡死（session/token 可能仍在跑）。
6. Dockerfile/拉仓直连国外源，卡数十分钟还不切国内镜像。
7. 因某个 reward 数量提前杀 job；每个 job 必须完整运行 16 次，再透明更新跨 job 候选池和选样清单。
8. 删除、隐藏或只挑选部分 trial 来伪造完整 batch 的 reward 分布。
9. 无 reward 文件却当 SUCCESS / 过门。
10. 把 **超时导致的 0 分** 算进难度门有效样本（必须作废整 job 重跑）。
11. `instruction.md` 带 AI 腔（清单腔、确保/全面/综上所述、假 PRD 模板）——必须重写成人口语需求。
12. 只过难度门就交卷，跳过 baseline/oracle 或空壳 rubrics「回头再补」。
13. 验证失败 / 换仓后覆盖旧 `task/` 目录，或不带 `-YYYYMMDD-HHMM` 时间戳新建目录。
14. 成功交卷或失败换仓时 **停下来问用户要不要继续 / 重跑还是换项目**——挂机模式禁止；按 skill 自动续跑直到飞书无题。
15. 新题/重跑前 **不清理** Harbor 残留 Docker 网络/容器，带着污染环境开 16 并发。

更多见 [references/pitfalls.md](references/pitfalls.md)。