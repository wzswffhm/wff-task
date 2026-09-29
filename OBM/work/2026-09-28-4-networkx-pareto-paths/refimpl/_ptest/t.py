import shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, r"C:/Users/Administrator/Desktop/OBM/skills/obm-task-production/scripts")
from verify_agent_patch import prepare_app_context

tmp = Path(tempfile.mkdtemp())
app = tmp / "app"
(app / "marshmallow").mkdir(parents=True)
(app / "marshmallow" / "schema.py").write_text("a=1\nb=2\nc=3\n")
(app / "networkx").mkdir()
(app / "networkx" / "algo.py").write_text("x=1\ny=2\n")

p1 = tmp / "m1.patch"
p1.write_text("""diff --git a/src/marshmallow/schema.py b/src/marshmallow/schema.py
--- a/src/marshmallow/schema.py
+++ b/src/marshmallow/schema.py
@@ -1,3 +1,3 @@
 a=1
-b=2
+b=9
 c=3
""")
p2 = tmp / "m2.patch"
p2.write_text("""diff --git a/networkx/algo.py b/networkx/algo.py
--- a/networkx/algo.py
+++ b/networkx/algo.py
@@ -1,2 +1,2 @@
 x=1
-y=2
+y=7
""")
p3 = tmp / "m3.patch"
p3.write_text("""diff --git a/tests/test_zz.py b/tests/test_zz.py
new file mode 100644
--- /dev/null
+++ b/tests/test_zz.py
@@ -0,0 +1,1 @@
+def test_zz(): pass
""")
p_empty = tmp / "empty.patch"; p_empty.write_text("")

for name, patch, rel, expect in [
    ("marshmallow_src_to_flat", p1, "marshmallow/schema.py", "b=9"),
    ("networkx_level0",       p2, "networkx/algo.py",       "y=7"),
]:
    dest = tmp / ("d_" + name.replace("/", ""));
    prepare_app_context(app, patch, dest)
    got = (dest / rel).read_text().strip()
    print(f"{name:26s} -> {got!r} {'OK' if expect in got else 'FAIL'}")

dest = tmp / "d_noise"; prepare_app_context(app, p3, dest)
print(f"{'noise-only patch':26s} -> 未报错 OK，tests/ 未创建：{(dest/'tests').exists()}")

dest = tmp / "d_empty"; prepare_app_context(app, p_empty, dest)
print(f"{'empty patch':26s} -> 基线 OK：{(dest/'marshmallow/schema.py').read_text().strip()!r}")
