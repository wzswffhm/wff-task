● 在 Windows 上搭建 Linux 环境 (WSL2）
○ windows功能中启用“适用于Linux的Windows子系统”和虚拟机平台
○ 开启 WSL2 功能 
```
wsl --install
```
○ 如果之间命令执行失败了，通过 https://github.com/microsoft/WSL/releases 链接手动安装WSL
○ 设置 WSL2 为默认版本 wsl --set-default-version 2
○ 安装Linux发行版镜像，一般可以直接在 windows store 中搜索安装Ubuntu
○ 也可以选择直接在命令行通过命令安装，不过一般网络环境比较差的情况下，这个安装时间会比较长

```
wsl -l -o wsl --install Ubuntu-22.04
```

● 安装Docker Desktop
○ https://www.docker.com/products/docker-desktop/
○ 关键配置：在安装过程中，请务必勾选 "Use WSL 2 instead of Hyper-V" (使用 WSL 2 替代 Hyper-V) 这个选项。
○ 启动与集成：安装完成后，启动 Docker Desktop。然后在它的设置 (Settings) -> Resources (资源) -> WSL Integration (WSL 集成) 中，开启你刚刚安装的 Ubuntu 发行版的集成开关。

● 打开Ubuntu
○ 安装后首次启动会让你设置一个用户名和密码
○ 配置完密码后，需要直接进入user@localhost:~ 这样的界面，才能继续操作，否则在root@localhost:~ 这样的界面下操作安装的依赖环境会乱

```
# 验证 Docker，因为Docker Desktop已经集成了Ubuntu，所以不需要再安装
docker --version

# 安装 uv (Python包管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh
# 验证 uv
uv --version

# 安装 Harbor
uv tool install harbor
# 验证 Harbor
harbor --version
```

**explorer.exe**
通过资源管理器访问文件系统将下载的uv文件移动到~目录（因为curl无响应）

重要提醒
文件路径：在 WSL2 中，建议将所有项目文件放在 Linux 文件系统内（如 ~/harbor-projects），
不要放在 /mnt/c/ 下，以避免性能问题。

Docker 服务：每次使用 Docker 相关命令前，请确保 Windows 上的 Docker Desktop 已经启动。




难度提升方向
1. 增加推理深度 — 从"定位修复"到"因果链推理"
当前：Bug 相对独立，修一个是一个
升级：设计级联 Bug——表面 Bug A 的真正原因是深层 Bug B，B 的原因又是 C。Agent 必须追踪完整因果链才能修复
示例：数据损坏 → 校验失败 → 实际是加密层密钥轮换时序问题 → 根源是配置热加载缺少内存屏障
4. 从"修复已知接口"到"逆向理解协议"
当前：测试用例明确定义了期望行为
升级：
只给协议规范文档（RFC 风格），不给具体测试
Agent 需要从文档中推导实现细节
或者给抓包数据（pcap），让 Agent 逆向协议行为
5. 增加规模和数据量
当前：代码量在几百行到一两千行级别
升级：
万行级别代码库，单个文件 500+ 行
大量间接调用和抽象层
需要 Agent 做有效的代码导航策略
6. 引入时间维度和状态演化
当前：静态代码修复
升级：
Git 历史任务：给一段 commit 历史，问"哪次提交引入了回归"
增量修复：先修 A，再基于修复后的代码修 B，B 的答案依赖于 A 的正确性
性能回归定位：功能正确但性能下降，需要 profiling
8. 弱化提示信号
当前：instruction.md 描述清晰，测试报错明确
升级：
模糊的用户报告（"有时候偶尔会丢数据"）
没有明确的错误堆栈，只有日志片段
测试本身也有 Bug（需要先识别测试错误再修代码）
9. 架构设计类任务
当前：代码已存在，只需修改
升级：
给需求文档，从零设计模块接口
评估多个设计方案并选择
编写设计文档而非仅代码
10. 对抗性任务
最高难度：
代码中包含误导性注释（故意写错的注释）
变量命名具有欺骗性
需要 Agent 不盲信表面信息，交叉验证