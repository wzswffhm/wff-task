# -*- coding: utf-8 -*-
"""D3: 向 run_tests.ps1 追加 24 条新判据，并联动更新 required_testcases.json 与 rubric.json。

设计约束（已核对）：
  * 新检查只用 run_tests.ps1 已有的上下文变量：$never / $follow / $scanRoot /
    $reportError，以及 Get-WReparseTestRecord / Test-WReparseHasError。
  * id 不带 f2p-/p2p- 前缀（由 aggregate_results.ps1 拼接），required 中带前缀。
  * 断言全部落在 Gold 实测能力内（序数排序/深度/路径/Follow/确定性），
    不含 access_denied（管理员会绕过 ACL）、UNC（容器不可移植）、大小写决胜（NTFS 不允许同名）。
  * 只做加法：现有 36 条与它们的顺序一概不动。
"""
import json
import pathlib
import re
import sys

TASK = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wreparse-217")
RUN = TASK / "tests" / "run_tests.ps1"
REQ = TASK / "tests" / "required_testcases.json"
RUB = TASK / "tests" / "rubric.json"

# 24 条：(裸id, group, PowerShell 断言体)
NEW = [
    # ---- A. 区域设置无关（3）----
    ("culture-en-us-ordinal-order", "F2P", r'''
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "en-US: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }'''),
    ("culture-de-de-ordinal-order", "F2P", r'''
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('de-DE')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "de-DE: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }'''),
    ("culture-ja-jp-ordinal-order", "F2P", r'''
    $prevT = [System.Threading.Thread]::CurrentThread.CurrentCulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('ja-JP')
        $r = Get-WReparseReport -Root $scanRoot
        $p = @($r.Records | ForEach-Object { [string]$_.RelativePath })
        $z = [Array]::IndexOf($p, "$([char]0x5A).txt"); $a = [Array]::IndexOf($p, "$([char]0xC4).txt"); $o = [Array]::IndexOf($p, "$([char]0xF6).txt")
        if ($z -lt 0 -or $a -lt 0 -or $o -lt 0) { return 'Z/umlaut records missing' }
        if (-not ($z -lt $a -and $z -lt $o)) { return "ja-JP: ordinal order violated (Z=$z A=$a o=$o)" }
        return $true
    } finally { [System.Threading.Thread]::CurrentThread.CurrentCulture = $prevT }'''),

    # ---- B. 规模与深度（6）----
    ("deep-tree-emits-all-levels", "F2P", r'''
    $cursor = $scanRoot
    for ($i = 1; $i -le 8; $i++) {
        $cursor = Join-Path $cursor ('level' + $i)
        $rec = Get-WReparseTestRecord -Report $never -RelativePath ($cursor.Substring($scanRoot.Length + 1))
        if ($null -eq $rec) { return "level$i is missing from the default scan" }
        if ([int]$rec.Depth -ne $i) { return "level$i Depth=$($rec.Depth), expected $i" }
        if ($rec.Kind -ne 'Directory') { return "level$i Kind=$($rec.Kind), expected Directory" }
    }
    $tip = Get-WReparseTestRecord -Report $never -RelativePath 'level1\level2\level3\level4\level5\level6\level7\level8\deepest.txt'
    if ($null -eq $tip) { return 'deepest.txt missing' }
    if ([int]$tip.Depth -ne 9) { return "deepest.txt Depth=$($tip.Depth), expected 9" }
    return $true'''),
    ("maxdepth-1-count-is-exact", "F2P", r'''
    $direct = @(Get-ChildItem -LiteralPath $scanRoot -Force -ErrorAction SilentlyContinue)
    $r1 = Get-WReparseReport -Root $scanRoot -MaxDepth 1
    $expected = $direct.Count
    $actual = @($r1.Records).Count
    if ($actual -ne $expected) { return "MaxDepth 1 emitted $actual records, fixture has $expected direct children" }
    return $true'''),
    ("default-maxdepth-covers-deep-tree", "F2P", r'''
    if ([int]$never.Stats.Directories -lt 9) { return "default scan found only $($never.Stats.Directories) directories; the 8-level chain was truncated" }
    $tip = Get-WReparseTestRecord -Report $never -RelativePath 'level1\level2\level3\level4\level5\level6\level7\level8\deepest.txt'
    if ($null -eq $tip) { return 'deepest.txt not emitted under the default -MaxDepth' }
    return $true'''),
    ("stats-sum-equals-record-count", "F2P", r'''
    $sum = [int]$never.Stats.Directories + [int]$never.Stats.Files + [int]$never.Stats.ReparsePoints
    if ($sum -ne @($never.Records).Count) { return "Stats sum $sum != record count $(@($never.Records).Count)" }
    return $true'''),
    ("stats-match-kind-counts", "F2P", r'''
    $d = @($never.Records | Where-Object { $_.Kind -eq 'Directory' }).Count
    $f = @($never.Records | Where-Object { $_.Kind -eq 'File' }).Count
    $r = @($never.Records | Where-Object { $_.Kind -eq 'ReparsePoint' }).Count
    if ([int]$never.Stats.Directories -ne $d) { return "Stats.Directories=$($never.Stats.Directories) but Kind=Directory count=$d" }
    if ([int]$never.Stats.Files -ne $f) { return "Stats.Files=$($never.Stats.Files) but Kind=File count=$f" }
    if ([int]$never.Stats.ReparsePoints -ne $r) { return "Stats.ReparsePoints=$($never.Stats.ReparsePoints) but Kind=ReparsePoint count=$r" }
    return $true'''),
    ("skipped-equals-unfollowed-reparse-count", "F2P", r'''
    $rp = @($never.Records | Where-Object { $_.Kind -eq 'ReparsePoint' }).Count
    if ([int]$never.Stats.Skipped -ne $rp) { return "Skipped=$($never.Stats.Skipped) but only $rp reparse records exist" }
    if ([int]$follow.Stats.Skipped -ne 0) { return "with -Follow Skipped=$($follow.Stats.Skipped), expected 0" }
    return $true'''),

    # ---- C. 路径语义（4）----
    ("canonical-folds-dot-dot", "F2P", r'''
    $in = Join-Path (Join-Path $scanRoot 'docs') '..\data'
    $expect = Join-Path $scanRoot 'data'
    $actual = [string](Get-WReparseCanonicalPath -Path $in)
    if ($actual -cne $expect) { return "Get-WReparseCanonicalPath('$in')='$actual', expected '$expect'" }
    return $true'''),
    ("within-root-rejects-prefix-sibling", "F2P", r'''
    $sibling = Join-Path (Split-Path -Parent $scanRoot) 'scanroot-extra'
    if (-not (Test-Path -LiteralPath $sibling)) { return "fixture sibling $sibling missing" }
    if (Test-WReparseWithinRoot -Path $sibling -Root $scanRoot) { return "$sibling reported inside $scanRoot; they only share a name prefix" }
    if (-not (Test-WReparseWithinRoot -Path (Join-Path $scanRoot 'docs') -Root $scanRoot)) { return 'real child reported outside the root' }
    return $true'''),
    ("resolve-absolute-target-normalised", "F2P", r'''
    $expected = Join-Path $scanRoot 'docs'
    $abs = [string](Resolve-WReparseLinkTarget -LinkFullPath (Join-Path $scanRoot 'link-in') -RawTarget $expected)
    if ($abs -cne $expected) { return "absolute target resolved to '$abs', expected '$expected'" }
    $nullOut = Resolve-WReparseLinkTarget -LinkFullPath (Join-Path $scanRoot 'link-rel') -RawTarget ''
    if ($null -ne $nullOut) { return "empty RawTarget returned '$nullOut', expected `$null" }
    return $true'''),
    ("report-root-is-canonical", "F2P", r'''
    $expected = [string](Get-WReparseCanonicalPath -Path $scanRoot)
    if ([string]$never.Root -cne $expected) { return "Root='$($never.Root)', canonical is '$expected'" }
    if ([string]$never.Root -ne [string]$follow.Root) { return 'Root differs between default and -Follow scans' }
    return $true'''),

    # ---- D. Follow 语义（5）----
    ("follow-prefix-uses-link-name", "F2P", r'''
    $child = Get-WReparseTestRecord -Report $follow -RelativePath 'link-in\readme.txt'
    if ($null -eq $child) { return 'link-in\readme.txt missing under -Follow' }
    if ([string]$child.Kind -ne 'File') { return "link-in\readme.txt Kind=$($child.Kind)" }
    if ([int]$child.Depth -ne 2) { return "link-in\readme.txt Depth=$($child.Depth), expected 2" }
    return $true'''),
    ("follow-never-emits-target-real-name", "F2P", r'''
    foreach ($p in @('docs\readme.txt', 'outside\secret.txt')) {
        $rec = Get-WReparseTestRecord -Report $follow -RelativePath $p
        if ($null -ne $rec) { return "$p was emitted under -Follow; entries reached through a link must keep the link path prefix" }
    }
    return $true'''),
    ("follow-file-link-has-no-children", "F2P", r'''
    $linkRec = Get-WReparseTestRecord -Report $follow -RelativePath 'link-file'
    if ($null -eq $linkRec) { return 'link-file record missing under -Follow' }
    $kids = @($follow.Records | Where-Object { $_.RelativePath -like 'link-file\*' })
    if ($kids.Count -ne 0) { return "link-file has $($kids.Count) child records; its target is a file" }
    return $true'''),
    ("follow-enters-twin-without-cycle", "F2P", r'''
    $twin = Get-WReparseTestRecord -Report $follow -RelativePath 'link-twin'
    if ($null -eq $twin) { return 'link-twin missing under -Follow' }
    $kids = @($follow.Records | Where-Object { $_.RelativePath -like 'link-twin\*' })
    if ($kids.Count -eq 0) { return 'link-twin was not entered; two siblings pointing at the same target is not a cycle' }
    $cyc = @($follow.Errors | Where-Object { [string]$_.Code -eq 'cycle' })
    foreach ($c in $cyc) { if ([string]$c.RelativePath -eq 'link-twin') { return 'link-twin was reported as a cycle' } }
    return $true'''),
    ("follow-vs-default-record-relation", "F2P", r'''
    $nDef = @($never.Records).Count
    $nFol = @($follow.Records).Count
    if ($nFol -le $nDef) { return "default scan has $nDef records, -Follow has $nFol; entering links must add records" }
    return $true'''),

    # ---- E. 确定性与字段（6）----
    ("report-json-has-no-volatile-field", "F2P", r'''
    $json = [string](ConvertTo-WReparseJson -Report $never)
    if ([string]::IsNullOrWhiteSpace($json)) { return 'serialised report is empty' }
    foreach ($bad in @('GeneratedAt', 'Timestamp', 'timestamp', 'ProcessId', 'PID', 'Random', 'Guid', 'guid')) {
        if ($json.Contains($bad)) { return "serialised report contains volatile field marker '$bad'" }
    }
    return $true'''),
    ("errors-serialise-as-empty-array", "P2P", r'''
    if (@($never.Errors).Count -ne 0) { return "default scan produced $(@($never.Errors).Count) errors on a healthy fixture" }
    $json = [string](ConvertTo-WReparseJson -Report $never)
    if ($json -notmatch '"Errors"\s*:\s*\[\s*\]') { return 'Errors did not serialise as an empty array' }
    return $true'''),
    ("schema-version-is-constant", "P2P", r'''
    if ([string](Get-WReparseSchemaVersion) -ne [string]$never.SchemaVersion) { return "Get-WReparseSchemaVersion differs from report SchemaVersion" }
    if ([string]$never.SchemaVersion -ne 'wreparse/1.0') { return "SchemaVersion='$($never.SchemaVersion)'" }
    return $true'''),
    ("record-fields-match-contract-exactly", "F2P", r'''
    $want = @('RelativePath','Kind','ReparseKind','Target','ResolvedTarget','InScope','Depth','Size')
    foreach ($rec in @($never.Records | Select-Object -First 12)) {
        $got = @($rec.PSObject.Properties.Name)
        if (($got -join ',') -ne ($want -join ',')) { return "record '$($rec.RelativePath)' fields are [$($got -join ',')]" }
    }
    return $true'''),
    ("size-zero-for-non-file-records", "F2P", r'''
    foreach ($rec in @($never.Records | Where-Object { $_.Kind -ne 'File' })) {
        if ([int64]$rec.Size -ne 0) { return "'$($rec.RelativePath)' Kind=$($rec.Kind) Size=$($rec.Size), expected 0" }
    }
    return $true'''),
    ("non-reparse-null-fields-stay-null", "F2P", r'''
    foreach ($rec in @($never.Records | Where-Object { $_.Kind -ne 'ReparsePoint' })) {
        if ($null -ne $rec.ReparseKind) { return "'$($rec.RelativePath)' ReparseKind=$($rec.ReparseKind), expected null" }
        if ($null -ne $rec.Target) { return "'$($rec.RelativePath)' Target=$($rec.Target), expected null" }
        if ($null -ne $rec.ResolvedTarget) { return "'$($rec.RelativePath)' ResolvedTarget=$($rec.ResolvedTarget), expected null" }
    }
    return $true'''),
]

GROUP_PREFIX = {"F2P": "f2p-", "P2P": "p2p-"}
RUBRIC_HINTS = {
    "traversal-safety": ["follow-", "no-follow", "deep-tree", "maxdepth", "default-maxdepth", "stats-", "skipped-"],
    "path-semantics": ["canonical-", "within-root", "resolve-", "report-root"],
    "deterministic-output": ["culture-", "report-json", "errors-serialise", "schema-version", "record-fields", "size-zero", "non-reparse"],
}


def main() -> int:
    # ---- 1) run_tests.ps1：插入 24 条 + 改 task_version -------------------
    text = RUN.read_text(encoding="utf-8")
    if "culture-en-us-ordinal-order" in text:
        print("[skip] run_tests.ps1 已含新判据")
    else:
        anchor = "# ---- persist ---"
        if anchor not in text:
            print("[FAIL] 找不到 persist 锚点")
            return 1
        blocks = []
        for bare, _group, body in NEW:
            body = body.strip("\n")
            blocks.append(f"Add-WReparseCheck '{bare}' {{\n{body}\n}}\n")
        insert = ("\n# ---- deepened contract checks (24, added by v1.3.0) ---"
                  "-----------------------------------------------------------\n" + "\n".join(blocks) + "\n")
        text = text.replace(anchor, insert + anchor, 1)
        text = text.replace("task_version = '1.2.0'", "task_version = '1.3.0'")
        RUN.write_text(text, encoding="utf-8", newline="\n")
        print(f"[OK] run_tests.ps1 追加 24 条检查，task_version -> 1.3.0（现 {len(text.splitlines())} 行）")

    # ---- 2) required_testcases.json --------------------------------------
    req = json.loads(REQ.read_text(encoding="utf-8"))
    have = {r["id"] for r in req}
    added = 0
    for bare, group, _body in NEW:
        rid = GROUP_PREFIX[group] + bare
        if rid not in have:
            req.append({"id": rid, "group": group})
            have.add(rid)
            added += 1
    REQ.write_text(json.dumps(req, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    f2p = sum(1 for r in req if r["group"] == "F2P")
    p2p = sum(1 for r in req if r["group"] == "P2P")
    print(f"[OK] required_testcases.json: +{added} -> {len(req)} 条（F2P {f2p} / P2P {p2p}）")

    # ---- 3) rubric.json：把新 id 分配进现有 9 项的 test_ids ---------------
    rub = json.loads(RUB.read_text(encoding="utf-8"))
    if isinstance(rub, dict):
        items = rub.get("items") or []
        if rub.get("task_version") == "1.2.0":
            rub["task_version"] = "1.3.0"
    else:
        items = rub
    assigned, unassigned = set(), []
    for bare, group, _body in NEW:
        rid = GROUP_PREFIX[group] + bare
        done = False
        for item in items:
            rtype = str(item.get("rubric_id", "")).lower()
            if not any(h in rtype for h in RUBRIC_HINTS):
                continue
            tids = item.setdefault("test_ids", [])
            if rid not in tids:
                tids.append(rid)
            done = True
            assigned.add(rid)
            break
        if not done:
            unassigned.append(rid)
    if unassigned:
        # 兜底：塞进权重最大的项，保证每条 required 都被 rubric 覆盖
        biggest = max(items, key=lambda it: float(it.get("weight") or 0))
        print(f"  [WARN] 无精确匹配，兜底进 {biggest.get('rubric_id')}: {unassigned}")
        for rid in unassigned:
            biggest.setdefault("test_ids", []).append(rid)
        assigned.update(unassigned)
    total_weight = sum(float(it.get("weight") or 0) for it in items)
    covered = set()
    for it in items:
        covered.update(it.get("test_ids") or [])
    missing = have - covered
    RUB.write_text(json.dumps(rub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[OK] rubric.json: {len(items)} 项，权重合计={round(total_weight, 6)}，"
          f"已覆盖 {len(covered & have)}/{len(have)} 条 required，未覆盖={sorted(missing)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
