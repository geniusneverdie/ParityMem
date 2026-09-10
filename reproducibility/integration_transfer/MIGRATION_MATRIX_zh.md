# 新集成的契约配置与核心复用

三项新集成共享同一冻结核心；原迁移阶段与本轮源码核对均支持核心文件零修改。集成工作集中在来源契约、记录字段和消费者条件的映射，具有清晰的复用边界。

| 集成 | 固定版本 | 已确认契约字段 | 主要来源映射 | 核心变更 |
|---|---|---:|---|---:|
| TAU3 | `79975ac5741e23fbb1d2ac44262d62398a6d87bd` | 10/10 | SimulationRun; ToolCall; evaluate_simulation | 0 |
| TOOL_SANDBOX | `165848b9a78cead7ca7fe7c89c688b58e6501219` | 10/10 | Scenario; respond_to_messages; Evaluation.evaluate | 0 |
| APPWORLD | `a072b7a86e7c1d5b1d7175659d750ebb9b79f10a` | 9/10 | AppWorld; Requester.request; evaluate_task | 0 |

τ³-bench和ToolSandbox各10类契约字段完成确认；AppWorld完成9类，并按原登记显式保留HistoryClosure状态。30个字段的来源文件哈希均与当前冻结来源一致。

配置顺序可沿 Session、Observation、Memory/State、Action、Transition、Identifier、Ordering、SideEffect、Scorer、HistoryClosure 十类字段核对。`transfer_binding.json`逐项给出来源文件、符号、状态和哈希；共享编译/投影/配对函数保留在 `full_core/vendor/`。

本表对应原契约实例化阶段，完整/部分BIC、原生测试与后续自然轨迹验证是各自的端点。该表描述契约配置和已记录的核心复用，不推断未登记的适配器开发工时或新增代码量。
