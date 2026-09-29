请直接在当前打开的仓库中完成下面的软件工程任务。先阅读相关实现和现有测试，实际修改代码并运行合适的测试，不要只给出建议。不要访问网络，也不要通过修改、删除或跳过测试规避失败。

## 题目

任务概述：
为 marshmallow 的 Schema 增加 schema 感知的结构化 diff：新增 Schema.document_diff(left, right, *, include_unknown=False, ignore_fields=())，对两份文档做字段级比较，返回有序的变更记录，每条含 op（add/remove/change）、path 与 left/right；按 schema 声明的字段遍历并递归 Nested/List，而不做脱离 schema 的通用值比较；可选 include_unknown 与 ignore_fields 控制可见范围，且完全不改变 dump/load/validate 的既有行为。
改动集中在 Schema 的一个新增公开方法及其内部递归辅助上。其一，公开入口：Schema.document_diff(left, right, *, include_unknown=False, ignore_fields=())；left/right 若是 dict 就直接使用，否则先用当前 schema 的 dump 转成 dict 再比较，使调用方既能传已序列化的字典也能传可 dump 的对象。其二，遍历规则：按 schema.fields 的声明顺序逐个字段比较，而不是按输入字典的插入顺序；标量字段左右值不等记 change，只在一侧存在记 add/remove。其三，结构化递归：Nested（单值）按子 schema 递归，path 在字段名后追加子字段名并用点连接；Nested(many=True) 把每个元素当作一份文档、按元素下标递归，path 用 [i]；List 字段按位置逐元素比较，当内层字段仍是 Nested 时继续递归。其四，可见性选项：默认只比较 schema 声明的字段，文档中多出的未知键忽略；include_unknown=True 时把这些未知键也纳入比较；ignore_fields 中的字段名在整个比较中跳过。其五，兼容性：dump、load、validate 及其签名、异常与输出都必须与基线完全一致；document_diff 是纯函数，不修改 schema 或文档，也不新增任何公开类型或破坏既有 API。

在 marshmallow 的 Schema 上实现 document_diff(left, right, *, include_unknown=False, ignore_fields=())。它对比两份文档并返回一个有序的变更记录列表，每个记录形如 {op, path, left, right}。op 取 add、remove 或 change：标量字段左右值不同为 change；某字段只出现在右侧为 add（left 为 None），只出现在左侧为 remove（right 为 None）；某字段同时出现在两侧且相等则该字段无记录。path 用声明字段名以点号连接表达嵌套，例如 address.street；List 或 Nested(many=True) 的元素位置用方括号下标，例如 tags[1]、members[0].age；Nested（单值）递归时按子 schema 的字段继续追加点号路径。比较必须按 schema.fields 的声明顺序遍历，而不是输入字典的顺序，并据此决定每个字段是标量比较还是结构递归：遇到 Nested（单值）就用其内嵌子 schema 继续比较对应子文档；遇到 Nested(many=True) 就把左右两侧按元素下标一一对应，逐元素当作子文档用同一个子 schema 比较；遇到 List 就按位置逐元素比较，当元素自身是 Nested 时继续递归。未知键（文档里有、schema 里没有的键）默认忽略，include_unknown=True 时才纳入比较；ignore_fields 给出的字段名在比较中整体跳过。left/right 可以是 dict，也可以是能用当前 schema dump 出来的对象——对象要先 dump 成 dict 再比较。完全相同的两份文档必须返回空列表。dump、load、validate 的全部签名、异常与输出必须保持与基线一致，不得引入新的公开类型或破坏既有 API。判定依据是可观察行为：返回的变更记录里的 op、path 与左右值，嵌套与列表递归后的路径形态，include_unknown 与 ignore_fields 对结果的影响，以及 dump/load/validate 是否回归；不与任何参考补丁比对。

任务难点：
- 把 diff 建成 schema 驱动而非值驱动：必须沿着 schema.fields 的声明顺序遍历，并按字段类型决定是标量比较还是结构递归，而不是脱离 schema 地通用遍历字典；否则会把未知键、隐藏字段或错误顺序带进结果，也会和没有子 schema 概念的通用比较混淆。
- 正确处理 Nested(many=True)：每个元素是一份文档，要用内嵌子 schema 按元素下标递归比较，path 用 [i]；若把它当成单个嵌套值去取值，会对整型下标 KeyError，或在元素个数变化时给出错误的增删判定。
- 为缺失键与 List 位置定义无歧义的 add/remove/change 语义，并让路径格式（点号与方括号）在不同嵌套深度保持一致；同一字段只在单侧出现应成为 add/remove，相同文档必须为空，列表按位置比较时元素个数不同要正确产生 add/remove 而不是错位成 change。
- 守住选项契约：include_unknown 只在本次比较里把非 schema 键纳入视图，ignore_fields 跳过指定字段，二者都不应污染 schema 的持久状态或影响 dump/load/validate；同时要确认新增方法是纯函数，不修改 schema 或文档，也不改变任何既有公开 API 的行为。

完成后请简要说明修改内容和实际运行的测试结果。
