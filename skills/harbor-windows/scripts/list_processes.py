#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列出进程及其父进程与命令行（不依赖 wmic / PowerShell）。

背景：新版 Windows 已移除 `wmic.exe`，而部分环境下 PowerShell 通道不可用，
排查「Agent 沙箱里的命令挂死」时拿不到命令行就无法定位。本脚本用
CreateToolhelp32Snapshot 取 PID/PPID、用 NtQueryInformationProcess
（ProcessCommandLineInformation=60）取命令行，纯 ctypes，无第三方依赖。

用法：
    python list_processes.py                      # 全部进程
    python list_processes.py --filter python      # 名字含 python
    python list_processes.py --filter python --tree
    python list_processes.py --kill-tree <PID>    # 杀掉以 PID 为根的整棵树
"""
from __future__ import annotations

import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

IS_WIN = os.name == "nt"

if IS_WIN:
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

    TH32CS_SNAPPROCESS = 0x00000002
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", ctypes.c_void_p),
        ]


def _iter_basic():
    """返回 [(pid, ppid, exe_name)]，按 pid 升序。"""
    if not IS_WIN:
        raise SystemExit("仅支持 Windows")
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE or snap is None:
        raise SystemExit("CreateToolhelp32Snapshot 失败：%d" % ctypes.get_last_error())
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        out = []
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            out.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID),
                        entry.szExeFile))
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
        out.sort(key=lambda t: t[0])
        return out
    finally:
        _k32.CloseHandle(snap)


def _cmdline(pid: int) -> str:
    """命令行；取不到时返回空串（通常是权限不足或进程已退出）。"""
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_string_buffer(8192)
        ret = _ntdll.NtQueryInformationProcess(
            wintypes.HANDLE(h), 60, ctypes.byref(buf),
            ctypes.sizeof(buf), None)
        if ret != 0:
            return ""
        us = ctypes.cast(buf, ctypes.POINTER(UNICODE_STRING)).contents
        if not us.Buffer or not us.Length:
            return ""
        return ctypes.wstring_at(us.Buffer, us.Length // 2)
    except Exception:
        return ""
    finally:
        _k32.CloseHandle(h)


def collect():
    rows = []
    for pid, ppid, exe in _iter_basic():
        rows.append({"pid": pid, "ppid": ppid, "exe": exe,
                     "cmd": _cmdline(pid), "alive": True})
    return rows


def kill_tree(pid: int) -> int:
    """用 taskkill /F /T 杀整棵树；返回 taskkill 的退出码。"""
    import subprocess
    r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=60)
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", help="进程名/命令行包含该子串（不区分大小写）")
    ap.add_argument("--tree", action="store_true", help="按父子关系缩进展示")
    ap.add_argument("--kill-tree", type=int, metavar="PID", help="杀掉以该 PID 为根的整棵树")
    a = ap.parse_args()

    if a.kill_tree:
        rc = kill_tree(a.kill_tree)
        print("taskkill rc=%d pid=%d" % (rc, a.kill_tree))
        return 0 if rc == 0 else 1

    rows = collect()
    if a.filter:
        f = a.filter.lower()
        rows = [r for r in rows if f in r["exe"].lower() or f in r["cmd"].lower()]
    by_pid = {r["pid"]: r for r in rows}

    if a.tree:
        children = {}
        for r in rows:
            children.setdefault(r["ppid"], []).append(r["pid"])
        roots = [r["pid"] for r in rows if r["ppid"] not in by_pid]

        def walk(pid, depth):
            r = by_pid[pid]
            cmd = r["cmd"] or "(无命令行权限)"
            print("%s%-6d %s" % ("  " * depth, pid, cmd[:170]))
            for c in sorted(children.get(pid, [])):
                walk(c, depth + 1)

        for rt in sorted(roots):
            walk(rt, 0)
    else:
        for r in rows:
            cmd = r["cmd"] or "(无命令行权限)"
            print("%-7d %-7d %-22s %s" % (r["pid"], r["ppid"], r["exe"][:22], cmd[:150]))
    print("--- 共 %d 个进程（筛选后） ---" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
