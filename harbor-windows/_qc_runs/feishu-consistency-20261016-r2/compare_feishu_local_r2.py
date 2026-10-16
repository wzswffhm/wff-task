"""飞书交付附件（ZIP）与本地题包目录逐文件 SHA256 比对（只读）。

口径（README 铁律四第 6 条）：
- 只认交付附件字段「作业压缩包」；
- ZIP 内唯一根目录名必须等于「附件名去 .zip」；
- 解压后与本地 <harbor-windows>/<附件名去 .zip>/ 逐文件比对 SHA256。
"""
import hashlib
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ZIPDIR = os.path.join(HERE, "zip")
LOCALROOT = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows"

LOCAL_EXTRA_OK = {
    # 本地保留、但飞书附件里不需要镜像的目录（过程产物）
    "_qc_runs",
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def zip_entries(zip_path):
    """返回 {相对根目录的路径: sha256} 与根目录名（唯一则返回，否则 None）。"""
    out = {}
    roots = set()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            parts = name.split("/", 1)
            roots.add(parts[0])
            rel = parts[1] if len(parts) > 1 else parts[0]
            out[rel] = sha256_bytes(zf.read(info))
    root = roots.pop() if len(roots) == 1 else None
    return out, root, len(roots)


def local_files(root_dir):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in LOCAL_EXTRA_OK]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root_dir).replace("\\", "/")
            out[rel] = full
    return out


def main():
    report = []
    for zip_name in sorted(os.listdir(ZIPDIR)):
        if not zip_name.endswith(".zip"):
            continue
        zip_path = os.path.join(ZIPDIR, zip_name)
        expected_dir = zip_name[:-4]
        local_dir = os.path.join(LOCALROOT, expected_dir)
        zhash = sha256_file(zip_path)

        zfiles, zroot, nroots = zip_entries(zip_path)
        entry = {
            "attachment": zip_name,
            "zip_sha256": zhash,
            "zip_size": os.path.getsize(zip_path),
            "zip_root_dir": zroot,
            "zip_root_count": nroots,
            "zip_root_matches_attachment": (zroot == expected_dir),
            "zip_file_count": len(zfiles),
            "local_dir": local_dir,
            "local_exists": os.path.isdir(local_dir),
        }
        if not entry["local_exists"]:
            entry["verdict"] = "本地无对应目录"
            report.append(entry)
            continue

        lfiles = local_files(local_dir)
        entry["local_file_count"] = len(lfiles)

        only_zip = sorted(set(zfiles) - set(lfiles))
        only_local = sorted(set(lfiles) - set(zfiles))
        changed = []
        for rel in sorted(set(zfiles) & set(lfiles)):
            if sha256_file(lfiles[rel]) != zfiles[rel]:
                changed.append(rel)

        entry["only_in_zip"] = only_zip[:50]
        entry["only_in_local"] = only_local[:50]
        entry["content_changed"] = changed[:50]
        entry["only_in_zip_count"] = len(only_zip)
        entry["only_in_local_count"] = len(only_local)
        entry["content_changed_count"] = len(changed)
        ok = (not only_zip) and (not only_local) and (not changed) and entry["zip_root_matches_attachment"]
        entry["verdict"] = "一致" if ok else "不一致"
        report.append(entry)

    with open(os.path.join(HERE, "feishu-vs-local-r2.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    lines = ["# 飞书交付附件 vs 本地题包：逐文件 SHA256 比对（2026-10-16 复核 r2）", "",
             "| 附件 | ZIP 文件数 | 本地文件数 | 根目录名匹配 | ZIP 独有 | 本地独有 | 同名异内容 | 结论 |",
             "|---|---|---|---|---|---|---|---|"]
    for e in report:
        if not e["local_exists"]:
            lines.append("| `%s` | %d | - | %s | - | - | - | %s |" %
                         (e["attachment"], e["zip_file_count"], e["zip_root_matches_attachment"], e["verdict"]))
            continue
        lines.append("| `%s` | %d | %d | %s | %d | %d | %d | **%s** |" % (
            e["attachment"], e["zip_file_count"], e["local_file_count"],
            e["zip_root_matches_attachment"], e["only_in_zip_count"],
            e["only_in_local_count"], e["content_changed_count"], e["verdict"]))
    lines += ["", "ZIP SHA256："]
    for e in report:
        lines.append("- `%s` → `%s`" % (e["attachment"], e["zip_sha256"]))
    lines += ["", "差异明细："]
    for e in report:
        detail = []
        if e.get("only_in_zip_count"):
            detail.append("ZIP 独有：%s" % ", ".join(e["only_in_zip"]))
        if e.get("only_in_local_count"):
            detail.append("本地独有：%s" % ", ".join(e["only_in_local"]))
        if e.get("content_changed_count"):
            detail.append("同名异内容：%s" % ", ".join(e["content_changed"]))
        if detail:
            lines.append("- **%s**：%s" % (e["attachment"], "；".join(detail)))
    lines.append("")
    with open(os.path.join(HERE, "feishu-vs-local-r2.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print("\n".join(lines))


if __name__ == "__main__":
    main()
