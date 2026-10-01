修复了 wsync 在 Windows 环境下的五类镜像同步问题：

1. **只读文件/目录处理**：在 fsops.py 中新增 clear_readonly() 函数，在删除或覆盖前自动去掉只读属性；remove_tree() 使用 onerror 回调处理只读条目；prune_empty_dirs() 清理只读空目录。

2. **大小写不敏感处理**：修改 path_key() 在 Windows 上将路径键统一转小写；list_entries() 返回规范化的键，确保源与目标中只有大小写不同的路径被正确识别为同一文件。

3. **被占用文件的容错**：在 mirror.py 的 sync_tree() 中用 try-except 包裹每个条目的执行，单个条目失败记入 failed 列表但不中断整次同步。

4. **类型冲突处理**：新增 _clear_path_for_file() 和 _ensure_parent_is_dir()，在创建/更新文件前先清理目标路径上的目录或其它障碍，确保父路径可用。

5. **内容比较与时间戳保留**：新增 content_equal() 进行字节级比较；planner.py 的 needs_update() 在签名相同时仍进行内容比较；copy_file() 复制后用 os.utime() 保留源文件的修改时间，实现幂等同步。

所有修改仅涉及实现代码（wsync/*.py），未改变公开接口签名，未引入第三方依赖，所有既有测试通过。