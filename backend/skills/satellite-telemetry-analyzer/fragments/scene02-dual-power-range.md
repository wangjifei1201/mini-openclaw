# 场景02：双通电条件下的范围判断

## 触发条件

用户要求在 A 和 B 均通电的情况下，检查 C 是否控制在 X-Y 范围内。

典型问题：

- “高分07C01星20250730全天，在成像处理箱通断和焦面通断均通电的情况下，负载电流是否控制在2.50-4.25A之间？”

## 参数提取规则

- `satellites`：标准化后的卫星名称数组。
- `start_time`、`end_time`：左闭右开时间范围。
- `power1_param`：第一个通断参数名。
- `power2_param`：第二个通断参数名。
- `target_param`：目标参数名。
- `low_threshold`：下限。
- `high_threshold`：上限。
- `power_on_value`：通电状态值（通电/断电），默认 `通电`。

## 规则

- A、B 必须是通断参数。
- C 是被检查的目标参数。
- 范围 X-Y 直接解析为下限和上限。

## 强制脚本

必须调用 `scripts/dual_power_range.py`。

## JSON 参数格式

```json
{
  "satellites": ["高分07C01星"],
  "start_time": "2025-07-30 00:00:00",
  "end_time": "2025-07-31 00:00:00",
  "power1_param": "成像处理箱通断",
  "power2_param": "焦面通断",
  "target_param": "负载电流",
  "low_threshold": 2.5,
  "high_threshold": 4.25,
  "power_on_value": "通电"
}
```

## 调用示例

```bash
python scripts/dual_power_range.py --json '{"satellites":["高分07C01星"],"start_time":"2025-07-30 00:00:00","end_time":"2025-07-31 00:00:00","power1_param":"成像处理箱通断","power2_param":"焦面通断","target_param":"负载电流","low_threshold":2.50,"high_threshold":4.25,"power_on_value":"通电"}'
```

## 返回数据样例

```json
{
  "status": "success",
  "data": [
    {
      "卫星名称": "高分07C01星",
      "遥测参数名称": "负载电流",
      "遥测参数代码": "PD-C083",
      "系统接收时间": "2025-07-30 18:15:13.707",
      "工程值": "2.53079705"
    }
  ]
}
```

## 展示规则

有异常数据时，先输出统计表：

| 卫星名称 | 通电条件 | 检查对象 | 异常数量 |
|---|---|---|---|

- `通电条件` 使用 `power1_param + "、" + power2_param + "均通电"`。
- `检查对象` 使用 `target_param`。
- 统计维度为 `卫星名称 + 通电条件 + 检查对象`。
- 多卫星查询时，统计表必须覆盖全部请求卫星。
- 无异常的卫星显示 `0`。

然后输出异常明细表，字段使用脚本返回字段，第一列必须为“卫星名称”。

## 注意事项

- 仅当存在两个通断条件时使用本场景。
- 单个通电条件的阈值判断应使用 `scene01-threshold.md` 并构造 `extra_conditions`，除非用户明确描述通信异常。
- 不输出总结、趋势分析、建议或异常原因推断
