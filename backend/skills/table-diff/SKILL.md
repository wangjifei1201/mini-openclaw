---
name: table-diff
description: 对比两份表格文件并生成差异报告。用户需要比较 xlsx 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。支持解析表格、结构分析、主键候选推荐、用户确认规则后执行比对，并输出 HTML 或 Excel 报告。
---

# table-diff

## 功能描述
表格比对技能。对两份表格文件执行结构分析、主键识别、行级/单元格级差异比对，并生成差异报告。支持 xlsx 和 csv 格式，1000 行以内。

## 触发场景
- 用户需要比对两份表格的差异
- 用户上传了两个表格文件并要求对比
- 用户询问"这两份表有什么不同"

## 上游依赖
无。由用户上传文件触发，是独立完整的比对流程。

## 下游流转
- 流程终点：输出差异报告文件发送给用户
- v2 扩展：用户可选择合并策略 → 流转到 **table-merger** skill

---

## 比对流程

完整流程分为 4 个步骤，按顺序执行。Step 2 完成后**必须暂停等待用户确认**，其余步骤自动流转。

```
Step 1: 解析表格 ──→ Step 2: 结构分析与主键识别 ──→ [暂停：用户确认] ──→ Step 3: 执行比对 ──→ Step 4: 生成报告
```

---

### Step 1: 解析表格 (parse.py)

**目的**：将两份表格文件解析为统一的 JSON 中间格式

**执行命令**（并行调用两次）：
```bash
python3 scripts/parse.py <file_path> [--sheet <name>] [--max-rows <n>] [--output <path>]
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | 是 | 文件路径 |
| --sheet | string | 否 | 指定 sheet，默认第一个 |
| --max-rows | int | 否 | 最大读取行数，默认 1000 |
| --output | string | 否 | 输出文件路径，不指定则 stdout |

**输出格式**：
```json
{
  "meta": {
    "source_file": "订单表.xlsx",
    "sheet_name": "Sheet1",
    "row_count": 856,
    "col_count": 12,
    "columns": [
      {"name": "订单号", "index": 0, "dtype": "string", "null_count": 0, "unique_count": 856, "sample_values": ["ORD-001"]}
    ]
  },
  "data": [
    {"订单号": "ORD-001", "金额": 128.5}
  ]
}
```

**代码调用**：
```python
from scripts.parse import parse
result = parse(file_path="xxx.xlsx", sheet_name="Sheet1", max_rows=1000)
```

**异常处理**：
- `file_not_found` → 提示用户重新上传
- `unsupported_format` → 提示仅支持 xlsx/csv
- `empty_file` → 提示文件为空

**通过条件**：两次调用均返回含 `meta` + `data` 的结果，保存为 `left_table` 和 `right_table`

---

### Step 2: 结构分析与主键识别 (analyze.py)

**目的**：对比两表结构，自动识别主键候选，输出比对建议

**执行命令**：
```bash
python3 scripts/analyze.py <left_file> <right_file> [--output <path>]
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| left_file | string | 是 | Step 1 输出的左表 JSON 文件路径 |
| right_file | string | 是 | Step 1 输出的右表 JSON 文件路径 |
| --output | string | 否 | 输出文件路径 |

**输入准备**：将 Step 1 的输出保存为 JSON 文件后传入

**输出格式**：
```json
{
  "structure_diff": {
    "common_columns": ["订单号", "金额", "状态"],
    "left_only_columns": ["备注"],
    "right_only_columns": ["负责人"],
    "type_mismatch": [{"column": "金额", "left_type": "float", "right_type": "string"}],
    "row_count": {"left": 856, "right": 903}
  },
  "primary_key_candidates": [
    {"columns": ["订单号"], "confidence": 0.95, "reason": "单列唯一，列名含关键词，两表均有此列"}
  ],
  "suggestion": {
    "recommended_key": ["订单号"],
    "recommended_rules": {
      "primary_key": ["订单号"],
      "ignore_columns": ["负责人"],
      "tolerance": {},
      "case_sensitive": false,
      "null_equals_empty": true,
      "ignore_order": true
    },
    "warnings": ["右表多出列：负责人，比对时将被忽略"]
  }
}
```

**代码调用**：
```python
from scripts.analyze import analyze
result = analyze(left_table=left_dict, right_table=right_dict)
```

**主键识别算法**：
1. 过滤有空值的列和两表非共有的列
2. 检测 unique_count == row_count 的唯一列，基础 confidence = 0.7
3. 列名含 id/编号/号/code/key 等关键词 → confidence +0.2
4. 两表均唯一则保持 confidence，仅一端唯一则 -0.3
5. 无高置信度单列候选时，尝试 2-3 列组合键
6. 按 confidence 降序返回 top 5 候选

**⚠️ 必须暂停：向用户展示分析结果，等待确认主键和比对规则**

**展示给用户的内容**：
1. 结构差异摘要（共有列、各自独有列、行数差异、类型不一致）
2. 主键候选列表及置信度
3. 推荐的主键和规则

**用户确认后产出**：`confirmed_rules` JSON，以 suggestion.recommended_rules 为基础，合并用户调整

**异常处理**：
- `no_common_columns` → 终止流程，提示用户两表无共有列

---

### Step 3: 执行比对 (diff.py)

**目的**：根据确认的主键和规则，执行行级和单元格级比对

**触发条件**：用户已确认主键和规则

**执行命令**：
```bash
python3 scripts/diff.py <left_file> <right_file> --rules <rules_file> [--output <path>]
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| left_file | string | 是 | Step 1 输出的左表 JSON 文件路径 |
| right_file | string | 是 | Step 1 输出的右表 JSON 文件路径 |
| --rules | string | 是 | 比对规则 JSON 文件路径 |
| --output | string | 否 | 输出文件路径 |

**输入准备**：
- left_file / right_file：Step 1 的输出 JSON 文件
- rules_file：用户确认后的比对规则 JSON 文件

**比对规则格式**：
```json
{
  "primary_key": ["订单号"],
  "ignore_columns": ["备注"],
  "tolerance": {"金额": 0.01},
  "case_sensitive": false,
  "null_equals_empty": true,
  "ignore_order": true
}
```

**输出格式**：
```json
{
  "summary": {
    "total_left": 856,
    "total_right": 903,
    "matched": 800,
    "left_only": 56,
    "right_only": 103,
    "value_changed": 120,
    "unchanged": 680,
    "change_rate": 0.15
  },
  "diffs": [
    {"type": "value_changed", "primary_key": {"订单号": "ORD-042"}, "changes": [{"column": "金额", "left_value": 128.5, "right_value": 130.0}]},
    {"type": "left_only", "primary_key": {"订单号": "ORD-900"}, "row_data": {"订单号": "ORD-900", "金额": 500}},
    {"type": "right_only", "primary_key": {"订单号": "ORD-950"}, "row_data": {"订单号": "ORD-950", "金额": 750}}
  ],
  "column_diff_summary": {
    "金额": {"changed_count": 45, "change_rate": 0.05}
  }
}
```

**代码调用**：
```python
from scripts.diff import diff
result = diff(left_table=left_dict, right_table=right_dict, rules=rules_dict)
```

**比对逻辑**：
1. 根据 primary_key 建立两表行映射
2. 左表有右表无 → left_only；右表有左表无 → right_only
3. 两表都有 → 逐列比较：
   - ignore_columns 中的列跳过
   - 数值列 + tolerance → abs(left - right) <= tolerance 视为相同
   - case_sensitive=false → 统一转小写
   - null_equals_empty=true → null/空字符串/纯空格视为等价
4. 统计每列变更次数和变更率

**异常处理**：
- `primary_key_missing` → 回退到用户确认环节，提示重新确认主键
- `invalid_rules` → 回退到用户确认环节，提示调整规则
- `empty_data` → 提示数据为空

**无需暂停，比对完自动进入 Step 4**

---

### Step 4: 生成报告 (report.py)

**目的**：将差异结果渲染为可读报告

**执行命令**：
```bash
python3 scripts/report.py <diff_file> --left-meta <left_meta_file> --right-meta <right_meta_file> --format <html|excel> [--output <path>]
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| diff_file | string | 是 | Step 3 输出的差异结果 JSON 文件路径 |
| --left-meta | string | 是 | 左表 meta JSON 文件路径 |
| --right-meta | string | 是 | 右表 meta JSON 文件路径 |
| --format | string | 是 | "html" 或 "excel" |
| --output | string | 条件必填 | Excel 格式必填；HTML 可选，不填则 stdout |

**输入准备**：
- diff_file：Step 3 的输出 JSON 文件
- left_meta / right_meta：从 Step 1 输出中提取 meta 字段保存为独立 JSON

**代码调用**：
```python
from scripts.report import report
result = report(diff_result=diff_dict, left_meta=left_meta, right_meta=right_meta,
                format="html", output_path="report.html")
```

**报告内容**：

HTML 格式：
1. 概览卡片：变更统计、变更率
2. 列级摘要：每列变更次数和变更率
3. 差异明细表：左右并排，值变化单元格高亮（红=旧值，绿=新值）
4. 筛选按钮：按差异类型筛选

Excel 格式：
- Sheet1「概览」：统计摘要 + 列级变更率
- Sheet2「值变化明细」：主键 | 列名 | 旧值 | 新值
- Sheet3「新增行」：右表独有行
- Sheet4「删除行」：左表独有行
- Sheet5「完整对比」：左右并排，差异单元格标色

**流程终点，生成报告文件后发送给用户**

---

## 整体约束

- 文件格式：仅 .xlsx 和 .csv
- 规模上限：单文件 1000 行
- 合并单元格：取左上角值，其余置空
- 公式：取计算后的值
- CSV 编码：UTF-8 优先，失败回退 GBK

## 依赖

```bash
pip install openpyxl
```

openpyxl 仅 xlsx 解析和 Excel 报告生成时需要，csv 解析和 HTML 报告无需额外依赖。
