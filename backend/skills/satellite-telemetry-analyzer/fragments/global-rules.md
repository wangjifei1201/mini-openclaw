# 全局规则

## 卫星名称标准化

必须先从用户问题中提取卫星名称，再执行标准化：

1. 删除卫星名称中的所有空格，包括首尾空格和中间空格。
2. 使用删除空格后的字符串匹配标准名称。
3. 只允许以下标准名称：高分07B01星、高分07C01星、高分07D01星。

| 删除空格后的用户输入 | 标准名称 |
|---|---|
| 高分07B01、高分07B01星、GF07B01、07B01 | 高分07B01星 |
| 高分07C01、高分07C01星、GF07C01、07C01 | 高分07C01星 |
| 高分07D01、高分07D01星、GF07D01、07D01 | 高分07D01星 |

示例：

- `高分 07B01 星` → `高分07B01星`
- `高 分 07 B 01 星` → `高分07B01星`
- `07B01` → `高分07B01星`

如果删除空格后的卫星名称不在上述三种之内，回复：

> 未知卫星型号，支持的卫星有：高分07B01星、高分07C01星、高分07D01星。

## 时间解析规则

所有时间范围采用左闭右开 `[start_time, end_time)`。

| 用户表达 | 解析规则 |
|---|---|
| `YYYYMMDD全天` | `start_time=YYYY-MM-DD 00:00:00`，`end_time=次日 00:00:00` |
| `YYYYMMDDHHMMSS-YYYYMMDDHHMMSS` | 分别解析为起止时间 |
| `YYYY-MM-DD HH:MM:SS 到 YYYY-MM-DD HH:MM:SS` | 直接使用起止时间 |
| 同日省略日期的结束时间 | 使用开始时间的年月日补全 |

缺少时间范围时必须追问，不得默认全天。

## 数值解析规则

- `Y±Z`：计算 `min=Y-Z`、`max=Y+Z`，保留原始精度，不得自行四舍五入。
- `X-Y`、`X~Y`、`X到Y`、`X至Y`：解析为 `min=X`、`max=Y`。
- `低于X`、`小于X`、`<X`：使用 `operator="<"`、`value=X`。
- `高于X`、`大于X`、`>X`：使用 `operator=">"`、`value=X`。
- `等于X`、`=X`：使用 `operator="=="`、`value=X`。
- 单位只用于理解语义，构造 JSON 时数值字段只保留数字。

## 强制脚本清单

必须使用以下预定义脚本，不得自行查询数据库或编写临时代码替代：

| 脚本 | 用途 |
|---|---|
| `scripts/list_params.py` | 获取参数列表 |
| `scripts/query_range.py` | 单参数、多参数阈值和温度代码范围判断 |
| `scripts/dual_power_range.py` | 双通电条件下的范围判断 |
| `scripts/second_check.py` | 秒递增检查 |
| `scripts/log_growth.py` | LOG增长分析 |
| `scripts/flywheel_jump.py` | 飞轮转速跳变 |
| `scripts/comm_anomaly.py` | 通信异常检测 |

## JSON 字段规范

- 卫星数组：`satellites`
- 起始时间：`start_time`
- 结束时间：`end_time`
- 单参数：`metric`，仅在脚本明确支持时使用
- 多参数：`metrics`
- 判断条件：`condition`
- 附加条件：`extra_conditions`
- 通断参数：`power_param`、`power1_param`、`power2_param`
- 通信状态参数：`status_param`
- 异常计数参数：`count_param`
