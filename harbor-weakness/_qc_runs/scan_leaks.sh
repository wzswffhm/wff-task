#!/bin/bash
# 扫描所有会暴露答案的文本：gen_inputs.py 注释、input_files 里的提示、README/dictionary
IN=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-152/environment/input_files
G=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/work-282-v2/gen_inputs.py

echo "=== [1] gen_inputs.py 里的引导性/答案注释 ==="
grep -nE '隐式陷阱|重复导出|量级错位|勾稽暴露|needs|trap|不能提示|不可提示|埋点|无标注|无任何标注|答案' "$G" 2>/dev/null | head -40

echo
echo "=== [2] input_files 里含 重复/去重/优先级/量级/错位/勾稽 等提示词 ==="
grep -rnE '重复|去重|duplicate|de-dup|优先级|priority|量级|错位|magnitude|勾稽|不一致|待核验|pending re-verification|核验' "$IN" 2>/dev/null | grep -viE 'Source_Index.csv.*Priority|data_dictionary|数据字典' | head -40

echo
echo "=== [3] README / data_dictionary 是否有引导 ==="
grep -nE '重复|未审|优先级|量级|核验|勾稽|不要直接采信|须核对' "$IN/00_README.md" "$IN/data_dictionary.md" 2>/dev/null | head -30
