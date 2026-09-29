# WSL 离线 Docker 验证证据 — 2026-09-28-3-marshmallow-doc-diff

本文件记录在本地 WSL 里复现「离线 Docker grade 契约」的原始命令与输出，用于佐证
`NOP=0 / ORACLE=1` 在容器路径下同样成立（不依赖本地 venv）。

## 环境

- WSL：Ubuntu 22.04.5 LTS，内核随 Windows
- Docker：`29.1.3`（`docker version --format '{{.Server.Version}}'`）
- 基础镜像：`python:3.12@sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7`
  - 注：Docker Hub（`registry-1.docker.io`）直连被墙，本机在 `/etc/docker/daemon.json`
    配置 registry mirror（daocloud + aliyun）后拉取成功。`--network=none` 仅约束构建/运行阶段，
    与“预先拉取基础镜像”解耦。

## 复现步骤

```
# 1. NOP 基线 app 镜像（无 document_diff）
docker build --network=none -t obm-app-nop:latest  /root/obm-test/app-nop
# 2. ORACLE app 镜像（叠加参考 schema.py，含 document_diff）
docker build --network=none -t obm-app-oracle:latest /root/obm-test/app-oracle
# 3. verifier 镜像（FROM $APP_IMAGE，离线装 pytest 等）
docker build --network=none --build-arg APP_IMAGE=obm-app-nop:latest    -t obm-ver-nop:latest    /root/obm-test/verifier
docker build --network=none --build-arg APP_IMAGE=obm-app-oracle:latest -t obm-ver-oracle:latest /root/obm-test/verifier
# 4. 运行判分（挂载 /logs/verifier，容器内写 reward.json）
docker run --rm --network=none -v /root/obm-test/nop-logs:/logs/verifier    obm-ver-nop:latest
docker run --rm --network=none -v /root/obm-test/oracle-logs:/logs/verifier obm-ver-oracle:latest
```

## 结果

### NOP（`obm-ver-nop`）→ `/logs/verifier/reward.json`

```json
{
  "reward": 0,
  "f2p": { "expected": 11, "missing": [], "passed": 0,
           "not_passed": [ "tests/test_doc_diff.py::test_add_remove_top_level_field",
                           "tests/test_doc_diff.py::test_diff_accepts_objects_via_dump",
                           "tests/test_doc_diff.py::test_identical_documents_produce_empty_list",
                           "tests/test_doc_diff.py::test_ignore_fields_skips_named_fields",
                           "tests/test_doc_diff.py::test_list_element_add_and_remove",
                           "tests/test_doc_diff.py::test_list_element_change_uses_index_path",
                           "tests/test_doc_diff.py::test_list_of_nested_compares_element_fields",
                           "tests/test_doc_diff.py::test_nested_change_recurses_with_dotted_path",
                           "tests/test_doc_diff.py::test_nested_many_add_new_element",
                           "tests/test_doc_diff.py::test_scalar_change_records_field_path",
                           "tests/test_doc_diff.py::test_unknown_field_policy_default_excludes" ] },
  "p2p": { "expected": 826, "missing": [], "not_passed": [], "passed": 826 }
}
```
容器内 `REWARD=0`，`reward.json` = `{"reward": 0}`。

### ORACLE（`obm-ver-oracle`）→ `/logs/verifier/reward.json`

```json
{
  "reward": 1,
  "f2p": { "expected": 11, "missing": [], "not_passed": [], "passed": 11 },
  "p2p": { "expected": 826, "missing": [], "not_passed": [], "passed": 826 }
}
```
容器内 `REWARD=1`，`reward.json` = `{"reward": 1}`。

## 结论

- 离线构建成功（`--network=none`，`pip install --no-index --find-links=/verifier/wheels`，
  7 个 wheel 全部本地可解）。
- 运行契约正确：verifier 容器内写出 `/logs/verifier/reward.json`，与 `verify_agent_patch.py --docker` 的读取路径一致。
- **NOP=0（F2P 0/11、P2P 826/826），ORACLE=1（F2P 11/11、P2P 826/826）**，与本地
  `run_local_verifier.py` 结果一致，容器路径判分可信。

## 遗留（非阻塞）

- `verify_agent_patch.py` 只把 `model.patch` 存进 artifacts，**不**自动打进 `/app/marshmallow`；
  线上 harness 需在 grade 前应用补丁（或把应用步骤接进 app 镜像构建）。
- Trae 为 GUI 工作流，无 CLI 驱动，双跑实验需在 Trae 主机人工执行。
