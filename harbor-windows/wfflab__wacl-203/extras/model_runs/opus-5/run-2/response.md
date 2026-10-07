修复了 wpublish 的三个核心问题：

1. **递归权限应用** (wpublish/publish.py): publish() 调用 deny() 时添加 recursive=True 参数，确保拒绝项覆盖整棵子树，包括发布时已存在的所有子目录和文件。由于带有 (OI)(CI) 标记，新建的文件也会自动继承拒绝项。

2. **拒绝优先判定** (wpublish/rights.py): can_write() 现在检查 deny 集合是否包含写权限，一旦命中拒绝项立即返回 False，符合 Windows "显式拒绝优先于允许"的访问控制规则。

3. **显式与继承项区分** (wpublish/icacls.py): list_explicit_aces() 现在过滤掉所有 inherited=True 的项，只返回显式设置的 ACE；同时修复了 parse_aces() 中主体名称解析问题，正确处理 icacls 输出中路径前缀与主体名称混在一起的情况。

所有既有测试通过，验证满足全部五项验收标准：递归覆盖、继承生效、拒绝优先、显式过滤、审计通过。