"""目录树同步（反例：只比较内容，漏掉 mtime 回写分支）。"""

import os
import shutil

from .stamps import set_times
from . import attributes

_FILE_ATTRIBUTE_READONLY = 0x01


class SyncReport:
    def __init__(self):
        self.created = []
        self.updated = []
        self.restamped = []
        self.deleted = []
        self.failed = []


def sync_tree(src, dst, dry_run=False):
    report = SyncReport()
    _sync_dir(src, dst, "", report, dry_run)
    _prune(src, dst, "", report, dry_run)
    _restore_dir_mtimes(src, dst, "", dry_run)
    return report


def _clear_readonly(path):
    attrs = attributes.get_attributes(path)
    if attrs & _FILE_ATTRIBUTE_READONLY:
        attributes.set_attributes(path, attrs & ~_FILE_ATTRIBUTE_READONLY)


def _copy_entry(src_path, dst_path):
    src_st = os.stat(src_path)
    if os.path.exists(dst_path) and attributes.is_readonly(dst_path):
        _clear_readonly(dst_path)
    shutil.copyfile(src_path, dst_path)
    set_times(dst_path, src_st.st_atime_ns, src_st.st_mtime_ns,
              restore_readonly=True)
    attributes.set_attributes(dst_path, attributes.get_attributes(src_path))


def _sync_dir(src, dst, rel, report, dry_run):
    src_dir = os.path.join(src, rel) if rel else src
    dst_dir = os.path.join(dst, rel) if rel else dst
    if not dry_run:
        os.makedirs(dst_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        src_path = os.path.join(src_dir, name)
        rel_path = os.path.join(rel, name) if rel else name
        if os.path.isdir(src_path):
            _sync_dir(src, dst, rel_path, report, dry_run)
            continue
        dst_path = os.path.join(dst, rel_path)
        try:
            with open(src_path, "rb") as fh:
                src_bytes = fh.read()
            if not os.path.exists(dst_path):
                if not dry_run:
                    _copy_entry(src_path, dst_path)
                report.created.append(rel_path)
            else:
                with open(dst_path, "rb") as fh:
                    dst_bytes = fh.read()
                if src_bytes != dst_bytes:
                    if not dry_run:
                        _copy_entry(src_path, dst_path)
                    report.updated.append(rel_path)
                # 反例：内容相同一律视为一致，不回写 mtime。
        except OSError as exc:
            report.failed.append(rel_path)
            print("wstamp: %s (%s)" % (rel_path, exc))


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
                    if attributes.is_readonly(dst_path):
                        _clear_readonly(dst_path)
                    if os.path.isdir(dst_path) and not os.path.islink(dst_path):
                        shutil.rmtree(dst_path)
                    else:
                        os.remove(dst_path)
                report.deleted.append(rel_path)
            except OSError as exc:
                report.failed.append(rel_path)
                print("wstamp: %s (%s)" % (rel_path, exc))
        elif os.path.isdir(dst_path):
            _prune(src, dst, rel_path, report, dry_run)


def _restore_dir_mtimes(src, dst, rel, dry_run):
    src_dir = os.path.join(src, rel) if rel else src
    dst_dir = os.path.join(dst, rel) if rel else dst
    if not os.path.isdir(dst_dir):
        return
    for name in sorted(os.listdir(src_dir)):
        src_path = os.path.join(src_dir, name)
        if not os.path.isdir(src_path):
            continue
        rel_path = os.path.join(rel, name) if rel else name
        _restore_dir_mtimes(src, dst, rel_path, dry_run)
    if not dry_run:
        src_st = os.stat(src_dir)
        if os.path.isdir(dst_dir):
            os.utime(dst_dir, ns=(src_st.st_atime_ns, src_st.st_mtime_ns))
