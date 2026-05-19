# XLS/XLSX/CSV Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add end-to-end support for `.xlsx`, `.xls`, and `.csv` table files across frontend upload selection, backend upload validation, and the `table-diff` parsing/comparison flow.

**Architecture:** Keep the existing table-diff pipeline unchanged after parsing by extending only the file intake and parser dispatch layers. `.xlsx` continues to use `openpyxl`, `.csv` keeps the current streaming parser, and `.xls` gets a dedicated `xlrd` parsing path that normalizes rows into the same `build_table_result(...)` output shape.

**Tech Stack:** Next.js/React/TypeScript, FastAPI/Python, `openpyxl`, `xlrd`, `xlwt`, `unittest`

---

## File Structure

- Modify: `frontend/src/components/chat/ChatInput.tsx`
  - Expand the browser file picker `accept` list to include `.xlsx` and `.xls`.
- Modify: `backend/api/files.py`
  - Expand backend upload extension validation to allow `.xlsx` and `.xls`.
- Modify: `backend/requirements.txt`
  - Add `.xls` read/write dependencies used by parser code and parser tests.
- Modify: `backend/skills/table-diff/scripts/parse.py`
  - Add `.xls` parser support and route `.xls/.xlsx/.csv` through a unified output structure.
- Modify: `backend/skills/table-diff/tests/test_parse.py`
  - Add failing and passing regression tests for `.xls` parsing while preserving current `.xlsx/.csv` behavior.
- Modify: `backend/skills/table-diff/SKILL.md`
  - Update documented input format support and parser error descriptions from `xlsx/csv` to `xlsx/xls/csv`.

---

### Task 1: Add parser dependencies and failing `.xls` tests

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/skills/table-diff/tests/test_parse.py`
- Test: `backend/skills/table-diff/tests/test_parse.py`

- [ ] **Step 1: Write the failing test for `.xls` row parsing**

Replace the import block and add `.xls` dependencies plus two new tests in `backend/skills/table-diff/tests/test_parse.py`:

```python
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from parse import openpyxl, parse, parse_csv, xlrd, xlwt


class ParseTests(unittest.TestCase):
    def test_csv_reads_only_max_non_empty_data_rows(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", encoding="utf-8", newline="", delete=False) as tmp:
            path = tmp.name
            tmp.write("id,name\n")
            tmp.write("1,Alice\n")
            tmp.write(",\n")
            tmp.write("2,Bob\n")
            tmp.write("3,Carol\n")

        try:
            result = parse_csv(path, max_rows=2)
        finally:
            Path(path).unlink()

        self.assertNotIn("error", result)
        self.assertEqual(result["meta"]["row_count"], 2)
        self.assertEqual([row["id"] for row in result["data"]], [1, 2])

    def test_xls_reads_only_max_non_empty_data_rows(self):
        if xlrd is None or xlwt is None:
            self.skipTest("xlrd/xlwt is not installed")

        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            path = tmp.name

        try:
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("Sheet1")
            headers = ["id", "name"]
            rows = [
                [1, "Alice"],
                ["", ""],
                [2, "Bob"],
                [3, "Carol"],
            ]
            for col_index, value in enumerate(headers):
                sheet.write(0, col_index, value)
            for row_index, row in enumerate(rows, start=1):
                for col_index, value in enumerate(row):
                    sheet.write(row_index, col_index, value)
            workbook.save(path)

            result = parse(path, max_rows=2)
        finally:
            Path(path).unlink()

        self.assertNotIn("error", result)
        self.assertEqual(result["meta"]["sheet_name"], "Sheet1")
        self.assertEqual(result["meta"]["row_count"], 2)
        self.assertEqual([row["id"] for row in result["data"]], [1.0, 2.0])

    def test_xls_returns_json_safe_values(self):
        if xlrd is None or xlwt is None:
            self.skipTest("xlrd/xlwt is not installed")

        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as tmp:
            path = tmp.name

        try:
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("Sheet1")
            sheet.write(0, 0, "id")
            sheet.write(0, 1, "created_at")
            sheet.write(1, 0, 1)
            sheet.write(1, 1, "2024-01-02 03:04:05")
            workbook.save(path)

            result = parse(path, max_rows=1)
            json.dumps(result)
        finally:
            Path(path).unlink()

        self.assertNotIn("error", result)
        self.assertEqual(result["data"][0]["created_at"], "2024-01-02 03:04:05")
        self.assertEqual(result["meta"]["columns"][1]["sample_values"], ["2024-01-02 03:04:05"])

    def test_xlsx_returns_json_safe_values(self):
        if openpyxl is None:
            self.skipTest("openpyxl is not installed")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            ws.append(["id", "created_at"])
            ws.append([1, datetime(2024, 1, 2, 3, 4, 5)])
            wb.save(path)
            wb.close()

            result = parse(path, max_rows=1)
            json.dumps(result)
        finally:
            Path(path).unlink()

        self.assertNotIn("error", result)
        self.assertEqual(result["data"][0]["created_at"], "2024-01-02T03:04:05")
        self.assertEqual(result["meta"]["columns"][1]["sample_values"], ["2024-01-02T03:04:05"])

    def test_xlsx_skips_empty_rows_before_applying_max_rows(self):
        if openpyxl is None:
            self.skipTest("openpyxl is not installed")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            path = tmp.name

        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["id", "name"])
            ws.append([1, "Alice"])
            ws.append([None, None])
            ws.append([2, "Bob"])
            ws.append([3, "Carol"])
            wb.save(path)
            wb.close()

            result = parse(path, max_rows=2)
        finally:
            Path(path).unlink()

        self.assertNotIn("error", result)
        self.assertEqual(result["meta"]["row_count"], 2)
        self.assertEqual([row["id"] for row in result["data"]], [1, 2])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Add missing dependencies required by the failing tests**

Append these lines to `backend/requirements.txt` under the existing tool dependencies section:

```txt
openpyxl>=3.1.0
xlrd>=2.0.1
xlwt>=1.3.0
```

- [ ] **Step 3: Run the parser tests to verify the new `.xls` test fails first**

Run: `python3 -m unittest backend/skills/table-diff/tests/test_parse.py -v`
Expected: FAIL in `test_xls_reads_only_max_non_empty_data_rows` and/or `test_xls_returns_json_safe_values` because `parse.py` does not yet export `xlrd`/`xlwt` or support `.xls` dispatch.

- [ ] **Step 4: Commit the red test setup**

```bash
git add backend/requirements.txt backend/skills/table-diff/tests/test_parse.py
git commit -m "test: add xls parser coverage"
```

---

### Task 2: Implement `.xls` parsing in `parse.py`

**Files:**
- Modify: `backend/skills/table-diff/scripts/parse.py`
- Test: `backend/skills/table-diff/tests/test_parse.py`

- [ ] **Step 1: Add `xlrd`/`xlwt` optional imports and update the supported-format docstring**

Update the top of `backend/skills/table-diff/scripts/parse.py` to this shape:

```python
#!/usr/bin/env python3
"""
file-parser: 解析表格文件，提取结构元信息和数据内容
支持格式：.xlsx, .xls, .csv
"""

import csv
import json
import os
import sys
from datetime import date, datetime, time
from pathlib import Path

try:
    import openpyxl
except ImportError:
    openpyxl = None

try:
    import xlrd
except ImportError:
    xlrd = None

try:
    import xlwt
except ImportError:
    xlwt = None
```

- [ ] **Step 2: Write the minimal `.xls` parser implementation**

Insert this function below `parse_xlsx(...)` and before `parse_csv(...)`:

```python
def parse_xls(file_path: str, sheet_name: str = None, max_rows: int = 1000) -> dict:
    """解析 .xls 文件"""
    if xlrd is None:
        return {"error": "dependency_missing", "message": "xlrd 未安装，请执行 pip install xlrd"}

    workbook = xlrd.open_workbook(file_path)

    if workbook.nsheets == 0:
        return {"error": "empty_file", "message": "文件内容为空"}

    sheet_names = workbook.sheet_names()
    if sheet_name:
        if sheet_name not in sheet_names:
            return {"error": "sheet_not_found", "message": f"Sheet '{sheet_name}' 不存在", "available_sheets": sheet_names}
        worksheet = workbook.sheet_by_name(sheet_name)
    else:
        worksheet = workbook.sheet_by_index(0)
        sheet_name = worksheet.name

    if worksheet.nrows == 0:
        return {"error": "empty_file", "message": "文件内容为空"}

    header_row = worksheet.row_values(0)
    headers = [str(h).strip() if str(h).strip() else f"column_{i}" for i, h in enumerate(header_row)]

    data_rows = []
    for row_index in range(1, worksheet.nrows):
        row = worksheet.row_values(row_index)
        if not any(str(value).strip() for value in row if value not in (None, "")):
            continue
        data_rows.append(tuple(serialize_cell_value(value) if value != "" else None for value in row))
        if len(data_rows) >= max_rows:
            break

    return build_table_result(file_path, sheet_name, headers, data_rows)
```

- [ ] **Step 3: Extend the parser dispatch to route `.xls` files**

Replace the `parse(...)` dispatcher with:

```python
def parse(file_path: str, sheet_name: str = None, max_rows: int = 1000) -> dict:
    """统一入口"""
    if not os.path.exists(file_path):
        return {"error": "file_not_found", "message": f"文件不存在: {file_path}"}

    ext = Path(file_path).suffix.lower()
    if ext == ".xlsx":
        return parse_xlsx(file_path, sheet_name, max_rows)
    elif ext == ".xls":
        return parse_xls(file_path, sheet_name, max_rows)
    elif ext == ".csv":
        return parse_csv(file_path, max_rows)
    else:
        return {"error": "unsupported_format", "message": f"不支持的格式: {ext}，仅支持 .xlsx、.xls 和 .csv"}
```

- [ ] **Step 4: Run the parser tests to verify green**

Run: `python3 -m unittest backend/skills/table-diff/tests/test_parse.py -v`
Expected: PASS with all `.csv`, `.xlsx`, and new `.xls` parse tests green.

- [ ] **Step 5: Commit the parser implementation**

```bash
git add backend/skills/table-diff/scripts/parse.py backend/skills/table-diff/tests/test_parse.py backend/requirements.txt
git commit -m "feat: add xls support to table parser"
```

---

### Task 3: Allow `.xls/.xlsx` uploads in frontend and backend

**Files:**
- Modify: `backend/api/files.py`
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Test: `backend/api/files.py`

- [ ] **Step 1: Write the failing backend upload validation test**

Create a new test file `backend/tests/test_file_upload_validation.py` with this content:

```python
import unittest
from pathlib import Path
import sys

API_DIR = Path(__file__).resolve().parents[1] / "api"
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from api.files import validate_upload_file


class FileUploadValidationTests(unittest.TestCase):
    def test_accepts_excel_extensions(self):
        self.assertEqual(validate_upload_file("report.csv", 1024), (True, ""))
        self.assertEqual(validate_upload_file("report.xlsx", 1024), (True, ""))
        self.assertEqual(validate_upload_file("report.xls", 1024), (True, ""))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the backend validation test to verify it fails first**

Run: `python3 -m unittest backend/tests/test_file_upload_validation.py -v`
Expected: FAIL because `validate_upload_file(...)` currently rejects `.xlsx` and `.xls`.

- [ ] **Step 3: Make the minimal backend and frontend allowlist changes**

Update `backend/api/files.py` so the document extension block becomes:

```python
# 文档
".txt", ".md", ".pdf", ".csv", ".xlsx", ".xls", ".json", ".xml", ".yaml", ".yml",
```

Update the hidden file input in `frontend/src/components/chat/ChatInput.tsx` to:

```tsx
<input
  ref={fileInputRef}
  type="file"
  multiple
  accept=".jpg,.jpeg,.png,.gif,.webp,.svg,.bmp,.txt,.md,.pdf,.csv,.xlsx,.xls,.json,.xml,.yaml,.yml,.py,.js,.ts,.tsx,.jsx,.html,.css,.log,.sql,.sh"
  onChange={handleFileSelect}
  className="hidden"
/>
```

- [ ] **Step 4: Re-run the backend validation test and frontend build verification**

Run: `python3 -m unittest backend/tests/test_file_upload_validation.py -v`
Expected: PASS

Run: `npm run build`
Working directory: `frontend`
Expected: PASS

- [ ] **Step 5: Commit the intake-layer changes**

```bash
git add backend/api/files.py backend/tests/test_file_upload_validation.py frontend/src/components/chat/ChatInput.tsx
git commit -m "feat: allow xls and xlsx uploads"
```

---

### Task 4: Update skill documentation and run final verification

**Files:**
- Modify: `backend/skills/table-diff/SKILL.md`
- Test: `backend/skills/table-diff/tests/test_parse.py`
- Test: `backend/tests/test_file_upload_validation.py`

- [ ] **Step 1: Update the skill description and parser error docs**

Make these exact doc updates in `backend/skills/table-diff/SKILL.md`:

1. Frontmatter description line:
```md
description: 对比两份表格文件并先向用户展示差异摘要。用户需要比较 xlsx、xls 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。默认流程是先解析、分析、确认规则、执行比对，然后用 Markdown 表格 + 总结展示结果；只有用户明确要求时才生成 HTML、XLSX、Markdown 或 CSV 差异报告。
```

2. 功能描述中的支持格式句子改为:
```md
表格比对技能。对两份表格文件执行结构分析、主键识别、行级/单元格级差异比对，并先在对话中展示差异摘要和明细预览。支持 xlsx、xls 和 csv 输入格式，默认读取前 1000 行，可通过 `--max-rows` 调整；增大读取行数可能影响性能，缩小读取行数可能遗漏差异。不要默认生成报告文件；只有用户看过比对结果并明确要求导出时，才生成 HTML、XLSX、Markdown 或 CSV 报告。
```

3. Step 1 code call example改为:
```python
from scripts.parse import parse
result = parse(file_path="xxx.xls", sheet_name="Sheet1", max_rows=1000)
```

4. Step 1 异常处理中的 unsupported_format 改为:
```md
- `unsupported_format` → 提示仅支持 xlsx/xls/csv
```

- [ ] **Step 2: Run the full targeted verification suite**

Run: `python3 -m unittest backend/skills/table-diff/tests/test_parse.py backend/tests/test_file_upload_validation.py -v`
Expected: PASS with 0 failures.

Run: `npm run build`
Working directory: `frontend`
Expected: PASS

- [ ] **Step 3: Re-read changed files and confirm spec coverage manually**

Check these files and confirm the final state matches the goal:
- `frontend/src/components/chat/ChatInput.tsx`
- `backend/api/files.py`
- `backend/skills/table-diff/scripts/parse.py`
- `backend/skills/table-diff/SKILL.md`
- `backend/skills/table-diff/tests/test_parse.py`
- `backend/tests/test_file_upload_validation.py`
- `backend/requirements.txt`

Expected confirmation:
- frontend accepts `.xlsx/.xls/.csv`
- backend upload validation accepts `.xlsx/.xls/.csv`
- parser dispatch supports `.xlsx/.xls/.csv`
- docs no longer claim only `.xlsx/.csv`
- targeted tests and frontend build are green

- [ ] **Step 4: Commit the documentation and verification pass**

```bash
git add backend/skills/table-diff/SKILL.md backend/skills/table-diff/scripts/parse.py backend/skills/table-diff/tests/test_parse.py backend/tests/test_file_upload_validation.py backend/requirements.txt frontend/src/components/chat/ChatInput.tsx backend/api/files.py
git commit -m "docs: align table diff docs with xls support"
```

---

## Self-Review

- Spec coverage: covered frontend accept list, backend upload whitelist, `.xls` parser support, dependency handling, tests, and skill-doc updates.
- Placeholder scan: no `TODO`/`TBD` placeholders remain; each task includes concrete code and exact commands.
- Type consistency: the plan consistently uses `parse_xls(...)`, `parse(...)`, `validate_upload_file(...)`, and the `.xlsx/.xls/.csv` support set across all tasks.
