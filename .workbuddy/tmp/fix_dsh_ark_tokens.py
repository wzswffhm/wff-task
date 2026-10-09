# -*- coding: utf-8 -*-
"""修复 DSH 中 ark provider 模型容量字段留空导致的「输出被截断」。

问题：`~/.dsh/profiles/desktop/cordis.patch.yml` 里 ark 的 3 个模型只写了
      id + name，容量字段留空 -> 回落到 llm-pi-ai 的 route 级 defaultMaxTokens
      （asar 内出现的量级为 16384 / 32000），而 deepseek-v4-1-flash 带 thinking，
      思考 token 计入输出预算 -> 很快触顶 -> DSH 提示「已达到输出 token 上限」。

修复：显式补 contextWindow + maxTokens（取值对齐历史 env 备份：
      KIMI_MAX_TOKENS=32000 / GLM_MAX_TOKENS=65536；v4.1-flash 取 65536）。

安全：① 先备份为 .bak-YYYYMMDD-HHMMSS；② 只替换 ark 那一段（断言命中 1 次）；
      ③ 改后用 YAML 解析校验（无 PyYAML 时退回结构性检查）；④ 不重启/不重载应用。
"""
import datetime
import os
import pathlib
import shutil
import sys

P = pathlib.Path(os.path.expanduser(r"~\.dsh\profiles\desktop\cordis.patch.yml"))
if not P.is_file():
    print(f"配置不存在: {P}")
    sys.exit(2)

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak = P.with_name(P.name + f".bak-{stamp}")
shutil.copy2(P, bak)
print(f"已备份: {bak.name}")

OLD = """          - id: kimi-k2-thinking-251104
            name: kimi-k2
          - id: glm-5-3-flash-260828
            name: glm-5-3-flash
          - id: deepseek-v4-1-flash-260910
            name: deepseek-v4-1-flash"""

NEW = """          - id: kimi-k2-thinking-251104
            name: kimi-k2
            contextWindow: 262144
            maxTokens: 32768
          - id: glm-5-3-flash-260828
            name: glm-5-3-flash
            contextWindow: 262144
            maxTokens: 65536
          - id: deepseek-v4-1-flash-260910
            name: deepseek-v4-1-flash
            contextWindow: 262144
            maxTokens: 65536"""

text = P.read_text(encoding="utf-8")
n = text.count(OLD)
if n != 1:
    print(f"!! 目标片段命中 {n} 次（期望 1），已中止，未修改文件")
    sys.exit(1)

text = text.replace(OLD, NEW)
P.write_text(text, encoding="utf-8", newline="\n")
print("已写入修复")

# ---- 校验 -------------------------------------------------------------------
try:
    import yaml  # type: ignore
    doc = yaml.safe_load(P.read_text(encoding="utf-8"))
    provs = {}
    for entry in doc:
        cfg = (entry or {}).get("config") or {}
        if "providers" in cfg:
            provs = cfg["providers"]
    ark = provs.get("ark", {})
    print("\nYAML 解析 OK。ark 模型容量：")
    for m in ark.get("models", []):
        print(f"   {m.get('id'):34} contextWindow={m.get('contextWindow')} maxTokens={m.get('maxTokens')}")
    assert all(m.get("maxTokens") for m in ark.get("models", [])), "仍有模型缺 maxTokens"
    print("校验通过：ark 全部模型均已显式声明 maxTokens")
except ImportError:
    print("\n(无 PyYAML，退回结构检查)")
    seg = P.read_text(encoding="utf-8")
    assert seg.count("maxTokens:") >= 5, "maxTokens 数量异常"
    print("结构检查通过")
