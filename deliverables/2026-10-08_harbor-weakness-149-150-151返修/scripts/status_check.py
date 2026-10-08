"""直接读盘核对 149/150/151 的 12 场判分状态（不依赖 docker）。"""
import json
import pathlib

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASKS = ["FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151"]
EXECUTORS = ["oracle", "qwen3.8-max-0902", "claude-opus-4-8", "gpt-5.6-sol"]

done = pending = 0
for t in TASKS:
    for ex in EXECUTORS:
        ver = H / t / "_rejudge" / ex / "verifier"
        rj, rem = ver / "reward.json", ver / "reward_exit_message.json"
        if rj.is_file() and not rem.is_file():
            try:
                d = json.loads(rj.read_text(encoding="utf-8"))
                cc = float(d.get("criteria_counted") or 0)
                if cc >= 1:
                    done += 1
                    print(f"完成   {t} {ex:20s} reward={d.get('reward')} "
                          f"counted={int(cc)} verr={d.get('verifier_error')}")
                    continue
            except Exception as e:  # noqa: BLE001
                print(f"异常   {t} {ex:20s} reward.json 解析失败: {e}")
                continue
        pending += 1
        reason = ""
        if rem.is_file():
            try:
                e = json.loads(rem.read_text(encoding="utf-8"))
                reason = f"exit={e.get('exit_code')} {str(e.get('exit_reason'))[:80]}"
            except Exception:  # noqa: BLE001
                reason = "(错误文件不可解析)"
        else:
            reason = "(无错误文件，未起跑或进行中)"
        print(f"待跑   {t} {ex:20s} {reason}")

print(f"\n合计：完成 {done}/12  待跑 {pending}/12")

# 顺带列出实体目录情况
for t in TASKS:
    rd = H / t / "_rejudge"
    if rd.is_dir():
        subs = sorted(p.name for p in rd.iterdir() if p.is_dir())
        print(f"{t} _rejudge 子目录: {subs}")
