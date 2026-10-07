"""目录树同步。"""

import os
import shutil


class SyncReport:
    """一次同步的动作记录。列表元素是相对 ``dst`` 的路径。"""

    def __init__(self):
        self.created = []
        self.updated = []
        self.deleted = []
        self.failed = []


def sync_tree(src, dst, dry_run=False):
    """把 ``src`` 目录树同步到 ``dst``，返回 :class:`SyncReport`。"""
    report = SyncReport()
    _sync_dir(src, dst, "", report, dry_run)
    _prune(src, dst, "", report, dry_run)
    return report


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
                    shutil.copyfile(src_path, dst_path)
                report.created.append(rel_path)
            else:
                with open(dst_path, "rb") as fh:
                    dst_bytes = fh.read()
                if src_bytes != dst_bytes:
                    if not dry_run:
                        shutil.copyfile(src_path, dst_path)
                    report.updated.append(rel_path)
                # 内容相同时视为一致，不做任何动作。
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
                if os.path.isdir(dst_path):
                    if not dry_run:
                        shutil.rmtree(dst_path)
                else:
                    if not dry_run:
                        os.remove(dst_path)
                report.deleted.append(rel_path)
            except OSError as exc:
                report.failed.append(rel_path)
                print("wstamp: %s (%s)" % (rel_path, exc))
        elif os.path.isdir(dst_path):
            _prune(src, dst, rel_path, report, dry_run)
