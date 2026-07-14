# 场景06：温度代码范围判断

## 触发条件

用户给出温度参数代码范围，并给出温度条件。

典型问题：

- “高分07D01星20250819230000-20250820050000，WD-C001——WD-C015温度值是否都满足20±0.05？”
- “高分07B01星20250819全天，WD-C001到WD-C015的温度是否在19.95到20.05之间？”

## 参数提取规则

- `satellites`：标准化后的卫星名称数组。
- `start_time`、`end_time`：左闭右开时间范围。
- `metrics`：展开后的代码对象数组，每个元素为 `{"type":"code","value":"WD-C001"}`。
- `condition`：温度范围条件。
- `extra_conditions`：通常为空数组 `[]`。

## 标准化规则

- `WD-C001——WD-C015`、`WD-C001到WD-C015`、`WD-C001-WD-C015` 必须展开为连续代码列表。
- `20±0.05` 必须计算为 `min=19.95`、`max=20.05`。
- 不得自行四舍五入或修改阈值。

## 强制脚本

必须调用 `scripts/query_range.py`。

## JSON 参数格式

```json
{
  "satellites": ["高分07D01星"],
  "start_time": "2025-08-19 23:00:00",
  "end_time": "2025-08-20 05:00:00",
  "metrics": [
    {"type": "code", "value": "WD-C001"},
    {"type": "code", "value": "WD-C002"},
    {"type": "code", "value": "WD-C003"},
    {"type": "code", "value": "WD-C004"},
    {"type": "code", "value": "WD-C005"},
    {"type": "code", "value": "WD-C006"},
    {"type": "code", "value": "WD-C007"},
    {"type": "code", "value": "WD-C008"},
    {"type": "code", "value": "WD-C009"},
    {"type": "code", "value": "WD-C010"},
    {"type": "code", "value": "WD-C011"},
    {"type": "code", "value": "WD-C012"},
    {"type": "code", "value": "WD-C013"},
    {"type": "code", "value": "WD-C014"},
    {"type": "code", "value": "WD-C015"}
  ],
  "condition": {"operator": "between", "min": 19.95, "max": 20.05},
  "extra_conditions": []
}
```

## 调用示例

```bash
python scripts/query_range.py --json '{"satellites":["高分07D01星"],"start_time":"2025-08-19 23:00:00","end_time":"2025-08-20 05:00:00","metrics":[{"type":"code","value":"WD-C001"},{"type":"code","value":"WD-C002"},{"type":"code","value":"WD-C003"},{"type":"code","value":"WD-C004"},{"type":"code","value":"WD-C005"},{"type":"code","value":"WD-C006"},{"type":"code","value":"WD-C007"},{"type":"code","value":"WD-C008"},{"type":"code","value":"WD-C009"},{"type":"code","value":"WD-C010"},{"type":"code","value":"WD-C011"},{"type":"code","value":"WD-C012"},{"type":"code","value":"WD-C013"},{"type":"code","value":"WD-C014"},{"type":"code","value":"WD-C015"}],"condition":{"operator":"between","min":19.95,"max":20.05},"extra_conditions":[]}'
```

## 返回数据样例

```json
{
  "status": "success",
  "data": [
    {
      "卫星名称": "高分07D01星",
      "遥测参数名称": "温度值",
      "遥测参数代码": "WD-C001",
      "系统接收时间": "2025-08-20 00:15:00.000",
      "工程值": "20.08"
    }
  ]
}
```

## 展示规则

有温度异常数据时，先输出统计表：

| 卫星名称 | 温度代码 | 异常数量 |
|---|---|---|

- `温度代码` 使用展开后的遥测参数代码，例如 `WD-C001`。
- 统计维度为 `卫星名称 + 温度代码`。
- 多卫星或多温度代码查询时，统计表必须覆盖全部请求组合。
- 无异常的组合显示 `0`。

然后输出异常明细表，字段使用脚本返回字段，第一列必须为“卫星名称”。

## 注意事项

- 本场景的强制脚本是 `scripts/query_range.py`，不是 `scripts/flywheel_jump.py`。
- 代码范围必须展开，不得在真实调用 JSON 中使用省略号。
- 不输出总结、趋势分析、建议或异常原因推断
