请直接在当前打开的仓库中完成下面的软件工程任务。先阅读相关实现和现有测试，实际修改代码并运行合适的测试，不要只给出建议。不要访问网络，也不要通过修改、删除或跳过测试规避失败。

## 题目

任务概述：
为 networkx 增加一个公开的多目标（帕累托）最短路径查询 API：nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)。它在同一张图上同时考虑两条可加属性（成本与权重），返回 source 到 target 之间所有互不支配的 (cost, weight) 组合，并为每个组合给出恰好实现该组合的简单路径。
改动是新增一个公开算法及其导出。其一，公开入口签名 nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)，两条属性名可配置，默认 cost 与 weight，并支持可选的双上界。其二，返回语义：结果是 record 列表，每条 record 为 {cost, weight, path}，其中 path 是节点序列的简单路径，首尾必须是 source 与 target，且沿路径两条属性之和必须精确等于该 record 声明的 cost 与 weight。其三，集合语义：被支配的组合不得出现，可达的非支配组合不得遗漏；支配定义为分量均不大于且至少一项严格更小。其四，排序与边界：结果按 cost 升序、cost 相同时按 weight 升序；source 等于 target 时返回仅含零代价零权重的单条记录；不可达与节点缺失分别抛出既有的 NetworkXNoPath 与 NodeNotFound；被上界挡空时返回空列表；负属性抛 ValueError；多重图抛 NetworkXNotImplemented。其五，兼容与不变量：新 API 完全附加，不改变任何既有算法、导出或异常的行为；它是纯函数，不修改传入图，且同一输入重复调用结果完全一致。

在 networkx 中实现并导出一个公开 API：nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)。

语义契约（全部为可观察行为）：
1) 每条边带两条可加属性（默认名 cost 与 weight）。边缺少某条属性时该属性按 0 计。
2) 返回 source 到 target 之间所有【非支配】的 (cost, weight) 组合。支配定义为：(c1, w1) 支配 (c2, w2) 当且仅当 c1 <= c2 且 w1 <= w2 且 (c1 < c2 或 w1 < w2)。返回结果中不得出现被支配的组合，也不得遗漏任何可达的非支配组合。
3) 返回类型为列表，元素是字典 {cost, weight, path}；path 必须是【简单路径】（同一节点不重复出现），首元素为 source、末元素为 target，并且沿 path 累加两条属性必须【精确等于】该记录声明的 cost 与 weight。
4) 结果按 cost 升序排序；cost 相同时按 weight 升序（因此前沿中 weight 随 cost 严格递减）。
5) source == target 时返回单条 {"cost": 0, "weight": 0, "path": [source]}。
6) source 或 target 不在 G 中时抛 networkx 既有的 NetworkXNoPath 之外的节点错误类型：NodeNotFound。target 在 G 中但与 source 不连通时抛 NetworkXNoPath。
7) 若可达但不存在任何同时满足 max_cost 与 max_weight 上界的路径，返回空列表 []（不抛异常）。上界只用于过滤候选路径，不得改变其余语义，也不得因剪枝而遗漏仍在上界内的非支配组合。
8) 路径中出现负的 cost 或 weight 时抛 ValueError。
9) 多重图（MultiGraph / MultiDiGraph）不支持，抛 NetworkXNotImplemented。
10) 必须同时支持有向图与无向图。
11) 纯函数：不得修改 G（节点集、边集、边属性都不变）；对同一输入重复调用必须返回完全相同的结果（含顺序）。
12) 性能：在 4000 个节点、16000 条边的随机有向图（cost 与 weight 均为 0..20 的整数）上，单次 pareto_paths 调用必须在 30 秒内返回；退化为枚举全部简单路径的实现无法满足该要求。

判定依据只有可观察行为：返回组合的集合与顺序、每条 record 的 path 是否为简单路径且属性精确吻合、边界输入下的返回或异常种类、以及纯函数与规模要求。不与任何参考实现比对。

任务难点：
- 支配语义的精确实现：必须区分「被支配」与「完全相等」。若只按严格改进去剪枝，等价组合会被反复展开，在零权重环上导致结果重复乃至不终止；若剪枝过强，又会静默丢掉前沿上的组合。前沿必须既不重不漏。
- 给出精确见证：每条 record 必须配一条简单路径，其两条属性之和精确等于声明的组合。由于搜索过程可能走过带环的路线，必须能还原出剥离环之后仍然属性不变的简单路径；而 witness 又不能因为随意取边而算错属性。
- 上界过滤与边界行为的相互作用：max_cost / max_weight 的剪枝必须保持完备性（上界内仍在前沿的组合不能丢），同时要分别处理 source 等于 target、节点缺失、不可达、可达但被上界挡空这四种不同结局，并给出各自规定的返回值或异常类型。
- 规模与确定性：小图可以正常枚举，但数千节点/上万条边的实例无法承受朴素枚举，必须设计有效的多标号搜索与支配剪枝；同时输出顺序与重复调用结果必须完全确定，不能依赖字典遍历或集合顺序。

完成后请简要说明修改内容和实际运行的测试结果。
