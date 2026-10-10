# Legacy Workpaper Notes（上一版底稿说明）

上一版底稿 `legacy/Candidate_Model_v0.xlsx` 存在下列已知处理，**不应默认正确**：

1. 以管理层 Adjusted EBITDA 直接作为盈利质量结论。
2. 以 2023 年收入作为估值分母。
3. 净现金桥仅计入现金，遗漏有价证券。
4. 将全部发行股份视为 primary。
5. 将 greenshoe 预设计入 Base。
6. 承销费按 primary + secondary 全部股份计提。
7. 将 secondary 股份计入发行后总股数。
8. 将 secondary 所得款项计入公司现金。
9. 稀释指标分子分母口径不一致。
10. 定价建议主要依据 peer high case 上调。
11. 模型内存在未解析的引用错误单元格，导致部分联动失效。

复核时应逐条判断上述处理是否成立，并在模型中记录所发现的问题与正确处理。
