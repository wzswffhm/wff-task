请直接在当前打开的仓库中完成下面的软件工程任务。先阅读相关实现和现有测试，实际修改代码并运行合适的测试，不要只给出建议。不要访问网络，也不要通过修改、删除或跳过测试规避失败。

## 题目

任务概述：
为 networkx 增加一组互相一致的公开多目标（帕累托）最短路径 API：核心查询 nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)，只返回配对结果的 nx.pareto_frontier(...)，以及可变图上的索引 nx.ParetoIndex(G, source, weight="weight", cost="cost")。它们在同一张图上同时考虑两条可加属性，返回 source 到 target 之间所有互不支配的 (cost, weight) 组合，并为每个组合给出恰好实现该组合的简单路径；索引还支持在图上增删边后继续查询，且结果必须与「对当前图直接调用函数式入口」完全一致。
改动是新增一个公开算法模块及其导出（三个入口）。其一，签名：nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)；nx.pareto_frontier(...) 同签名但只返回排序后的 (cost, weight) 列表；nx.ParetoIndex(G, source, weight="weight", cost="cost") 提供 pareto / frontier / update_edge / remove_edge / reset / graph。其二，两条属性名可配置，且既可为属性名字符串也可为可调用对象 f(u, v, data) -> number。其三，pareto_paths 返回 record 列表，每条为 {cost, weight, path}，path 为简单路径，首尾为 source 与 target，沿路径属性之和精确等于声明的组合；pareto_frontier 必须恒为 pareto_paths 的 (cost, weight) 投影。其四，集合语义：被支配组合不得出现，可达的非支配组合不得遗漏；支配为分量均不大于且至少一项严格更小；且前沿集合与边的插入顺序无关。其五，排序与边界：按 cost 升序、cost 相同时按 weight 升序；source 等于 target 返回仅含零属性单条记录；不可达与节点缺失分别抛现有的 NetworkXNoPath 与 NodeNotFound；被上界挡空返回空列表；负属性抛 ValueError；多重图抛 NetworkXNotImplemented。其六，索引语义：构造时对图做快照且不修改调用方图；任意 update_edge / remove_edge 序列后，pareto / frontier 的结果必须等于对当前索引图直接调用函数式入口的结果（含空结果与异常种类）；remove_edge 对不存在的边抛 NetworkXError；reset 恢复构造时快照。其七，兼容与不变量：新 API 完全附加，不改变任何既有算法、导出或异常的行为；函数式入口是纯函数，同一输入重复调用结果完全一致。

在 networkx 中实现并导出三个互相一致的公开入口：

- nx.pareto_paths(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)
- nx.pareto_frontier(G, source, target, weight="weight", cost="cost", *, max_cost=None, max_weight=None)
- nx.ParetoIndex(G, source, weight="weight", cost="cost")

语义契约（全部为可观察行为）：
1) 每条边带两条可加属性（默认名 cost 与 weight）。边缺少某条属性、或该属性为 None 时按 0 计。
2) 返回 source 到 target 之间所有【非支配】的 (cost, weight) 组合。支配定义为：(c1, w1) 支配 (c2, w2) 当且仅当 c1 <= c2 且 w1 <= w2 且 (c1 < c2 或 w1 < w2)。返回中不得出现被支配的组合，也不得遗漏任何可达的非支配组合。
3) pareto_paths 返回列表，元素是字典 {cost, weight, path}；path 必须是【简单路径】（同一节点不重复出现），首元素为 source、末元素为 target，并且沿 path 累加两条属性必须【精确等于】该记录声明的 cost 与 weight。
4) 结果按 cost 升序排序；cost 相同时按 weight 升序。
5) source == target 时返回单条 {"cost": 0, "weight": 0, "path": [source]}。
6) source 或 target 不在 G 中时抛 NodeNotFound。target 在 G 中但与 source 不连通时抛 NetworkXNoPath。
7) 若可达但不存在任何同时满足 max_cost 与 max_weight 上界的路径，返回空列表 []（不抛异常）。上界只用于过滤候选路径，不得改变其余语义，也不得因剪枝而遗漏仍在上界内的非支配组合。
8) 路径中出现负的 cost 或 weight 时抛 ValueError。
9) 多重图（MultiGraph / MultiDiGraph）不支持，抛 NetworkXNotImplemented。
10) 必须同时支持有向图与无向图。
11) 纯函数：函数式入口不得修改 G（节点集、边集、边属性都不变）；对同一输入重复调用必须返回完全相同的结果（含顺序）。
12) weight 与 cost 既可以是属性名字符串，也可以是可调用对象 f(u, v, data) -> number。三个入口都必须支持两种写法，且对同一张图两种写法必须给出完全相同的 (cost, weight) 集合与顺序。
13) pareto_frontier 只返回排序后的 (cost, weight) 二元组列表（不返回见证路径），并且必须恒等于 [(r["cost"], r["weight"]) for r in pareto_paths(...)]——在带与不带双上界时都成立。其边界与异常语义与 pareto_paths 完全一致。
14) 前沿集合与图的构造顺序无关：同一批节点与边（属性完全相同）无论以何种顺序插入，pareto_paths 与 pareto_frontier 给出的 (cost, weight) 集合与顺序必须完全相同。
15) ParetoIndex(G, source, ...) 是可变图上的索引。构造时必须对传入图做快照，【不得修改调用方的 G】；并以 source 为起点。其接口：
    - idx.pareto(target, *, max_cost=None, max_weight=None)：结果必须与 nx.pareto_paths(idx.graph, source, target, ...) 完全相同。
    - idx.frontier(target, *, max_cost=None, max_weight=None)：同上，对应 nx.pareto_frontier。
    - idx.update_edge(u, v, **attrs)：新增或覆盖这条边（必要时补建节点）。
    - idx.remove_edge(u, v)：删除该边；若该边不存在则抛 NetworkXError。
    - idx.reset()：把索引图恢复为构造时的快照。
    - idx.graph：当前索引图，必须反映全部已执行的 update_edge / remove_edge。
    任意 update_edge / remove_edge 序列之后，两条查询的结果都必须等于「对 idx.graph 直接调用对应函数式入口」的结果，包括空结果与抛出的异常种类。
16) 三个入口的异常语义完全一致：缺失节点 NodeNotFound；连通但无路径 NetworkXNoPath；负属性 ValueError；多重图 NetworkXNotImplemented。ParetoIndex 在构造时就校验 source 是否存在与是否为多重图；对不存在的 target 查询时同样抛 NodeNotFound。
17) 性能：在 3000 个节点、12000 条边的随机有向图上，构造索引、执行一次 update_edge 与一次 remove_edge、再完成一次 pareto 与一次 frontier 查询，合计须在 30 秒内返回；在 4000 个节点、16000 条边的随机有向图（cost 与 weight 均为 0..20 的整数）上，单次 pareto_paths 调用须在 30 秒内返回。退化为枚举全部简单路径的实现无法满足该要求。

判定依据只有可观察行为：返回组合的集合与顺序、每条 record 的 path 是否为简单路径且属性精确吻合、frontier 与 paths 的投影关系、索引在变更前后与全量重算的一致性、边界输入下的返回值或异常种类、以及纯函数与规模要求。不与任何参考实现比对。

任务难点：
- 支配语义的精确实现：必须区分「被支配」与「完全相等」。若只按严格改进去剪枝，等价组合会被反复展开，在零属性环上导致结果重复乃至不终止；若剪枝过强，又会静默丢掉前沿上的组合。前沿必须既不重不漏。
- 给出精确见证：每条 record 必须配一条简单路径，其两条属性之和精确等于声明的组合。由于搜索过程可能走过带环的路线，必须能还原出剥离环之后仍然属性不变的简单路径；而 witness 又不能因为随意取边而算错属性。
- 上界过滤与边界行为的相互作用：max_cost / max_weight 的剪枝必须保持完备性（上界内仍在前沿的组合不能丢），同时要分别处理 source 等于 target、节点缺失、不可达、可达但被上界挡空这四种不同结局，并给出各自规定的返回值或异常类型。
- 规模与确定性：小图可以正常枚举，但数千节点/上万条边的实例无法承受朴素枚举，必须设计有效的多标号搜索与支配剪枝；同时输出顺序与重复调用结果必须完全确定，不能依赖字典遍历或集合顺序。
- 三入口的一致性：frontier 必须恒为 paths 的 (cost, weight) 投影，不得出现「一个入口按上界过滤、另一个不过滤」这类漂移；索引的查询又必须与函数式入口逐项相同。任何在两个入口之间各自实现一套逻辑的做法，都会在边界与异常上分叉。
- 索引在变更后的正确性：update_edge / remove_edge 之后必须给出与全量重算一致的结果。带缓存或增量维护的实现最容易在这里出错——删掉一条曾参与最优解的边、或覆盖一条端点相同而属性不同的边之后，陈旧结果会被继续返回；同时构造索引不得改动调用方传入的图。
- 可调用属性与顺序无关性：weight / cost 允许是可调用对象，三个入口都要统一解析，且与属性名写法结果一致；此外前沿集合必须与边的插入顺序无关，这要求支配剪枝与结果排序都不依赖邻接表或字典的遍历顺序。

完成后请简要说明修改内容和实际运行的测试结果。
