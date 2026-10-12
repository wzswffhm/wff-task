"""按文本锚点移除 run_model_validation.py 的内置端点块，插入 find_config()。"""
import io
import os

P = r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\skills\harbor-windows\scripts\run_model_validation.py"

txt = io.open(P, encoding="utf-8").read()
start_mark = "# ------------------------------------------------------------------ 默认模型配置"
end_mark = "MAX_TOKENS = int(os.environ.get"
i = txt.index(start_mark)
j = txt.index(end_mark)
print("removing %d chars (built-in endpoint block)" % (j - i))

NEW = '''# ------------------------------------------------------------------ 端点配置
# 端点与凭据统一由仓库根的 models.local.json 提供：脚本从自身位置逐级上溯查找。
# 该文件含明文凭据，按甲方要求纳入版本控制，请勿外发。也可用 --config 或
# 环境变量 HARBOR_WINDOWS_ENDPOINTS_JSON 指向别的凭据文件。

CONFIG_FILENAME = "models.local.json"


def find_config():
    """定位端点配置：从脚本所在目录逐级上溯，直到找到 models.local.json。"""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        cand = os.path.join(cur, CONFIG_FILENAME)
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


'''

txt = txt[:i] + NEW + txt[j:]
with io.open(P, "w", encoding="utf-8", newline="\n") as f:
    f.write(txt)

print("DEFAULT_ENDPOINTS still referenced:", "DEFAULT_ENDPOINTS" in txt)
print("find_config defined:", "def find_config()" in txt)
print("file lines:", txt.count("\n") + 1)
