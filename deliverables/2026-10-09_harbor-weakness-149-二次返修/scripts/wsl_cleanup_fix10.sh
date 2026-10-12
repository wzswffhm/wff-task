#!/usr/bin/env bash
echo "=== 149 相关容器 ==="
docker ps --format '{{.Names}} {{.Status}}' | grep -i 149 || echo "(无)"
echo "=== harbor 进程（149） ==="
ps -eo etime,cmd | grep '[h]arbor trial start' | grep -i 'fix10\|fix9' || echo "(无)"
echo "=== fix10 输出尾 ==="
tail -5 /home/wff/harbor-runs/FIN3-WKN-149-fix10/oracle.out 2>/dev/null
echo "=== 磁盘占用（149 运行目录）==="
du -sh /home/wff/harbor-runs/FIN3-WKN-149-fix10 2>/dev/null
du -sh /home/wff/harbor-runs/FIN3-WKN-149-fix8 2>/dev/null
du -sh /home/wff/harbor-runs/FIN3-WKN-149-fix9 2>/dev/null
