# 领域分类表（外发题包 category 枚举，禁止自造近义说法）

> 来源：《外发版-评测题包交付规范 v4》(20260808) 附录领域分类表。
> 用法：task.toml 的 `category_l1` / `category_l2` / `scene_l3` 必须逐字取自下表枚举原文；`[metadata].domain` 取一级分类。

| 一级分类 | 二级分类 | 细分场景（scene_l3 枚举） |
|---|---|---|
| 非常规语言 | COBOL / JCL | 银行核心系统批处理程序维护；大型机报表程序修改；COBOL→Java 迁移改写与逻辑等价校验；JCL 作业调度脚本编写与排错 |
| 非常规语言 | ABAP | SAP 报表（ALV）开发；用户出口 / BAdI 增强；IDoc / RFC / BAPI 接口开发；智能表单（Smart Forms）；ECC→S/4HANA 代码适配改造 |
| 非常规语言 | RPG（IBM i / AS400） | AS400 遗留业务程序维护；RPG III→RPG IV / Free-format 改写；与 DB2 for i 交互的批处理逻辑 |
| 非常规语言 | Verilog / SystemVerilog | RTL 模块设计（FIFO、仲裁器、总线接口）；UVM 验证平台搭建；Testbench 与断言（SVA）编写；时序约束与综合脚本配合 |
| 非常规语言 | VHDL | FPGA 逻辑设计（Xilinx / Intel）；状态机与接口时序实现；军工航天遗留 VHDL 代码维护 |
| 非常规语言 | MATLAB / Simulink | 信号处理与滤波器设计；控制系统建模仿真；Simulink 模型搭建与代码生成（Embedded Coder）；图像处理算法原型 |
| 非常规语言 | VBA | Excel 自动化报表与数据清洗；跨工作簿批量处理；Access 小型业务系统维护；Outlook / Word 办公自动化宏 |
| 非常规语言 | Solidity / 智能合约语言 | ERC-20 / ERC-721 合约编写；DeFi 协议逻辑（质押、借贷、AMM）；合约安全审计（重入、溢出、权限）；Gas 优化 |
| 非常规语言 | AutoLISP / VBA for CAD | AutoCAD 批量图纸处理（标注、图层、块）；自定义绘图命令；图纸信息提取导出 |
| 非常规语言 | Fortran | 气象 / 海洋数值模式维护（WRF 等）；有限元遗留代码修改；Fortran 与 C / Python 混合编程封装 |
| 非常规语言 | R | 统计建模与假设检验；临床试验数据分析；生信包（Bioconductor）分析流程；ggplot2 出版级绘图；Shiny 交互应用 |
| 非常规语言 | SAS | 临床试验统计编程（CDISC / SDTM / ADaM）；金融风控评分卡；SAS 宏程序维护；SAS→Python/R 迁移 |
| 非常规语言 | PLC 语言（梯形图 / ST，IEC 61131-3） | 产线逻辑控制程序（西门子 TIA / Codesys / 三菱）；运动控制与伺服配置；与 HMI / SCADA 联调；安全联锁逻辑 |
| 非常规语言 | LabVIEW（G 语言） | 测试测量系统搭建；仪器控制（GPIB / VISA）；数据采集（DAQ）与实时显示程序 |
| 非常规语言 | 汇编（x86 / ARM / MCU） | 引导程序（Bootloader）与启动代码；中断服务与关键路径优化；逆向工程与反汇编分析；单片机裸机驱动 |
| 非常规语言 | 着色器语言（GLSL / HLSL / WGSL） | 渲染特效（水面、体积光、后处理）；计算着色器（Compute Shader）优化；Shadertoy 风格程序化图形 |
| 非常规语言 | TCL | EDA 工具自动化脚本（Vivado / Design Compiler / ICC）；综合与布局布线流程脚本；仿真回归脚本 |
| 非常规语言 | Perl | 遗留运维 / 文本处理脚本维护；老生信 pipeline（BioPerl）修补；Perl→Python 迁移 |
| 非常规语言 | Delphi / Object Pascal | 遗留桌面业务系统（进销存、医院、政务）维护；老组件（BDE、VCL）兼容处理；Delphi 版本升级迁移 |
| 非常规语言 | 数据库过程语言（PL/SQL / T-SQL 遗留存储过程） | 千行级遗留存储过程理解与重构；Oracle→PostgreSQL / 国产库迁移改写；游标与批处理性能优化 |
| 非常规语言 | G 代码 / 数控编程 | CNC 加工程序编写与刀路修改；宏程序（参数化加工）；后处理器定制 |
| 非常规语言 | 函数式小众语言（Haskell / OCaml / Erlang / Elixir） | 金融领域 DSL 与类型建模；电信高并发系统（Erlang/OTP）维护；编译器 / 静态分析工具开发 |
| 非常规语言 | Prolog / Lisp 家族 | 规则引擎与逻辑推理程序；Emacs Lisp 插件开发；遗留专家系统维护 |
| 非常规语言 | Groovy / 构建 DSL | Jenkins Pipeline 编写与排错；Gradle 构建脚本定制；nextflow 生信流程脚本 |
| 非常规语言 | MUMPS（M 语言） | 医疗信息系统（VistA / InterSystems Caché）维护；全局变量数据结构操作；接口改造 |
| 非常规语言 | 其他 | 其他非常规编程语言 |