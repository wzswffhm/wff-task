#!/usr/bin/env bash
echo "=== 可用解压器探测 ==="
for t in 7z 7za 7zr p7zip unzip busybox bsdtar jar python3; do
  p=$(command -v "$t" 2>/dev/null) && echo "  $t -> $p" || echo "  $t -> (无)"
done
echo ""
echo "=== busybox 子命令 ==="
if command -v busybox >/dev/null; then busybox --list 2>/dev/null | grep -iE 'unzip|zip' || echo "  (busybox 无 unzip)"; fi
echo ""
echo "=== python 模块探测 ==="
python3 - <<'PY'
mods = ['py7zr','zipfile','libarchive','rarfile']
for m in mods:
    try:
        __import__(m); print(f'  {m} OK')
    except Exception as e:
        print(f'  {m} 缺 ({type(e).__name__})')
PY
echo ""
echo "=== apt 能否安装 unzip（离线缓存）==="
ls /var/cache/apt/archives/*.deb 2>/dev/null | head -3 || echo "  (无 deb 缓存)"
echo ""
echo "=== 是否有 sudo 免密 ==="
sudo -n true 2>/dev/null && echo "  sudo 免密可用" || echo "  sudo 需密码/不可用"
