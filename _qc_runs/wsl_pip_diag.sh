#!/bin/bash
GW=$(ip route | awk '/^default/{print $3; exit}')
export http_proxy="http://$GW:18080" https_proxy="http://$GW:18080"
echo "======== pip 全量 verbose（前 60 行关键）========"
timeout 180 python3 -m pip install -vvv "harbor==0.22.0" 2>&1 | head -60
echo
echo "======== pip config list ======"
python3 -m pip config list 2>&1 | sed 's/proxy.*/proxy=<已设>/'
echo
echo "======== python urllib 是否认代理环境 ======"
python3 - <<PYEOF
import os, urllib.request as u
print("  https_proxy env =", os.environ.get("https_proxy"))
try:
    r = u.urlopen("https://pypi.org/simple/harbor/", timeout=25)
    print("  urllib 走环境代理:", r.status, "len=", len(r.read(300)))
except Exception as e:
    print("  urllib FAIL:", type(e).__name__, e)
PYEOF
echo "DIAG-DONE"