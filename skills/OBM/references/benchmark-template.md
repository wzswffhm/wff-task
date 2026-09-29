# 新 benchmark 扩展模板

只有在 OBM 任务不是 `deepSWE` 时使用本文件。先收集证据，再创建 `references/<benchmark>.md`，不要直接复制 `deepswe.md`。

## 需要确认的信息

从当前官方文档、示例题和本地运行器确认：

```text
规范枚举名称及大小写：
题目类型和适用场景：
Agent 可见文件：
私有文件：
目录结构：
环境构建方式：
网络规则：
Agent 产物收集方式：
verifier 入口：
评分指标和通过条件：
参考答案的用途：
原有行为保护方式：
运行时限和资源限制：
正式交付结构：
```

每项都要能指出来源文件、文档段落或一份可运行样例。缺少证据时标记未知，不用 DeepSWE 的规则补空白。

## 建立 benchmark reference

新 reference 至少写明：

1. 该 benchmark 衡量什么能力；
2. 什么题目适合，什么题目应拒绝；
3. Agent、verifier 和参考答案分别看到什么；
4. 如何证明基线失败和正确实现通过；
5. 如何保护原有能力或防止取巧；
6. 网络和依赖怎样处理；
7. no-skill/with-skill 如何在相同条件下运行；
8. 正式包包含什么、排除什么；
9. 提交前必须执行哪些命令。

## 增加检查器

不要把新 benchmark 硬塞进 `check_deepswe`。为它增加独立函数，例如：

```python
def check_examplebench(root, proposal, report):
    ...
```

只自动检查能从文件客观判断的事项。相关性、难度、skill 是否有用、是否泄漏解决思路等仍需人工复核，并在报告中作为 manual gate 输出。
