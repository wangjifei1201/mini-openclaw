---
name: table-generator
description: 根据用户自然语言描述生成表格。用于用户要求生成、设计、整理、导出表格，或需要 Markdown 预览后生成可下载的 xlsx/xls 文件时。
---

# Table Generator

根据用户的自然语言需求生成表格，并在确认后导出为可下载的 Excel 文件。

## 核心流程

1. 解析用户需求，识别表格用途、字段、行数据、排序、分组、统计和格式要求。
2. 先生成 Markdown 表格预览，用于和用户确认需求。
3. 明确询问用户是否确认，或需要调整字段/内容/格式。
4. 用户确认后生成 Excel 文件：
   - 默认生成 `.xlsx`。
   - 只有用户明确要求 `.xls` 时才生成 `.xls`。
5. 将文件保存到 `outputs/` 目录，并返回可下载路径。

## Markdown 预览规则

- 默认输出 Markdown 表格。
- 表头应从用户需求中抽取；如果用户没有指定字段，按场景补充常见字段。
- 如果用户提供了具体数据，必须优先使用用户数据。
- 如果是模板、计划表、登记表、清单类需求，可以生成空白行或示例行。
- 如果是事实型数据且用户没有提供来源，不要编造；使用“待填写”或请用户补充。
- 预览后用一句话请用户确认，例如：
  - `请确认这个表格结构是否符合预期；确认后我会生成 xlsx 文件。`

## Excel 生成规则

确认后再生成文件，不要在首次预览时直接生成。

生成 `.xlsx` 时优先使用 Python `openpyxl`：

```python
from pathlib import Path
from openpyxl import Workbook

output_dir = Path("outputs")
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "table.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "Sheet1"

rows = [
    ["列1", "列2"],
    ["值1", "值2"],
]
for row in rows:
    ws.append(row)

wb.save(output_path)
```

如果 `openpyxl` 不可用：

- 优先检查项目依赖是否已有可用 Excel 库。
- 不要随意新增依赖；如必须新增，先说明原因。
- 可临时生成 CSV，但必须告知用户这不是最终 Excel 格式。

## 输出路径

- 文件应保存到后端 `outputs/` 目录。
- 回复用户时必须使用 Markdown 链接，并使用 `/outputs/<filename>` 形式的相对输出路径。
- 不要返回 `localhost`、IP 地址、前端地址或本地绝对路径。
- Excel 示例：`已生成文件：[下载 Excel](/outputs/table-20260521.xlsx)`。
- PDF 示例：`已生成文件：[查看 PDF](/outputs/report-20260521.pdf)`。

## 质量要求

- 表格字段名清晰、短小、可读。
- 日期、金额、数量等字段保持一致格式。
- 中文需求默认生成中文表头；英文需求默认生成英文表头。
- 不要把确认说明写入 Excel 文件，除非用户要求。
- 不要覆盖用户已有文件；文件名应包含简短主题或时间戳。

## 交互原则

- 首次响应重点是 Markdown 预览，不要过度解释。
- 用户确认后直接生成文件。
- 用户要求修改时，先更新 Markdown 预览，再等待确认。
