# wtask 任务 XML 模式与调度语义（权威规格）

> 本文是 `wtask` 的**权威契约**。`wtask` 是我们在 Windows 侧调度运维作业时
> 使用的一个纯 Python 子集实现：它只负责「解析任务 XML → 算出接下来什么时候运行」，
> 不真正创建系统计划任务。
>
> 下游依赖两个性质：**同一份任务 XML 在任何时候算出的运行时刻完全一致**，
> 以及 **规范化序列化可原样回写**（配置管理系统按字节 hash 做增量同步）。

---

## 1. 顶层结构

```xml
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers> … 至少一个触发器 … </Triggers>
  <Settings> … 可选 … </Settings>
</Task>
```

* 根元素必须是 `<Task>`。
* `version` 属性只接受 `"1.0"` 与 `"1.2"`。
* `<Triggers>` 必须存在且非空。
* 根下其它元素（`<RegistrationInfo>`、`<Actions>`、`<Principals>`、`<Data>` 等）
  本实现**忽略**（不建模、不回写）。

`<Settings>` 可包含：

| 元素 | 可选 | 默认 | 语义 |
|---|---|---|---|
| `MultipleInstancesPolicy` | 是 | `IgnoreNew` | 原样保留的字符串 |
| `Enabled` | 是 | `true` | 任务总开关 |
| `ExecutionTimeLimit` | 是 | 不限 | ISO-8601 时长；**`PT0S` 等于「不限」** |
| `RandomDelay` | 是 | `PT0S` | 随机延迟，见 §6 |

---

## 2. 触发器

`<Triggers>` 下只允许 `<CalendarTrigger>` 与 `<TimeTrigger>`；出现别的元素是
**未知触发器**。

`<TimeTrigger>`（一次性）允许的子元素：

```
<StartBoundary>  必填
<EndBoundary>    可选
<Enabled>        可选，默认 true
<Repetition>     可选
```

`<CalendarTrigger>` 在以上四项之外，**必须且只能**再带一个日程元素：

```
<ScheduleByDay> | <ScheduleByWeek> | <ScheduleByMonth> | <ScheduleByMonthDayOfWeek>
```

出现 0 个或 ≥2 个日程元素都是内部矛盾。

时间文本一律是本地 naive 时间，格式固定为 `YYYY-MM-DDTHH:MM:SS`。
`<Enabled>` 的取值只接受 `true` / `false`（大小写不敏感，也接受 `1` / `0`）。

---

## 3. 四种日程

### 3.1 `ScheduleByDay`

```xml
<ScheduleByDay><DaysInterval>3</DaysInterval></ScheduleByDay>
```

* `DaysInterval` 可选，默认 `1`，允许范围 **1..365**。
* **锚点是 `StartBoundary` 的日期**：只有当
  `(当天日期 − StartBoundary 日期).days % DaysInterval == 0` 时才触发。
  换句话说，`DaysInterval=3`、起点 `2026-01-01` 时触发日是 1/1、1/4、1/7 …。

### 3.2 `ScheduleByWeek`

```xml
<ScheduleByWeek>
  <DaysOfWeek><Monday/><Wednesday/></DaysOfWeek>
  <WeeksInterval>2</WeeksInterval>
</ScheduleByWeek>
```

* `DaysOfWeek` 必填，列出星期名（`Sunday`…`Saturday`，可多个）。
* `WeeksInterval` 可选，默认 `1`，范围 **1..52**。
* 周按 **周一起始** 划分。从 `StartBoundary` 所在的周算起，第 0 周触发；
  之后每隔 `WeeksInterval` 周触发一次（即周序号差是 `WeeksInterval` 的整数倍）。

### 3.3 `ScheduleByMonth`

```xml
<ScheduleByMonth>
  <DaysOfMonth><Day>1</Day><Day>15</Day></DaysOfMonth>
  <Months><January/><March/></Months>
</ScheduleByMonth>
```

* `DaysOfMonth` 必填，至少一个 `<Day>`，取值 **1..31**。
* `Months` 必填，至少一个月名。
* 只有「月份在 `Months` 里」且「日号在 `DaysOfMonth` 里」才触发。
* 某个月里**不存在**的日号（例如 2 月的 30 日）自然不触发，**不是错误**。

### 3.4 `ScheduleByMonthDayOfWeek`

```xml
<ScheduleByMonthDayOfWeek>
  <Weeks><Week>1</Week><Week>3</Week></Weeks>
  <DaysOfWeek><Friday/></DaysOfWeek>
  <Months><January/></Months>
</ScheduleByMonthDayOfWeek>
```

* `Weeks` 必填，取值 **1..5**；`DaysOfWeek` 必填；`Months` 必填。
* 月内的「日历周」按日号划分：1–7 日为第 1 周，8–14 日为第 2 周，
  15–21 日为第 3 周，22–28 日为第 4 周，29 日及以后为第 5 周。
* **`<Week>5</Week>` 表示「该月的最后一周」**。因此在一个只有 4 个日历周的月份
  （例如平年 2 月）里，`Week=5` 匹配的是第 4 周。这是本项目刻意采用的语义。

---

## 4. 出现时刻

* 每个触发器的**主出现日**由 §3 的日程决定，**时刻**一律取
  `StartBoundary` 的时分秒。
* 主出现时刻必须 **≥ `StartBoundary`**。
* 若存在 `<EndBoundary>`，则 **> `EndBoundary`** 的主出现时刻不再触发。

---

## 5. `Repetition`

```xml
<Repetition>
  <Interval>PT30M</Interval>
  <Duration>PT2H</Duration>
  <StopAtDurationEnd>false</StopAtDurationEnd>
</Repetition>
```

* `Interval` 必填且必须是正时长。
* 每次主出现 `T` 之后，还会在 `T + k×Interval`（k = 0, 1, 2, …）继续触发，
  直到**偏移量达到 `Duration` 为止**：即只保留满足 `k×Interval < Duration` 的那些。
* `Duration` 缺省表示**不限时长**（一直按 `Interval` 重复）。
* 重复产生的时刻同样受 `EndBoundary` 约束。
* `StopAtDurationEnd` 只做原样保留，不影响 `next_runs` 的结果。

---

## 6. 时长文本（ISO-8601 子集）

接受：`P<n>D`、`PT<n>H`、`PT<n>M`、`PT<n>S` 及其组合，例如
`P3D`、`PT72H`、`P1DT2H3M4S`、`PT0S`。秒以外的分量必须是整数，不支持小数秒。

**规范形式**（`format_duration` 的输出，也是回写时使用的形式）：

1. 先把总秒数分解成「天 / 时 / 分 / 秒」；
2. 只写非零分量；时分秒全为 0 时省略整个 `T` 段；
3. 零时长写作 `PT0S`。

例：`PT72H` → `P3D`；`PT2H` → `PT2H`；`PT90M` → `PT1H30M`；`P1DT2H3M4S` 不变。

---

## 7. 规范化序列化

`task_to_xml(task)` 的输出必须满足：

* 元素顺序固定：`Triggers` → `Settings`；
  触发器内：`StartBoundary` → `EndBoundary` → `Enabled` → 日程 → `Repetition`；
  `Settings` 内：`MultipleInstancesPolicy` → `Enabled` → `ExecutionTimeLimit` → `RandomDelay`。
* **缺省值省略**：`Enabled` 只在为假时写出；`StopAtDurationEnd` 只在为真时写出；
  `ExecutionTimeLimit` / `RandomDelay` 为「不限 / 零」时省略。
* 日期时间写作 `YYYY-MM-DDTHH:MM:SS`。
* 星期的书写顺序按 `Sunday, Monday, …, Saturday`；月份按 `January … December`；
  `<Day>` 升序、`<Week>` 升序。
* 幂等：`task_to_xml(parse_task_xml(x))` 与再次解析后的输出完全一致；
  且 `parse_task_xml(task_to_xml(t)) == t`。

---

## 8. 运行时刻查询

```python
next_runs(task, after, count) -> list[datetime]
plan_window(task, start, end) -> list[datetime]
```

* `next_runs` 返回 **严格晚于 `after`** 的、最近的 `count` 次运行时刻，
  升序、去重；不足 `count` 次就返回实际数量。
* **任务被禁用时返回空列表**；**单个触发器被禁用时跳过该触发器**。
* `plan_window` 返回落在 **(start, end]** 内的全部运行时刻。

---

## 9. 错误模型

所有「结构 / 取值」问题都必须抛 `TaskDefError`，且 `err.kind` 取值如下：

| kind | 何时 |
|---|---|
| `xml` | XML 语法错误 |
| `schema` | 根元素不对、必填子元素缺失、同一子元素重复 |
| `version` | `version` 属性不受支持 |
| `trigger` | `<Triggers>` 下出现未知触发器；触发器内出现未知元素；日程元素个数不对；`<DaysOfWeek>` 为空或有重复；`<Weeks>` / `<DaysOfMonth>` 为空；`<DaysOfWeek>` 缺失 |
| `range` | 整数越界（`DaysInterval`、`WeeksInterval`、`Day`、`Week`）；日期时间文本非法；布尔文本非法 |
| `duration` | 时长文本非法 |
| `structure` | `<Triggers>` 缺失或为空；`EndBoundary` 早于 `StartBoundary` |

不得抛 `ValueError` / `struct.error` / `IndexError` 之类的临时异常。
