# FIN3-WKN-153 qwen 第 4 次尝试（2026-10-12 19:00-19:51）产物保险副本

- agent 段：**成功**（terminal_reason=completed，6 件交付物齐全，cost≈7.41 USD，claude-code.txt 2.9 MB）
- verifier 段：**失败**，exit_code=judge:scorer_error
  原始报错：401 API-key is blocked（claude 退出码 1，duration 183s）
- 根因：判官凭据（~/.wff-creds/judge.env 的 JUDGE_API_KEY，尾号 oZ5EMs）被阿里云 MaaS 封禁；
  该 key 直测 qwen3.7-plus 与 qwen3.8-max-0902 均返回 401 InvalidApiKey: API-key is blocked。
- 交叉验证：models.local.json 中 qwen3.8-max / qwen3.7-plus 端点共用的 key（尾号 GC4FaQ）**可用**，
  对该 base_url 下调 qwen3.8-max-0902 与 qwen3.7-plus 均返回 HTTP 200。
- 本目录 output/ 为该模型本次真实交付物（6 件），供 verifier-only 重判复用（本题 verifier 为 shared 模式，
  harbor trial regrade 不适用，需走 -a nop + bind mount 到 /app/output 的等价路径）。
- 注意：**不要再对 g5-153-qwen 直接执行 g5_153_run.sh qwen**——该脚本会 m -rf trials/* 覆盖本次有效产物。
