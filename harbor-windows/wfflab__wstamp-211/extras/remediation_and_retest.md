# 整改与复测记录 —— wfflab__wstamp-211

## R1（2026-10-02 构建期）：反例变体判为 INVALID

- **现象**：`negative_01_content_only_sync`、`negative_03_no_attribute_transaction`
  判分为 INVALID 而非 0.0。
- **根因**：两个反例只覆盖 `sync.py` / `copier.py`，其 `from .stamps import
  set_times` 在 base 的 `stamps.py` 里没有该函数 → ImportError → 测试收集失败
  → 按 INVALID 口径处理（正确行为，不是 0 分）。
- **整改**：两个反例目录补入含 `set_times` 的正确版 `stamps.py`。
- **复测**：controls 重跑，四变体 = 0.0 / 0.0 / 0.0 / 1.0，全部符合预期。

## R2（待办）：镜像构建

- image_digest 全部为 PENDING_BUILD，task-build 完成后回写
  spec / platform_import / manifest / EXTERNAL_IMAGES.json 四处。

## R3（待办）：模型验证

- 待跑：Opus 5 ×3、Qwen3.8-Max-0902 ×3、GLM-5.3 ×1、Kimi K3 ×1；
  完成后按规范 8.2 做 `model_score_sum` 判定并回填本记录。
