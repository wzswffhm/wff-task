"""Assemble the deepSWE task package for the pycasbin decision-trace task.

Idempotent: wipes and rebuilds ``output/deepSWE_2026-09-29-1-pycasbin-decision-trace``.

Layout produced:
  proposal.json                       (written separately)
  sources/README.md
  sources/app/{<repo>/, Dockerfile, wheels/, upstream.tar.gz}
  sources/skill/SKILL.md
  sources/verifier/{Dockerfile, config.json, grader.py, test.sh, test.patch,
                    tests/, examples/, wheels/}
  sources/provenance/provenance.json
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

OBM = Path(r"C:/Users/Administrator/Desktop/OBM")
REPO = OBM / "work" / "upstream" / "pycasbin"
WORK = OBM / "work" / "2026-09-29-1-pycasbin-decision-trace"
OUT = OBM / "output" / "deepSWE_2026-09-29-1-pycasbin-decision-trace"
PY = OBM / ".venv" / "Scripts" / "python.exe"

TASK_ID = "2026-09-29-1"
PROPOSAL_NAME = "2026-09-29-1-pycasbin-decision-trace"
UPSTREAM = "casbin/pycasbin"
BASE_COMMIT = "bf5a94be899c3eb14e9d9509904a3b38d9f2cf71"
COMMIT_DATE = "2026-08-13 13:58:49 +0800"
LICENSE = "Apache-2.0"
LANGUAGE = "Python"

APP_IMAGE = (
    "python:3.12@sha256:"
    "4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7"
)

F2P_MODULE = "tests/test_decision_trace.py"

# Verifier test modules: upstream tests that live directly under tests/ so that
# grader.py's classname -> node-id reconstruction (parts[0]/parts[1].py) is exact.
P2P_MODULES = [
    "tests/test_cached_enforcer.py",
    "tests/test_distributed_api.py",
    "tests/test_enforcer.py",
    "tests/test_fast_enforcer.py",
    "tests/test_filter.py",
    "tests/test_frontend.py",
    "tests/test_management_api.py",
    "tests/test_rbac_api.py",
    "tests/test_synced_enforcer.py",
    "tests/test_watcher_ex.py",
]


def run(cmd, cwd=None, check=True):
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("command failed: {}".format(cmd))
    return result


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reset_out():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "sources").mkdir(parents=True)


def stage_app():
    """Extracts the base commit into sources/app and adds the OBM build files."""
    app = OUT / "sources" / "app"
    app.mkdir(parents=True)
    archive = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "archive", "--format=tar", BASE_COMMIT],
        cwd=str(REPO),
        capture_output=True,
        check=True,
    )
    with tarfile.open(fileobj=__import__("io").BytesIO(archive.stdout)) as tar:
        tar.extractall(app, filter="data")
    if (app / "casbin" / "trace.py").exists():
        raise SystemExit("sources/app must not contain the reference implementation")

    shutil.copytree(WORK / "wheels", app / "wheels")
    shutil.copyfile(WORK / "templates" / "app.Dockerfile", app / "Dockerfile")

    tarball = app / "upstream.tar.gz"
    with open(tarball, "wb") as handle:
        handle.write(
            subprocess.run(
                [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "archive",
                    "--format=tar.gz",
                    "--prefix=pycasbin/",
                    BASE_COMMIT,
                ],
                cwd=str(REPO),
                capture_output=True,
                check=True,
            ).stdout
        )
    return app


def stage_verifier(app):
    verifier = OUT / "sources" / "verifier"
    verifier.mkdir(parents=True)

    # The whole upstream test tree is copied verbatim: tests/__init__.py imports
    # every sub-package, so trimming it would break `import tests`. The F2P
    # module is appended; P2P node ids are then restricted to the modules that
    # live directly under tests/ (see collect_node_ids).
    shutil.copytree(app / "tests", verifier / "tests")
    shutil.copyfile(REPO / F2P_MODULE, verifier / "tests" / Path(F2P_MODULE).name)

    shutil.copytree(app / "examples", verifier / "examples")
    shutil.copytree(WORK / "wheels", verifier / "wheels")

    for name in ("grader.py", "test.sh"):
        shutil.copyfile(WORK / "templates" / name, verifier / name)
    shutil.copyfile(WORK / "templates" / "verifier.Dockerfile", verifier / "Dockerfile")
    return verifier


def collect_node_ids(verifier, app):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(app), str(verifier)])
    result = subprocess.run(
        [
            str(PY),
            "-m",
            "pytest",
            str(verifier / "tests"),
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "--no-header",
            "-o",
            "addopts=",
        ],
        cwd=str(verifier),
        env=env,
        capture_output=True,
        text=True,
    )
    nodes = [line.strip() for line in result.stdout.splitlines() if "::" in line]
    if not nodes:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("collection produced no node ids")

    f2p = [n for n in nodes if n.startswith(F2P_MODULE + "::")]
    # grader.py rebuilds a node id as "<pkg>/<module>.py::<name>", which is only
    # exact for modules sitting directly under tests/. Nested packages collect
    # under a mangled id and are therefore not gradeable.
    p2p = [n for n in nodes if n.startswith("tests/") and n.count("/") == 1 and n not in f2p]
    if len(f2p) < 71 or len(p2p) < 71:
        raise SystemExit("F2P/P2P floor not met: {} / {}".format(len(f2p), len(p2p)))
    return sorted(f2p), sorted(p2p)


def write_config(verifier, f2p, p2p):
    config = {
        "benchmark": "deepSWE",
        "task_id": TASK_ID,
        "proposal_name": PROPOSAL_NAME,
        "grader": "grader.py",
        "test_entry": "test.sh",
        "test_patch": "test.patch",
        "network": False,
        "timeout_seconds": 900,
        "scoring": {
            "type": "binary",
            "reward_1_when": "every F2P and every P2P test reports passed",
            "missing_test_counts_as": "failed",
            "skipped_counts_as": "failed",
            "duplicate_node_id": "keep the worst outcome",
        },
        "f2p_node_ids": f2p,
        "p2p_node_ids": p2p,
    }
    (verifier / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def write_test_patch(verifier):
    subprocess.run(["git", "add", "-N", F2P_MODULE], cwd=str(REPO), check=True)
    try:
        diff = subprocess.run(
            ["git", "diff", "--", F2P_MODULE], cwd=str(REPO), capture_output=True, text=True, check=True
        ).stdout
    finally:
        subprocess.run(["git", "reset", "-q", "--", F2P_MODULE], cwd=str(REPO), check=True)
    if not diff.strip():
        raise SystemExit("test.patch would be empty")
    # The dev checkout is CRLF (core.autocrlf=true) while the packaged tree is
    # LF; normalize so the patch applies inside the verifier regardless of the
    # applying side's eol configuration.
    (verifier / "test.patch").write_text(
        diff.replace("\r\n", "\n"), encoding="utf-8", newline="\n"
    )


def write_readme(app, verifier, f2p, p2p):
    text = """# 题包文件说明（sources）

本目录是 `{proposal}` 正式题包的 `sources`，逐项说明如下。

## app/

上游仓库 `{upstream}` 在基线提交 `{commit}`（{date}）的源码副本，保留仓库原始布局（`casbin/`、`tests/`、`examples/`、`pyproject.toml`、`LICENSE`、`README.md`、`CHANGELOG.md` 等），另加 Agent 环境的 `Dockerfile`、离线依赖 `wheels/`，以及该基线提交的归档 `upstream.tar.gz`（顶层目录 `pycasbin/`）。**本目录不含参考实现**：`casbin/trace.py` 与 `tests/test_decision_trace.py` 均由补丁注入。

## skill/

中文专家 skill `SKILL.md`，按本题难点分节给出契约模型、冲突关系、决策方法与验证思路，不暴露参考实现、测试名或固定断言；仅作为 with-skill 提示词上下文，不安装为项目级 skill。

## verifier/

行为级评测器：

- `grader.py`：在**已应用 Agent 补丁**的源码上运行 pytest 并解析 junit-xml，按 `config.json` 的 `f2p_node_ids` 与 `p2p_node_ids` 判定，只有全部 F2P 与全部 P2P 通过时输出 `REWARD=1`。Agent 补丁由评测编排器（`verify_agent_patch.py`）在构建评测镜像前应用到 `sources/app` 的暂存副本，`test.sh` 负责写入 `/logs/verifier/reward.json`。
- `config.json`：评测配置，含 {n_f2p} 个 F2P 节点与 {n_p2p} 个 P2P 节点。
- `tests/`：行为测试套件。`test_decision_trace.py` 为新增功能测试（F2P）；其余 {n_mod} 个上游测试模块为回归测试（P2P），与 `app/` 中的副本内容一致，使评测不受 Agent 改动测试的影响。
- `examples/`：上游 `examples/` 的独立副本，供回归测试解析模型与策略文件（上游 `get_examples()` 以测试文件所在目录的 `../examples/` 为准）。
- `test.patch`：将 F2P 测试注入基线的工作区补丁（与 `tests/test_decision_trace.py` 内容一致）。
- `Dockerfile` 与 `test.sh`：离线评测环境；`test.sh` 为执行入口。
- `wheels/`：离线依赖（pytest 及其运行依赖，以及上游运行/测试所需的 simpleeval、wcmatch、bracex）。

## provenance/

`provenance.json`：来源、基线提交、许可证、复现命令，以及 `app/` 下每个文件的 sha256 散列，便于复核与复算归档散列。

## 题目契约

公开任务契约在 `proposal.json` 的自然语言字段中（A 修改设想 / B 修改细节 / C Agent 任务 / D 难点），不在本目录重复。verifier 只判定可观察行为：`enforce_traced` 返回的 `allowed` 是否与 `enforce()` 一致、`matched` 的求值顺序与早停边界、`decisive` 的归属、`effect` 的取值、空策略/禁用/`EnforceContext`/`eval()`/域与角色继承等分支，以及 `would_change` 的沙箱语义与不得污染 enforcer 的约束；不与任何参考补丁比对。

## 复现命令

```sh
docker build --network=none -t {name}-app sources/app
docker build --network=none --build-arg APP_IMAGE={name}-app -t {name}-verifier sources/verifier
docker run --rm --network=none {name}-verifier
```
""".format(
        proposal=PROPOSAL_NAME,
        upstream=UPSTREAM,
        commit=BASE_COMMIT,
        date=COMMIT_DATE,
        n_f2p=len(f2p),
        n_p2p=len(p2p),
        n_mod=len(P2P_MODULES),
        name=PROPOSAL_NAME,
    )
    (OUT / "sources" / "README.md").write_text(text, encoding="utf-8")


def write_provenance(app):
    files = []
    for path in sorted(app.rglob("*")):
        if path.is_file() and path.name != "upstream.tar.gz":
            files.append(
                {
                    "path": str(path.relative_to(OUT / "sources")).replace(os.sep, "/"),
                    "sha256": sha256_of(path),
                }
            )
    provenance = {
        "proposal_name": PROPOSAL_NAME,
        "upstream_repo": UPSTREAM,
        "upstream_url": "https://gitee.com/mirrors/pycasbin",
        "base_commit_hash": BASE_COMMIT,
        "commit_date": COMMIT_DATE,
        "base_commit_subject": "fix: restore broken star history chart (#431)",
        "license": LICENSE,
        "language": LANGUAGE,
        "upstream_archive": {
            "path": "sources/app/upstream.tar.gz",
            "top_level_dir": "pycasbin/",
            "sha256": sha256_of(app / "upstream.tar.gz"),
            "created_with": "git archive --format=tar.gz --prefix=pycasbin/ {}".format(BASE_COMMIT),
        },
        "app_image": APP_IMAGE,
        "reproduce": [
            "git clone https://gitee.com/mirrors/pycasbin && cd pycasbin",
            "git checkout {}".format(BASE_COMMIT),
            "git archive --format=tar.gz --prefix=pycasbin/ {} -o upstream.tar.gz".format(BASE_COMMIT),
        ],
        "reference_implementation": {
            "note": "The reference patch is intentionally NOT part of sources/app.",
            "files": ["casbin/trace.py", "casbin/core_enforcer.py", "casbin/__init__.py", F2P_MODULE],
        },
        "file_count": len(files),
        "files": files,
    }
    prov_dir = OUT / "sources" / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)
    (prov_dir / "provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    return provenance


def main():
    reset_out()
    app = stage_app()
    verifier = stage_verifier(app)
    f2p, p2p = collect_node_ids(verifier, app)
    write_config(verifier, f2p, p2p)
    write_test_patch(verifier)
    write_readme(app, verifier, f2p, p2p)
    provenance = write_provenance(app)
    print("F2P nodes : {}".format(len(f2p)))
    print("P2P nodes : {}".format(len(p2p)))
    print("app files : {}".format(provenance["file_count"]))
    print("output    : {}".format(OUT))


if __name__ == "__main__":
    main()
