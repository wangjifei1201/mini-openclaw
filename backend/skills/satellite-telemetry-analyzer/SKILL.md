---
name: satellite-telemetry-analyzer
description: Use when 用户询问高分07B01/07C01/07D01卫星遥测参数分析，包括参数发现、阈值判断、区间判断、秒递增、LOG增长、飞轮跳变、温度代码范围或通信异常。
version: 2.1.0
author: 长光卫星
license: MIT
---

# 卫星遥测参数智能分析助手

## 概述

本技能用于回答高分07B01星、高分07C01星、高分07D01星的卫星遥测分析问题。技能负责从用户自然语言中提取卫星、时间、参数和判断条件，加载对应分片，并调用预定义 Python 脚本完成分析。

## 何时使用

当用户询问以下任意遥测分析问题时使用本技能：

- 参数发现：有哪些参数、列出所有参数、可用测点。
- 单参数阈值：低于、高于、大于、小于、等于、是否在范围内。
- 双通电范围：A 和 B 均通电时，C 是否控制在 X-Y 范围内。
- 秒递增：某秒类参数是否每秒增加 1。
- LOG 增长：Log 增长计数是否有增长或变化。
- 飞轮跳变：飞轮1/2/3/4转速是否有跳变。
- 温度代码范围：WD-C001 到 WD-C015 等代码范围是否满足温度区间或 Y±Z。
- 通信异常：设备通电时通信状态是否无效，并且异常计数是否增加。

不要使用本技能处理修改、删除、写入遥测数据的请求。

## 缺少必要信息时

若用户问题属于遥测分析，但缺少必要字段：

- 缺少卫星名称：询问用户指定高分07B01星、高分07C01星或高分07D01星。
- 缺少时间范围：询问用户提供查询日期或起止时间。
- 缺少参数名或代码：询问用户指定遥测参数。
- 不得猜测默认卫星或默认时间。
- 不调用分析脚本，直到必要字段齐全。

## 必须加载的公共分片

每次执行遥测分析时，先读取以下公共分片：

1. `fragments/global-rules.md`
2. `fragments/list-params-step.md`
3. `fragments/output-rules.md`

参数发现类问题只需执行 `fragments/list-params-step.md` 中的 `scripts/list_params.py --json '{}'`，无需加载场景分片。

## 场景匹配优先级

按以下顺序匹配，命中后不再降级到更通用场景：

1. 通信异常：包含“通信无效”、“通信异常”或“异常计数”。
2. 双通电范围：包含两个通断参数，并要求目标参数控制在某范围内。
3. 温度代码范围：包含 WD-C 起止代码范围，且包含温度或 ± 区间。
4. 飞轮跳变：包含“飞轮”和“跳变”。
5. LOG 增长：包含“LOG”、“Log增长”或“增长计数”。
6. 秒递增：包含“每秒增加1”、“秒递增”或“PPS计数”。
7. 单参数阈值：包含低于、高于、大于、小于、等于、之间、控制在等判断。
8. 参数发现：有哪些参数、列出所有参数、可用测点。

## 场景路由表

| 用户意图 | 关键词/模式 | 加载分片 | 强制脚本 |
|---|---|---|---|
| 参数发现 | 有哪些参数、列出所有参数、可用测点 | 无场景分片 | `scripts/list_params.py` |
| 单参数阈值 | 低于、高于、大于、小于、等于、在...之间 | `fragments/scene01-threshold.md` | `scripts/query_range.py` |
| 双通电范围 | A和B均通电、C是否控制在X-Y之间 | `fragments/scene02-dual-power-range.md` | `scripts/dual_power_range.py` |
| 秒递增 | 每秒增加1、秒递增、PPS计数 | `fragments/scene03-second-increment.md` | `scripts/second_check.py` |
| LOG增长 | LOG增长、Log增长计数、增长计数变化 | `fragments/scene04-log-growth.md` | `scripts/log_growth.py` |
| 飞轮跳变 | 飞轮转速跳变、飞轮1/2/3/4 | `fragments/scene05-flywheel-jump.md` | `scripts/flywheel_jump.py` |
| 温度代码范围 | WD-C001到WD-C015、温度、± | `fragments/scene06-temperature-code-range.md` | `scripts/query_range.py` |
| 通信异常 | 通信无效、通信异常、异常计数增加 | `fragments/scene07-communication-anomaly.md` | `scripts/comm_anomaly.py` |

## 执行流程

1. 判断用户问题是否属于本技能范围。
2. 检查卫星名称、时间范围、参数信息是否齐全；缺失则追问，不调用脚本。
3. 读取公共分片：`global-rules.md`、`list-params-step.md`、`output-rules.md`。
4. 执行 `scripts/list_params.py --json '{}'` 获取全库参数列表。
5. 若用户只询问参数发现，按输出规则返回参数列表，结束。
6. 按场景匹配优先级选择唯一场景分片。
7. 读取对应场景分片，按分片要求构造 JSON 并调用强制脚本。
8. 若脚本返回 `status=error`，返回脚本错误信息。
9. 若脚本返回空数据，按 `fragments/output-rules.md` 只回复`无数据`。
10. 若脚本返回 `data` 非空，按场景分片的 `展示规则` 输出统计表和明细表。

## 参数匹配失败规则

执行 `scripts/list_params.py --json '{}'` 后，必须用返回结果匹配用户指定的参数名称或代码。

若参数无法匹配：

- 不调用场景脚本。
- 返回“未找到参数：XXX”。
- 如存在相似参数名，可列出最多 10 个候选项。

## 命名规范

- 技能名称使用小写英文和连字符，例如 `satellite-telemetry-analyzer`。
- 分片文件使用小写英文和连字符。
- 场景分片使用 `sceneNN-topic-name.md`，例如 `scene06-temperature-code-range.md`。
- 公共分片使用职责命名，例如 `global-rules.md`、`list-params-step.md`、`output-rules.md`。
- 现有脚本名保持兼容；未来新增脚本建议使用动作前缀，例如 `check_xxx.py`、`list_xxx.py`。
- JSON 字段统一使用：`satellites`、`start_time`、`end_time`、`metrics`、`condition`、`power_param`、`status_param`、`count_param`。
