import sys
sys.path.insert(0, r"C:\Users\Administrator\AppData\Roaming\uv\tools\harbor\Lib\site-packages")
from dirhash import dirhash, filter_paths
p = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\wfflab__wpeimg-219-v1.4.0-delivery"
print("expected 8af4efbac29d722f82574432c79da66a49ffcc345cbeafacbf1ef798be49236b")
print("full     ", dirhash(p, "sha256"))
print("no-jobs  ", dirhash(p, "sha256", filter=filter_paths(p, ignore=["jobs"])))
