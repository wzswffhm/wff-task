"""更新三份交付文档的批次代号与版本号（批次代号全局替换；版本号只改当前声明处）。

安全边界：
  - 批次代号：旧字符串（如 work_fin-b01_20261005_fix6-149）在文档中仅用于「当前批次」
    标识，历史批次用的是更早代号（fix5 等），故全局替换安全。
  - 版本号：文档中存在「1.0.2 定档」这类**历史叙述**，绝不能全局替换，
    只改当前声明处：表格 `[task].version` 行、打包日期行、文末版本说明。
"""
import argparse
import pathlib
import re

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")

TASKS = {
    "149": dict(
        batch_dir="work-金融-资产管理-20261008",
        old_batch="work_fin-b01_20261005_fix6-149",
        old_ver="1.0.6", new_ver="1.0.7",
    ),
    "150": dict(
        batch_dir="work-金融-私募股权投资-20261008",
        old_batch="work_fin-b01_20261006_fix2-150",
        old_ver="1.0.3", new_ver="1.0.4",
    ),
    "151": dict(
        batch_dir="work-金融-商业银行-20261008",
        old_batch="work_fin-b01_20261006-151",
        old_ver="1.0.1", new_ver="1.0.2",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    for tid, cfg in TASKS.items():
        f = H / cfg["batch_dir"] / "交付文档.md"
        text = f.read_text(encoding="utf-8")
        orig = text
        print("=" * 84)
        print(f"FIN3-WKN-{tid}  {f.name}  ({len(text)} 字符)")

        # ---- 1) 批次代号全局替换 ----
        n_batch = text.count(cfg["old_batch"])
        text = text.replace(cfg["old_batch"], cfg["batch_dir"])
        print(f"  批次代号 {cfg['old_batch']} -> {cfg['batch_dir']}：替换 {n_batch} 处")

        # ---- 2) 版本号：只改当前声明处 ----
        ver_changes = []
        pairs = [
            # 表格行：| `[task].version` | `1.0.6` |
            (rf"(\|\s*`\[task\]\.version`\s*\|\s*`){re.escape(cfg['old_ver'])}(`\s*\|)",
             rf"\g<1>{cfg['new_ver']}\g<2>"),
            # 打包日期行：| 打包日期 | 2026-10-06（质检整改版 1.0.3） |
            (rf"(打包日期[^\n]*?){re.escape(cfg['old_ver'])}", rf"\g<1>{cfg['new_ver']}"),
            # 文末：返修重交版 1.0.6 / 首交版 1.0.0…版本 1.0.1
            (rf"(版本\s*){re.escape(cfg['old_ver'])}(\s*，批次工作)", rf"\g<1>{cfg['new_ver']}\g<2>"),
        ]
        for pat, rep in pairs:
            text, k = re.subn(pat, rep, text)
            if k:
                ver_changes.append((pat[:46], k))
        print(f"  版本号 {cfg['old_ver']} -> {cfg['new_ver']}：{len(ver_changes)} 类命中 {ver_changes}")

        # ---- 残留自检 ----
        left_old_batch = text.count(cfg["old_batch"])
        left_old_ver = len(re.findall(rf"(?<![\d.]){re.escape(cfg['old_ver'])}(?![\d])", text))
        print(f"  残留：旧批次代号={left_old_batch}  旧版本号出现次数={left_old_ver}（后者含历史叙述，属正常）")
        print(f"  变更字节数：{len(text) - len(orig):+d}")

        if not a.dry_run and text != orig:
            f.write_text(text, encoding="utf-8")
            print("  已写回")


if __name__ == "__main__":
    main()
