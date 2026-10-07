"""Regression check for the parameterised Outside-Harbor runner.

Proves two things without touching Docker:
  1. resolve_task_profile() derives the right module / docs / samples / language
     for both wfflab__wreparse-217 (the original hard-coded task) and
     wfflab__wfmt-215 (the second task that used to be unwinnable).
  2. The agent view / mirror / fingerprint plumbing now follows the profile, so
     a candidate edit to the real module actually lands in the graded copy.
"""
import importlib.util
import pathlib
import shutil
import tempfile

RUNNER = pathlib.Path(
    r"C:\Users\Administrator\Desktop\wff-task\deliverables"
    r"\2026-10-04_outside-harbor-win\runner\runner.py"
)
TASKS = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")

spec = importlib.util.spec_from_file_location("oh_runner", RUNNER)
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

WRITE_CASES = {
    "wfflab__wreparse-217": [
        r"C:\task\environment\workspace\WReparse\Walker.ps1",
        r"C:\task\environment\workspace\docs\REPARSE-CONTRACT.md",
        r"C:\task\instruction.md",
    ],
    "wfflab__wfmt-215": [
        r"C:\task\environment\workspace\wfmt\varint.py",
        r"C:\task\environment\workspace\wfmt\codec.py",
        r"C:\task\environment\workspace\docs\FORMAT.md",
        r"C:\task\environment\workspace\assets\sample.wfmt",
        r"C:\task\instruction.md",
    ],
}

for name in ("wfflab__wreparse-217", "wfflab__wfmt-215"):
    task_dir = TASKS / name
    prof = m.resolve_task_profile(task_dir)
    m.TASK_PROFILE.clear()
    m.TASK_PROFILE.update(prof)

    print("=" * 78)
    print("TASK:", name)
    for key in ("task_id", "language", "module_rel", "container_writable",
                "contract_docs", "samples_dir"):
        print(f"  {key:19} = {prof[key]}")

    mount = pathlib.Path(tempfile.gettempdir()) / "_oh_mount_probe"
    print("  --- write whitelist ---")
    for case in WRITE_CASES[name]:
        try:
            host = m.translate_path(case, mount)
            verdict = "ALLOW" if m.is_writable(host, mount) else "deny "
        except Exception as exc:  # noqa: BLE001
            verdict = f"ERR({type(exc).__name__})"
        print(f"    {verdict:5} {case}")

    print("  --- first user turn ---")
    print("   ", m.build_task_prompt())

    print("  --- system prompt ---")
    for line in m.build_system_prompt().splitlines():
        print("   |", line)

    print("  --- tools ---")
    for tool in m.build_tools():
        print(f"    - {tool['name']:10} {tool['description'][:96]}")

# --------------------------------------------------------------------------- #
# end-to-end plumbing: view -> candidate edit -> mirror -> fingerprint
# --------------------------------------------------------------------------- #
print()
print("=" * 78)
print("END-TO-END PLUMBING (wfflab__wfmt-215)")

src = TASKS / "wfflab__wfmt-215"
work = pathlib.Path(tempfile.mkdtemp(prefix="oh_probe_"))
try:
    case = work / "case"
    view = work / "view"
    shutil.copytree(src, case, ignore=shutil.ignore_patterns(
        "__pycache__", ".pytest_cache", "extras", "results"))

    m.TASK_PROFILE.clear()
    m.TASK_PROFILE.update(m.resolve_task_profile(case))

    m.build_agent_view(case, view)
    view_module = view / m.TASK_PROFILE["module_rel"]
    print("  view module exists      :", view_module.is_dir(),
          sorted(p.name for p in view_module.iterdir())[:4], "...")

    # the candidate view must NOT leak tests/ or solution/
    leaked = [p.relative_to(view).as_posix() for p in view.rglob("*")
              if p.is_file() and (p.parts[-2:] == ("tests", "test_wfmt_basic.py")
                                  or "hidden" in p.parts or "oracle.patch" in p.name
                                  or "solve.ps1" in p.name)]
    print("  leaked verifier files   :", leaked or "none")

    fingerprint_before = m.workspace_fingerprint(view)
    target_file = view_module / "varint.py"
    target_file.write_text(target_file.read_text(encoding="utf-8") + "\n# probe edit\n",
                           encoding="utf-8")
    fingerprint_after = m.workspace_fingerprint(view)
    print("  fingerprint changed     :", fingerprint_before != fingerprint_after)

    m.mirror_workspace(view, case)
    mirrored = case / m.TASK_PROFILE["module_rel"] / "varint.py"
    print("  edit mirrored to case   :", "# probe edit" in mirrored.read_text(encoding="utf-8"))

    # sample bytes must survive the copy untouched
    a = (src / "environment" / "workspace" / "assets" / "sample.wfmt").read_bytes()
    b = (view / "environment" / "workspace" / "assets" / "sample.wfmt").read_bytes()
    print("  sample bytes preserved  :", a == b, f"({len(a)} bytes)")

    hexdump = m.tool_read_file(
        {"path": r"C:\task\environment\workspace\assets\sample.wfmt"},
        "probe", view)
    print("  hex dump head:")
    for line in hexdump.splitlines()[:4]:
        print("   >", line)
finally:
    shutil.rmtree(work, ignore_errors=True)

print()
print("DONE")
