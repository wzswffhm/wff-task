# 上游项目说明（sources/app）

本目录是题目环境，不是题目答案。

## 项目

- 名称：python-diskcache
- 仓库：https://github.com/grantjenks/python-diskcache
- 基线提交：`323787f507a6456c56cce213156a78b17073fe00`（tag v5.6.3）
- 许可证：Apache-2.0（见 `LICENSE`）
- 语言与运行时：Python 3，运行时无第三方依赖

## 目录内容

- `diskcache/`：基线提交的源码副本（`core.py`、`fanout.py`、`persistent.py`、`recipes.py`、`djangocache.py`、`cli.py`）。键值索引存放在 SQLite，值存放在独立磁盘文件。
- `setup.py`、`MANIFEST.in`、`requirements.txt`、`README.rst`、`LICENSE`：上游随包文件，用于就地安装与许可证核对。
- `Dockerfile`：Agent 工作镜像。把源码复制进 `/app` 并初始化为一个可提交的 Git 工作树，便于从基线导出二进制安全的 patch。构建期不访问网络。

## 构建与运行

```bash
docker build --network=none -t obm-trae-app:<fingerprint> .
python -c "from diskcache import Cache; c = Cache('/tmp/demo'); c['k'] = 1; print(c['k'])"
```

## 与本题的关系

上游在该基线提交上只有逐条生效的写入：每次 `set`/`delete` 立即进入索引，值文件先于索引落盘。题目要求在 `Cache` 上增加多键原子写批次，判定依据是公开 API 的可观察行为，不依赖本目录中的任何内部实现细节。
