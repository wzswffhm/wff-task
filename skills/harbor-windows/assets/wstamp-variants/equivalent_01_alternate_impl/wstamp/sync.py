"""目录树同步（等价实现：比较键用元组，目录时间收集后统一回写）。"""

import os
import stat

from .stamps import set_times
from . import attributes


class SyncReport:
    def __init__(self):
        self.created = []
        self.updated = []
        self.restamped = []
        self.deleted = []
        self.failed = []


def sync_tree(src, dst, dry_run=False):
    report = SyncReport()
    dir_pairs = []
    _walk(src, dst, "", report, dir_pairs, dry_run)
    _prune(src, dst, "", report, dry_run)
    # 收集顺序为浅→深，反向回写即深→浅。
    for src_dir, dst_dir in reversed(dir_pairs):
        if dry_run or not os.path.isdir(dst_dir):
            continue
        st = os.stat(src_dir)
        set_times(dst_dir, st.st_atime_ns, st.st_mtime_ns,
                  restore_readonly=True)
    return report


def _read_state(path):
    st = os.stat(path)
    with open(path, "rb") as fh:
        return fh.read(), st.st_mtime_ns


def _force_utime(path, atime_ns, mtime_ns):
    set_times(path, atime_ns, mtime_ns, restore_readonly=True)


def _walk(src, dst, rel, report, dir_pairs, dry_run):
    src_dir = os.path.join(src, rel) if rel else src
    dst_dir = os.path.join(dst, rel) if rel else dst
    if not dry_run:
        os.makedirs(dst_dir, exist_ok=True)
    dir_pairs.append((src_dir, dst_dir))
    for name in sorted(os.listdir(src_dir)):
        src_path = os.path.join(src_dir, name)
        rel_path = os.path.join(rel, name) if rel else name
        if os.path.isdir(src_path):
            _walk(src, dst, rel_path, report, dir_pairs, dry_run)
            continue
        dst_path = os.path.join(dst, rel_path)
        try:
            src_state = _read_state(src_path)
            if not os.path.exists(dst_path):
                if not dry_run:
                    _put(src_path, dst_path)
                report.created.append(rel_path)
                continue
            dst_state = _read_state(dst_path)
            if src_state[0] != dst_state[0]:
                if not dry_run:
                    _put(src_path, dst_path)
                report.updated.append(rel_path)
            elif src_state[1] != dst_state[1]:
                if not dry_run:
                    st = os.stat(dst_path)
                    set_times(dst_path, st.st_atime_ns, src_state[1],
                              restore_readonly=True)
                report.restamped.append(rel_path)
        except OSError as exc:
            report.failed.append(rel_path)
            print("wstamp: %s (%s)" % (rel_path, exc))


def _put(src_path, dst_path):
    """写入内容 + 时间戳 + 属性位（等价实现用 chmod 解只读）。"""
    st = os.stat(src_path)
    attrs = attributes.get_attributes(src_path)
    if os.path.exists(dst_path) and attributes.is_readonly(dst_path):
        os.chmod(dst_path, stat.S_IWRITE)
    with open(src_path, "rb") as fh:
        data = fh.read()
    with open(dst_path, "wb") as fh:
        fh.write(data)
    set_times(dst_path, st.st_atime_ns, st.st_mtime_ns, restore_readonly=True)
    attributes.set_attributes(dst_path, attrs)


def _prune(src, dst, rel, report, dry_run):
    dst_dir = os.path.join(dst, rel) if rel else dst
    if not os.path.isdir(dst_dir):
        return
    src_dir = os.path.join(src, rel) if rel else src
    for name in sorted(os.listdir(dst_dir)):
        dst_path = os.path.join(dst_dir, name)
        rel_path = os.path.join(rel, name) if rel else name
        src_path = os.path.join(src_dir, name)
        if not os.path.exists(src_path):
            try:
                if not dry_run:
                    _rm(dst_path)
                report.deleted.append(rel_path)
            except OSError as exc:
                report.failed.append(rel_path)
                print("wstamp: %s (%s)" % (rel_path, exc))
        elif os.path.isdir(dst_path):
            _prune(src, dst, rel_path, report, dry_run)


def _rm(path):
    if attributes.is_readonly(path):
        os.chmod(path, stat.S_IWRITE)
    if os.path.isdir(path) and not os.path.islink(path):
        import shutil
        shutil.rmtree(path)
    else:
        os.remove(path)
