# OBM 跑题与质检移交包

这个目录是给其他执行者使用的本地入口。解压后，直接对 Codex/执行代理说：

- `质检 D:\hc\obm\result\xxx.zip`
- `质检 result 下所有包`
- `跑题 3 个`
- `只跑这个候选 D:\hc\obm\cache\runs\...\candidates\...`

代理应加载本目录的 `SKILL.md`，再调用 `scripts/obm-dispatch.ps1`。详细配置在 `config/obm.paths.example.json` 和 `references/dispatch.md`。

## 包含内容

- `SKILL.md`：中文指令路由和安全边界。
- `scripts/obm-dispatch.ps1`：质检与批量跑题总入口。
- `config/`：不含密钥的路径与镜像配置模板。
- `vendor/obm-question-production/`：跑题、Trae、冻结、独立 verifier 和交付规则快照。
- `vendor/obm-review-skills/`：本地质检脚本、映射和审查模板快照（不含 Python 缓存）。

## 不包含内容

不会打包 Doubao key、DPAPI 密文、Trae 轨迹、候选工作区、标准答案、隐藏 verifier、Docker volume 或飞书凭据。运行证据仍留在目标机的 `cache`，交付结果仍留在 `result`。

## 当前版本提示

正式执行前应重新读取目标机上的最新版 `D:\hc\obm\质检工具\obm-review-skills` 和 `D:\hc\obm\需求`；`vendor` 只是本次打包时的离线快照，不能覆盖更新后的官方规则。
