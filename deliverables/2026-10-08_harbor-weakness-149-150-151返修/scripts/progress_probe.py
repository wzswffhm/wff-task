"""判官重跑精细进度探针：显示每个 (题目, 执行体) 当前判到第几条判据。

原理：rewardkit 以 individual 模式逐条起 claude 会话，prompt 里带
`- 'R02': <description>`，因此可从容器内 `claude -p` 进程的 argv 提取当前判据 ID，
再按 tests/rubrics.toml 的 criterion 出现顺序换算成「第 N / 总数 条」。
"""
import json
import pathlib
import re
import subprocess

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASKS = {
    "FIN3-WKN-149": "work-金融-资产管理-20261008",
    "FIN3-WKN-150": "work-金融-私募股权投资-20261008",
    "FIN3-WKN-151": "work-金融-商业银行-20261008",
}
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]
ID_RE = re.compile(r"-\s*'([A-Z]\d{2})'\s*:")


def criterion_order(task):
    toml = (H / task / "tests" / "rubrics.toml").read_text(encoding="utf-8")
    return re.findall(r'\[\[criterion\]\]\s*\nid\s*=\s*"([^"]+)"', toml)


def docker_ps_names():
    p = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True)
    return set((p.stdout or "").split())


def probe(name, want_id, order):
    """返回 (状态, 当前判据, 序号, judge会话已跑秒数)。"""
    if name not in RUNNING:
        ver = None
        return None
    r = subprocess.run(["docker", "exec", name, "bash", "-lc", "ps -eo etime,args"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    cur, secs = None, None
    for line in (r.stdout or "").splitlines():
        if "claude -p" in line:
            m = ID_RE.search(line)
            if m:
                cur = m.group(1)
            et = line.strip().split()[0]
            try:
                if "-" in et:            # D-HH:MM:SS
                    d, hms = et.split("-")
                    h, m, s2 = hms.split(":")
                    secs = int(d) * 86400 + int(h) * 3600 + int(m) * 60 + int(s2)
                else:                    # MM:SS 或 HH:MM:SS
                    parts = [int(x) for x in et.split(":")]
                    secs = 0
                    for x in parts:
                        secs = secs * 60 + x
            except ValueError:
                secs = None
    if cur is None:
        return ("判分中", "（会话切换间隙）", None, secs)
    idx = order.index(cur) + 1 if cur in order else None
    return ("判分中", cur, idx, secs)


def read_state(task, ex):
    ver = H / task / "_rejudge" / ex / "verifier"
    rj, rem = ver / "reward.json", ver / "reward_exit_message.json"
    if rj.is_file() and not rem.is_file():
        try:
            d = json.loads(rj.read_text(encoding="utf-8"))
            if float(d.get("criteria_counted") or 0) >= 1:
                return "done", d
        except Exception:  # noqa: BLE001
            pass
    if rem.is_file():
        # 注意：reward_exit_message.json 是 test.sh 开头的 fail-closed 占位，
        # 判分运行期间一直存在，只有 finalize.py 成功收尾才删除。
        # 因此不能据此判为失败——失败与否须结合「容器是否仍在运行」判断。
        pass
    return "pending", None


RUNNING = docker_ps_names()
for task, batch in TASKS.items():
    order = criterion_order(task)
    print("=" * 88)
    print(f"{task}   判据总数 {len(order)}   判据顺序: {' '.join(order)}")
    for ex in EXECUTORS:
        name = f"rejudge-{task}-{ex}"
        st, d = read_state(task, ex)
        if st == "done":
            print(f"  {ex:20s} ✅ 已完成  reward={d.get('reward')}  counted={d.get('criteria_counted')}")
            continue
        if st == "failed":
            print(f"  {ex:20s} ❌ 未成功收尾（待重试）")
            continue
        if name not in RUNNING:
            ver = H / task / "_rejudge" / ex / "verifier"
            started = (ver / "reward.json").is_file()
            if started:
                ts = (ver / "reward.json").stat().st_mtime
                import datetime as _dt
                when = _dt.datetime.fromtimestamp(ts).strftime("%H:%M")
                print(f"  {ex:20s} ⏸  排队中（占位残留于 {when}，driver 将按序启动）")
            else:
                print(f"  {ex:20s} ⏸  排队中（尚未启动）")
            continue
        r = probe(name, None, order)
        _, cur, idx, secs = r
        frac = f"{idx}/{len(order)}" if idx else "?"
        secs_s = f"{secs}s" if secs is not None else "?"
        print(f"  {ex:20s} 🔄 判分中  当前判据={cur}  进度≈{frac}  本条已跑={secs_s}")
