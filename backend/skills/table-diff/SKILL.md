---
name: table-diff
description: 对比两份表格文件并先向用户展示差异摘要。用户需要比较 xlsx 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。默认流程是先解析、分析、确认规则、执行比对，然后用 Markdown 表格 + 总结展示结果；只有用户明确要求时才生成 HTML、XLSX、Markdown 或 CSV 差异报告。
---

# table-diff

## 功能描述
表格比对技能。对两份表格文件执行结构分析、主键识别、行级/单元格级差异比对，并先在对话中展示差异摘要和明细预览。支持 xlsx 和 csv 输入格式，默认读取前 1000 行，可通过 `--max-rows` 调整；增大读取行数可能影响性能，缩小读取行数可能遗漏差异。不要默认生成报告文件；只有用户看过比对结果并明确要求导出时，才生成 HTML、XLSX、Markdown 或 CSV 报告。

## 触发场景
- 用户需要比对两份表格的差异
- 用户上传了两个表格文件并要求对比
- 用户询问"这两份表有什么不同"

## 上游依赖
无。由用户上传文件触发，是独立完整的比对流程。

## 下游流转
- 默认流程终点：在对话中输出差异摘要、列级差异表、差异明细预览和结论。
- 可选报告：用户确认需要后，生成 HTML、XLSX、Markdown 或 CSV 报告文件。
- v2 扩展：用户可选择合并策略 → 流转到 **table-merger** skill。

---

## 比对流程

完整流程分为 5 个步骤，按顺序执行。Step 2 完成后必须暂停等待用户确认主键和规则；Step 4 完成后必须先向用户展示比对结果，不能自动生成报告。只有用户明确要求导出时，才执行 Step 5。

```
Step 1: 解析表格 ──→ Step 2: 结构分析与主键识别 ──→ [暂停：用户确认]
      ──→ Step 3: 执行比对 ──→ Step 4: 展示比对结果 ──→ [可选：用户要求导出]
      ──→ Step 5: 生成报告
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
- `dependency_missing` → 提示安装缺失依赖（如 `pip install openpyxl`）
- `sheet_not_found` → 提示用户重新确认 sheet 名称，并展示可用 sheet 列表

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
1. 仅在两表共有列中识别候选，跳过任一表有空值的列
2. 单列只要在一端唯一即可成为候选，基础 confidence = 0.7
3. 列名含 id/编号/号/code/key 等关键词 → confidence +0.2
4. 两表均唯一则保持 confidence；仅一端唯一则 -0.3，作为低置信候选，必须由用户确认后才能使用
5. 无高置信度单列候选时，尝试 2-3 列组合键
6. 按 confidence 降序返回 top 5 候选
7. 候选只表示“可能适合作为主键”；即使用户确认，Step 3 仍会检查重复主键，发现重复时会终止比对

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
1. 默认 `ignore_order=true`：根据 primary_key 建立两表行映射
2. `ignore_order=false`：不按主键匹配行，而是按行位置逐行比较；主键列也作为普通列参与位置敏感比较，左/右表超出的尾部行分别记为 left_only/right_only
3. 左表有右表无 → left_only；右表有左表无 → right_only
4. 两表都有 → 逐列比较：
   - ignore_columns 中的列跳过
   - 数值列 + tolerance → abs(left - right) <= tolerance 视为相同
   - case_sensitive=false → 统一转小写
   - null_equals_empty=true → null/空字符串/纯空格视为等价
5. 统计每列变更次数和变更率

**异常处理**：
- `primary_key_missing` → 回退到用户确认环节，提示重新确认主键
- `invalid_rules` → 回退到用户确认环节，提示调整规则
- `empty_data` → 提示数据为空

**比对完成后进入 Step 4：必须先展示结果摘要和明细预览，不得直接生成报告。**

---

### Step 4: 展示比对结果（对话内输出，必须执行）

**目的**：先让用户看到比对结果，而不是直接生成报告文件。

**触发条件**：Step 3 成功返回 `summary`、`diffs`、`column_diff_summary`。

**展示格式**：使用 Markdown 输出，包含 4 部分。

#### 1. 比对摘要表

```markdown
| 指标 | 数值 |
|------|------:|
| 左表行数 | <summary.total_left> |
| 右表行数 | <summary.total_right> |
| 匹配行数 | <summary.matched> |
| 值变化行 | <summary.value_changed> |
| 仅左表行 | <summary.left_only> |
| 仅右表行 | <summary.right_only> |
| 未变更行 | <summary.unchanged> |
| 变更率 | <summary.change_rate * 100>% |
```

#### 2. 列级差异表

当 `column_diff_summary` 非空时，按变更率降序展示：

```markdown
| 列名 | 变更次数 | 变更率 |
|------|---------:|-------:|
| 金额 | 45 | 5.0% |
```

如果没有单元格变化，输出：`未发现共有列的值变化。`

#### 3. 差异明细预览

最多展示前 20 条差异，避免刷屏。格式：

```markdown
| 类型 | 主键/行号 | 列名 | 左表值 | 右表值 |
|------|-----------|------|--------|--------|
| 值变化 | 订单号=ORD-042 | 金额 | 128.5 | 130.0 |
| 仅左表 | 订单号=ORD-900 | 整行 | {...} | - |
| 仅右表 | 订单号=ORD-950 | 整行 | - | {...} |
```

若差异超过 20 条，在表格后补充：`仅展示前 20 条，完整差异可生成报告查看。`

#### 4. 总结与下一步提示

必须用自然语言总结：
- 是否存在结构差异：独有列、类型不一致。
- 推荐主键和比对模式：`key_based` 或 `order_sensitive`。
- 最大变化列（如有）。
- 数据风险：重复主键、无主键、变更率过高、仅左/仅右行较多。

最后必须提示用户可选导出报告，但不要自动生成：

```markdown
如需，我可以继续生成差异比对报告。推荐格式：
1. XLSX：适合业务查看、筛选和二次处理；
2. HTML：适合浏览器查看，带颜色高亮和筛选；
3. Markdown：适合粘贴到文档/Issue/PR；
4. CSV：适合程序后续处理或导入其他系统。
你希望导出哪种格式？
```

**禁止行为**：
- 禁止在用户未要求时调用 `report.py`。
- 禁止只给报告文件而不展示摘要。
- 禁止省略主键/规则确认步骤。

---

### Step 5: 生成报告 (report.py，可选)

**目的**：将差异结果渲染为可读报告

**执行命令**：
```bash
python3 scripts/report.py <diff_file> --left-meta <left_meta_file> --right-meta <right_meta_file> --format <html|xlsx|markdown|csv> [--output <path>]
```

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| diff_file | string | 是 | Step 3 输出的差异结果 JSON 文件路径 |
| --left-meta | string | 是 | 左表 meta JSON 文件路径 |
| --right-meta | string | 是 | 右表 meta JSON 文件路径 |
| --format | string | 是 | `html`、`xlsx`/`excel`、`markdown`/`md` 或 `csv` |
| --output | string | 条件必填 | XLSX/Excel 和 CSV 格式必须指定；HTML 和 Markdown 可选，不填则 stdout |

**输入准备**：
- diff_file：Step 3 的输出 JSON 文件
- left_meta / right_meta：从 Step 1 输出中提取 meta 字段保存为独立 JSON

**代码调用**：
```python
from scripts.report import report
result = report(diff_result=diff_dict, left_meta=left_meta, right_meta=right_meta,
                format="html", output_path="report.html")
```

**支持格式与推荐场景**：

| 格式 | 扩展名 | 推荐场景 | 特点 |
|------|--------|----------|------|
| XLSX | `.xlsx` | 默认推荐，业务人员查看、筛选、二次处理 | 多 Sheet、颜色高亮、Excel 可编辑 |
| HTML | `.html` | 浏览器查看、演示、轻量分享 | 颜色高亮、可筛选、视觉友好 |
| Markdown | `.md` | 粘贴到文档、Issue、PR、聊天工具 | 纯文本、易审阅、版本控制友好 |
| CSV | `.csv` | 程序处理、导入数据库/BI 工具 | 机器可读、只导出差异明细 |

**默认推荐顺序**：XLSX → HTML → Markdown → CSV。

**报告内容**：
- XLSX：概览、值变化明细、新增行、删除行、差异聚合对比（按差异行并排展示左右值；未变更行和未变化单元格不保证包含原始完整值）。
- HTML：概览卡片、列级摘要、差异明细、筛选按钮。
- Markdown：基本信息、摘要表、列级变更摘要、差异明细、总结。
- CSV：差异明细行，字段为 `type, primary_key, row_number, column, left_value, right_value`。

**流程终点，生成报告文件后发送给用户。**

---

## 整体约束

- 文件格式：仅 .xlsx 和 .csv
- 默认读取行数：单文件前 1000 行；可通过 `--max-rows` 调整，增大读取行数可能影响性能，缩小读取行数可能遗漏差异
- 合并单元格：取左上角值，其余置空
- 公式：取计算后的值
- CSV 编码：按 `utf-8` → `gbk` → `gb2312` → `latin-1` 顺序尝试
- 默认不生成报告：必须先展示 Step 4 的对话内比对结果。
- 重复主键：必须终止比对并提示用户更换主键或清洗数据，不能覆盖重复行。
- 明细预览：对话中最多展示前 20 条差异，完整内容通过报告导出。
- 报告安全：HTML 报告必须转义表格内容，不能把单元格内容当作 HTML 执行。

## 依赖

```bash
pip install openpyxl
```

openpyxl 仅 xlsx 解析和 Excel 报告生成时需要，csv 解析和 HTML 报告无需额外依赖。
