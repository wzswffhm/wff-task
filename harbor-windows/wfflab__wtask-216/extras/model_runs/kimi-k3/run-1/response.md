按 docs/TASKSCHEMA.md 逐条修复了 wtask 的十类缺陷，改动集中在 wtask/duration.py、wtask/schedule.py、wtask/xmlio.py（errors.py / model.py / __init__.py 无需变动，公共 API 名称与签名保持不变）。

wtask/schedule.py（现象 1–7 的计算核心）：
1. 每日日程锚定 StartBoundary 日期：`(day − start.date()).days % DaysInterval == 0`，取代原先错误的「当月日号取模」。
2. 每周日程补上 WeeksInterval：周按周一起始划分，StartBoundary 所在周为第 0 周，周序号差须为 WeeksInterval 的整数倍。
3. ScheduleByMonth 补上 Months 过滤（原先完全没检查月份）。
4. 修正月内日历周序号（1–7 日为第 1 周，原先 `day//7+1` 错位），并实现 `<Week>5</Week> = 该月最后一周`（在只有 4 个日历周的月份匹配第 4 周）。
5. Repetition 展开改为 `k×Interval < Duration`（原先 `<=` 多触发一次）；用 k 值区间直接计算（O(count)），替代原先最多 10 万次的步进循环。
6. 重复时刻同样受 EndBoundary 约束（== EndBoundary 仍触发，> 不触发）。
7. next_runs / plan_window 跳过 `enabled=False` 的触发器；任务级禁用在两个 API 中都返回空列表。
另外：plan_window 改为直接扫描到 end（不再受 HORIZON 截断后过滤），保证 (start, end] 边界与去重；主出现扫描按 repetition 类型裁剪下界，start 很早的任务也能毫秒级完成；HORIZON_DAYS 提升到 4000 天以覆盖低频日程。

wtask/duration.py（现象 8）：format_duration 输出规范形式——先分解为天/时/分/秒，只写非零分量，时分秒全 0 省略 T 段，零时长 PT0S（PT72H→P3D、PT90M→PT1H30M）；改用 days/seconds 字段避免 float 精度问题，拒绝负时长与小数秒。parse_duration 拒绝空分量（P/PT）与悬空 T（P1DT），全部抛 TaskDefError(kind="duration")。

wtask/xmlio.py（现象 9、10 与 §7）：
- version 属性校验：不在 {1.0, 1.2} 抛 kind="version"（缺失时宽容默认 1.2）。
- `<Triggers>` 下未知触发器元素抛 kind="trigger"（原先静默 continue）；ScheduleByDay/Week/Month/MonthDayOfWeek、DaysOfMonth、Weeks、Repetition 内部的未知子元素同样抛 trigger。
- DaysInterval 增加 1..365 范围检查（kind="range"）；DaysInterval/WeeksInterval 空文本按非法整数报 range。
- 日期时间文本先用 `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$` 严格校验再 strptime，非法一律 range。
- ExecutionTimeLimit=PT0S 解析为 None（「不限」），序列化时省略。
- ET.fromstring 同时捕获 ParseError 与 ValueError（带编码声明的 str 输入）统一归为 kind="xml"。
- 序列化：星期/月份/Day/Week 强制按规格顺序输出，multiple_instances/version 做 XML 转义；保持缺省省略规则与固定元素顺序，保证 task_to_xml 幂等且字节稳定（parse∘to_xml 往返相等）。

验证：可见冒烟测试 3 项全部通过；另用临时脚本（已删除）覆盖十条现象、§9 全部 kind 分支、§7 幂等与顺序、§8 边界/去重/两级启用开关、无限重复跨 after、远早 start 的性能等边角场景，全部通过。