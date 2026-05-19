# Table Diff Full Report System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `backend/skills/table-diff` into a rigorous compare-first workflow that previews differences in chat before optional report generation, while adding safer diff/report logic and broader report export formats.

**Architecture:** Keep the existing skill layout and Python scripts. Strengthen the core diff engine first, then add report renderers for `html`, `xlsx`, `markdown`, and `csv`, then update `SKILL.md` so agents compare and summarize first and only generate report files after the user asks.

**Tech Stack:** Python 3 standard library (`json`, `csv`, `html`, `argparse`, `tempfile`, `unittest`), optional `openpyxl` for `.xlsx` parsing/report generation, Markdown skill instructions.

---

## File Structure

- Modify: `backend/skills/table-diff/SKILL.md`
  - Documents the corrected workflow: parse, analyze, confirm rules, run diff, present Markdown summary/table preview, then ask whether to generate a report.
  - Lists supported report formats and recommendations.
- Modify: `backend/skills/table-diff/scripts/diff.py`
  - Adds duplicate primary-key detection.
  - Implements deterministic ordering for diff output.
  - Implements `ignore_order=false` row-position comparison as a distinct supported mode.
  - Adds compare metadata for report generation.
- Modify: `backend/skills/table-diff/scripts/report.py`
  - Escapes HTML output.
  - Adds Markdown report rendering.
  - Adds CSV export rendering.
  - Keeps existing HTML/XLSX behavior.
- Create: `backend/skills/table-diff/tests/test_diff.py`
  - Unit tests for duplicate primary keys, deterministic output, null/string/number comparison, and order-sensitive comparison.
- Create: `backend/skills/table-diff/tests/test_report.py`
  - Unit tests for HTML escaping, Markdown rendering, and CSV rendering.
- Create: `backend/skills/table-diff/tests/__init__.py`
  - Makes the test folder importable.

---

### Task 1: Add diff engine tests

**Files:**
- Create: `backend/skills/table-diff/tests/__init__.py`
- Create: `backend/skills/table-diff/tests/test_diff.py`
- Modify: none

- [ ] **Step 1: Create empty test package marker**

Create `backend/skills/table-diff/tests/__init__.py` with empty content.

- [ ] **Step 2: Write failing tests for duplicate primary keys and stable sorted output**

Create `backend/skills/table-diff/tests/test_diff.py` with:

```python
import unittest
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from diff import diff


def table(rows, columns=None):
    if columns is None:
        names = list(rows[0].keys()) if rows else ["id", "name", "amount"]
    else:
        names = columns
    return {
        "meta": {
            "source_file": "test.csv",
            "sheet_name": None,
            "row_count": len(rows),
            "col_count": len(names),
            "columns": [
                {"name": name, "index": i, "dtype": "integer" if name in {"id", "amount"} else "string", "null_count": 0, "unique_count": len({str(row.get(name, "")) for row in rows}), "sample_values": []}
                for i, name in enumerate(names)
            ],
        },
        "data": rows,
    }


class DiffTests(unittest.TestCase):
    def test_rejects_duplicate_primary_keys_in_left_table(self):
        left = table([
            {"id": "A", "name": "old"},
            {"id": "A", "name": "new"},
        ], ["id", "name"])
        right = table([
            {"id": "A", "name": "new"},
        ], ["id", "name"])

        result = diff(left, right, {"primary_key": ["id"]})

        self.assertEqual(result["error"], "duplicate_primary_key")
        self.assertEqual(result["side"], "left")
        self.assertEqual(result["duplicates"], [{"id": "A"}])

    def test_returns_diffs_in_stable_key_order(self):
        left = table([
            {"id": "B", "name": "same"},
            {"id": "A", "name": "old"},
            {"id": "D", "name": "left only"},
        ], ["id", "name"])
        right = table([
            {"id": "C", "name": "right only"},
            {"id": "A", "name": "new"},
            {"id": "B", "name": "same"},
        ], ["id", "name"])

        result = diff(left, right, {"primary_key": ["id"]})

        self.assertNotIn("error", result)
        self.assertEqual(
            [(item["type"], item["primary_key"]["id"]) for item in result["diffs"]],
            [("value_changed", "A"), ("right_only", "C"), ("left_only", "D")],
        )

    def test_compares_null_empty_case_and_numeric_values_by_rules(self):
        left = table([
            {"id": "1", "name": " Alice ", "note": None, "amount": 1},
        ], ["id", "name", "note", "amount"])
        right = table([
            {"id": "1", "name": "alice", "note": "", "amount": 1.0},
        ], ["id", "name", "note", "amount"])

        result = diff(left, right, {
            "primary_key": ["id"],
            "case_sensitive": False,
            "null_equals_empty": True,
        })

        self.assertEqual(result["summary"]["unchanged"], 1)
        self.assertEqual(result["diffs"], [])

    def test_order_sensitive_mode_compares_rows_by_position(self):
        left = table([
            {"id": "1", "name": "A"},
            {"id": "2", "name": "B"},
        ], ["id", "name"])
        right = table([
            {"id": "2", "name": "B"},
            {"id": "1", "name": "A"},
        ], ["id", "name"])

        result = diff(left, right, {"primary_key": ["id"], "ignore_order": False})

        self.assertEqual(result["summary"]["value_changed"], 2)
        self.assertEqual(result["comparison_mode"], "order_sensitive")
        self.assertEqual(result["diffs"][0]["row_number"], 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail before implementation**

Run:

```bash
python3 -m unittest discover -s backend/skills/table-diff/tests -p 'test_diff.py'
```

Expected: FAIL. At least `duplicate_primary_key` and `comparison_mode` assertions fail because existing `diff.py` overwrites duplicate keys and ignores `ignore_order=false`.

---

### Task 2: Implement diff engine rigor

**Files:**
- Modify: `backend/skills/table-diff/scripts/diff.py`
- Test: `backend/skills/table-diff/tests/test_diff.py`

- [ ] **Step 1: Replace `build_key_index` with duplicate-aware implementation**

In `backend/skills/table-diff/scripts/diff.py`, replace the existing `build_key_index` function with:

```python
def format_key_dict(primary_key: list, key) -> dict:
    """将内部 key 转成 {主键列: 值}。"""
    if len(primary_key) == 1:
        return {primary_key[0]: key}
    return {col: key[i] for i, col in enumerate(primary_key)}


def make_key(row: dict, primary_key: list):
    """根据主键从行数据生成稳定 key。"""
    key = tuple(str(row.get(col, "")) for col in primary_key)
    if len(primary_key) == 1:
        return key[0]
    return key


def sort_key(value):
    """对字符串/组合 key 做稳定排序。"""
    if isinstance(value, tuple):
        return tuple(str(v) for v in value)
    return (str(value),)


def build_key_index(table: dict, primary_key: list, side: str = "table") -> dict:
    """根据主键构建 key → row 的映射；发现重复主键时返回错误。"""
    index = {}
    duplicates = []
    duplicate_seen = set()

    for row in table["data"]:
        key = make_key(row, primary_key)
        if key in index:
            if key not in duplicate_seen:
                duplicates.append(format_key_dict(primary_key, key))
                duplicate_seen.add(key)
            continue
        index[key] = row

    if duplicates:
        return {
            "error": "duplicate_primary_key",
            "message": f"{side} 表存在重复主键，请更换主键或清洗数据后重试",
            "side": side,
            "duplicates": duplicates[:20],
        }

    return {"index": index}
```

- [ ] **Step 2: Add order-sensitive comparison helper before `diff`**

Add this function below `get_dtypes_map`:

```python
def diff_by_position(left: dict, right: dict, rules: dict, compare_columns: list, left_dtypes: dict, right_dtypes: dict) -> dict:
    """按行号逐行比对，用于 ignore_order=false。"""
    tolerance = rules.get("tolerance", {})
    case_sensitive = rules.get("case_sensitive", False)
    null_equals_empty = rules.get("null_equals_empty", True)
    primary_key = rules.get("primary_key", [])

    diffs = []
    column_change_counts = defaultdict(int)
    matched_count = min(len(left["data"]), len(right["data"]))
    value_changed_count = 0
    unchanged_count = 0

    for idx in range(matched_count):
        left_row = left["data"][idx]
        right_row = right["data"][idx]
        changes = []

        columns_to_check = list(primary_key) + compare_columns
        for col in columns_to_check:
            l_val = left_row.get(col)
            r_val = right_row.get(col)
            if not values_equal(
                l_val, r_val, col, tolerance,
                case_sensitive, null_equals_empty,
                left_dtypes.get(col), right_dtypes.get(col)
            ):
                changes.append({
                    "column": col,
                    "left_value": _serialize(l_val),
                    "right_value": _serialize(r_val),
                })
                column_change_counts[col] += 1

        if changes:
            diffs.append({
                "type": "value_changed",
                "row_number": idx + 1,
                "primary_key": {col: left_row.get(col) for col in primary_key},
                "changes": changes,
            })
            value_changed_count += 1
        else:
            unchanged_count += 1

    for idx in range(matched_count, len(left["data"])):
        row = left["data"][idx]
        diffs.append({
            "type": "left_only",
            "row_number": idx + 1,
            "primary_key": {col: row.get(col) for col in primary_key},
            "row_data": {k: v for k, v in row.items() if k not in primary_key},
        })

    for idx in range(matched_count, len(right["data"])):
        row = right["data"][idx]
        diffs.append({
            "type": "right_only",
            "row_number": idx + 1,
            "primary_key": {col: row.get(col) for col in primary_key},
            "row_data": {k: v for k, v in row.items() if k not in primary_key},
        })

    column_diff_summary = {}
    for col in list(primary_key) + compare_columns:
        changed = column_change_counts.get(col, 0)
        rate = round(changed / matched_count, 4) if matched_count > 0 else 0
        if changed > 0:
            column_diff_summary[col] = {
                "changed_count": changed,
                "change_rate": rate,
            }

    return {
        "comparison_mode": "order_sensitive",
        "compare_columns": compare_columns,
        "summary": {
            "total_left": len(left["data"]),
            "total_right": len(right["data"]),
            "matched": matched_count,
            "left_only": max(len(left["data"]) - matched_count, 0),
            "right_only": max(len(right["data"]) - matched_count, 0),
            "value_changed": value_changed_count,
            "unchanged": unchanged_count,
            "change_rate": round(value_changed_count / matched_count, 4) if matched_count > 0 else 0,
        },
        "diffs": diffs,
        "column_diff_summary": column_diff_summary,
    }
```

- [ ] **Step 3: Update `diff` to use duplicate detection and order-sensitive mode**

Inside `diff`, replace the index-building block:

```python
    # === 建立映射 ===
    left_index = build_key_index(left, primary_key)
    right_index = build_key_index(right, primary_key)
```

with:

```python
    if ignore_order is False:
        return diff_by_position(left, right, rules, compare_columns, left_dtypes, right_dtypes)

    # === 建立映射 ===
    left_index_result = build_key_index(left, primary_key, "left")
    if left_index_result.get("error"):
        return left_index_result
    right_index_result = build_key_index(right, primary_key, "right")
    if right_index_result.get("error"):
        return right_index_result

    left_index = left_index_result["index"]
    right_index = right_index_result["index"]
```

- [ ] **Step 4: Make unordered diff output deterministic**

Replace each key loop:

```python
    for key in left_only_keys:
```

with:

```python
    for key in sorted(left_only_keys, key=sort_key):
```

Replace:

```python
    for key in right_only_keys:
```

with:

```python
    for key in sorted(right_only_keys, key=sort_key):
```

Replace:

```python
    for key in matched_keys:
```

with:

```python
    for key in sorted(matched_keys, key=sort_key):
```

- [ ] **Step 5: Add metadata to unordered diff result**

In the return object at the end of `diff`, add two top-level keys before `summary`:

```python
        "comparison_mode": "key_based",
        "compare_columns": compare_columns,
```

- [ ] **Step 6: Run diff tests to verify they pass**

Run:

```bash
python3 -m unittest discover -s backend/skills/table-diff/tests -p 'test_diff.py'
```

Expected: PASS, 4 tests.

---

### Task 3: Add report renderer tests

**Files:**
- Create: `backend/skills/table-diff/tests/test_report.py`
- Modify: none

- [ ] **Step 1: Write failing tests for HTML escaping, Markdown, and CSV reports**

Create `backend/skills/table-diff/tests/test_report.py` with:

```python
import csv
import io
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from report import report


def diff_result():
    return {
        "comparison_mode": "key_based",
        "compare_columns": ["name", "amount"],
        "summary": {
            "total_left": 2,
            "total_right": 2,
            "matched": 1,
            "left_only": 1,
            "right_only": 1,
            "value_changed": 1,
            "unchanged": 0,
            "change_rate": 1.0,
        },
        "diffs": [
            {
                "type": "value_changed",
                "primary_key": {"id": "A<script>bad()</script>"},
                "changes": [
                    {"column": "name", "left_value": "old <b>", "right_value": "new & value"}
                ],
            },
            {
                "type": "left_only",
                "primary_key": {"id": "B"},
                "row_data": {"name": "left only", "amount": 2},
            },
            {
                "type": "right_only",
                "primary_key": {"id": "C"},
                "row_data": {"name": "right only", "amount": 3},
            },
        ],
        "column_diff_summary": {
            "name": {"changed_count": 1, "change_rate": 1.0}
        },
    }


LEFT_META = {"source_file": "left.csv", "row_count": 2}
RIGHT_META = {"source_file": "right.csv", "row_count": 2}


class ReportTests(unittest.TestCase):
    def test_html_report_escapes_cell_content(self):
        html = report(diff_result(), LEFT_META, RIGHT_META, "html")

        self.assertIn("A&lt;script&gt;bad()&lt;/script&gt;", html)
        self.assertIn("old &lt;b&gt;", html)
        self.assertIn("new &amp; value", html)
        self.assertNotIn("<script>bad()</script>", html)

    def test_markdown_report_contains_summary_and_diff_preview(self):
        markdown = report(diff_result(), LEFT_META, RIGHT_META, "markdown")

        self.assertIn("# 表格比对报告", markdown)
        self.assertIn("| 指标 | 数值 |", markdown)
        self.assertIn("| 值变化行 | 1 |", markdown)
        self.assertIn("## 差异明细", markdown)
        self.assertIn("A<script>bad()</script>", markdown)

    def test_csv_report_writes_machine_readable_rows(self):
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            output_path = report(diff_result(), LEFT_META, RIGHT_META, "csv", tmp.name)
            self.assertEqual(output_path, tmp.name)
            tmp.seek(0)
            content = tmp.read().decode("utf-8-sig")

        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(rows[0]["type"], "value_changed")
        self.assertEqual(rows[0]["primary_key"], "id=A<script>bad()</script>")
        self.assertEqual(rows[0]["column"], "name")
        self.assertEqual(rows[0]["left_value"], "old <b>")
        self.assertEqual(rows[0]["right_value"], "new & value")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run report tests to verify they fail before implementation**

Run:

```bash
python3 -m unittest discover -s backend/skills/table-diff/tests -p 'test_report.py'
```

Expected: FAIL. HTML escaping test fails because report currently interpolates values directly. Markdown and CSV tests fail because `report.py` only supports `html` and `excel`.

---

### Task 4: Implement safe and multi-format reports

**Files:**
- Modify: `backend/skills/table-diff/scripts/report.py`
- Test: `backend/skills/table-diff/tests/test_report.py`

- [ ] **Step 1: Add imports for HTML escaping and CSV**

At the top of `report.py`, add:

```python
import csv
import html
```

- [ ] **Step 2: Add safe display helpers after imports**

Add:

```python
def escape_html(value) -> str:
    """HTML 安全展示。"""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def markdown_escape(value) -> str:
    """Markdown 表格单元格安全展示。"""
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def plain_value(value) -> str:
    """CSV/文本展示。"""
    if value is None:
        return ""
    return str(value)


def primary_key_label(primary_key: dict) -> str:
    """主键字典展示为 key=value / key=value。"""
    return " / ".join(f"{k}={v}" for k, v in primary_key.items())
```

- [ ] **Step 3: Escape HTML overview and column summary values**

In `generate_overview_html`, wrap all dynamic values with `escape_html(...)`. The returned string must use this structure:

```python
    return f"""
<div class="overview">
  <div class="card"><div class="label">左表行数</div><div class="value blue">{escape_html(summary['total_left'])}</div></div>
  <div class="card"><div class="label">右表行数</div><div class="value blue">{escape_html(summary['total_right'])}</div></div>
  <div class="card"><div class="label">匹配行数</div><div class="value">{escape_html(summary['matched'])}</div></div>
  <div class="card"><div class="label">值变化行</div><div class="value accent">{escape_html(summary['value_changed'])}</div></div>
  <div class="card"><div class="label">仅左表</div><div class="value accent">{escape_html(summary['left_only'])}</div></div>
  <div class="card"><div class="label">仅右表</div><div class="value green">{escape_html(summary['right_only'])}</div></div>
  <div class="card"><div class="label">未变更行</div><div class="value">{escape_html(summary['unchanged'])}</div></div>
  <div class="card"><div class="label">变更率</div><div class="value accent">{escape_html(rate_pct)}</div></div>
</div>"""
```

In `generate_col_summary_html`, change row generation so `{col}`, `{info['changed_count']}`, and `{rate_pct}` use `escape_html(...)`.

- [ ] **Step 4: Escape HTML detail values**

Replace `_val_display` with:

```python
def _val_display(val) -> str:
    """值展示。"""
    if val is None:
        return "<em style='color:#999'>空</em>"
    return escape_html(val)
```

Update table header generation in `generate_detail_html`:

```python
    thead = "<tr>" + "".join(f"<th>{escape_html(h)}</th>" for h in headers) + "</tr>"
```

- [ ] **Step 5: Add Markdown report renderer before Excel section**

Add:

```python
def generate_markdown_report(diff_result: dict, left_meta: dict, right_meta: dict) -> str:
    """生成 Markdown 报告。"""
    summary = diff_result["summary"]
    col_diff = diff_result.get("column_diff_summary", {})
    diffs = diff_result.get("diffs", [])
    change_rate = f"{summary['change_rate'] * 100:.1f}%"

    lines = [
        "# 表格比对报告",
        "",
        "## 基本信息",
        "",
        "| 项目 | 左表 | 右表 |",
        "|---|---:|---:|",
        f"| 文件 | {markdown_escape(left_meta.get('source_file', ''))} | {markdown_escape(right_meta.get('source_file', ''))} |",
        f"| 行数 | {summary['total_left']} | {summary['total_right']} |",
        "",
        "## 摘要",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 匹配行数 | {summary['matched']} |",
        f"| 值变化行 | {summary['value_changed']} |",
        f"| 仅左表行 | {summary['left_only']} |",
        f"| 仅右表行 | {summary['right_only']} |",
        f"| 未变更行 | {summary['unchanged']} |",
        f"| 变更率 | {change_rate} |",
        "",
    ]

    if col_diff:
        lines.extend([
            "## 列级变更摘要",
            "",
            "| 列名 | 变更次数 | 变更率 |",
            "|---|---:|---:|",
        ])
        for col, info in sorted(col_diff.items(), key=lambda x: -x[1]["change_rate"]):
            lines.append(f"| {markdown_escape(col)} | {info['changed_count']} | {info['change_rate'] * 100:.1f}% |")
        lines.append("")

    lines.extend([
        "## 差异明细",
        "",
        "| 类型 | 主键 | 行号 | 列名 | 左表值 | 右表值 |",
        "|---|---|---:|---|---|---|",
    ])

    for item in diffs:
        dtype = item["type"]
        type_label = {"value_changed": "值变化", "left_only": "仅左表", "right_only": "仅右表"}.get(dtype, dtype)
        pk = markdown_escape(primary_key_label(item.get("primary_key", {})))
        row_number = item.get("row_number", "")

        if dtype == "value_changed":
            for change in item.get("changes", []):
                lines.append(
                    f"| {type_label} | {pk} | {row_number} | {markdown_escape(change['column'])} | {markdown_escape(change.get('left_value'))} | {markdown_escape(change.get('right_value'))} |"
                )
        elif dtype == "left_only":
            lines.append(f"| {type_label} | {pk} | {row_number} | 整行 | {markdown_escape(item.get('row_data', {}))} |  |")
        elif dtype == "right_only":
            lines.append(f"| {type_label} | {pk} | {row_number} | 整行 |  | {markdown_escape(item.get('row_data', {}))} |")

    lines.extend([
        "",
        "## 总结",
        "",
        f"本次比对匹配 {summary['matched']} 行，其中 {summary['value_changed']} 行存在值变化，{summary['left_only']} 行仅左表存在，{summary['right_only']} 行仅右表存在。",
    ])

    return "\n".join(lines)
```

- [ ] **Step 6: Add CSV report renderer before `report`**

Add:

```python
def generate_csv_report(diff_result: dict, output_path: str) -> str:
    """生成机器可读 CSV 明细。"""
    diffs = diff_result.get("diffs", [])
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "primary_key", "row_number", "column", "left_value", "right_value"])
        writer.writeheader()
        for item in diffs:
            dtype = item["type"]
            pk = primary_key_label(item.get("primary_key", {}))
            row_number = item.get("row_number", "")
            if dtype == "value_changed":
                for change in item.get("changes", []):
                    writer.writerow({
                        "type": dtype,
                        "primary_key": pk,
                        "row_number": row_number,
                        "column": plain_value(change.get("column")),
                        "left_value": plain_value(change.get("left_value")),
                        "right_value": plain_value(change.get("right_value")),
                    })
            elif dtype == "left_only":
                writer.writerow({
                    "type": dtype,
                    "primary_key": pk,
                    "row_number": row_number,
                    "column": "__row__",
                    "left_value": json.dumps(item.get("row_data", {}), ensure_ascii=False, default=str),
                    "right_value": "",
                })
            elif dtype == "right_only":
                writer.writerow({
                    "type": dtype,
                    "primary_key": pk,
                    "row_number": row_number,
                    "column": "__row__",
                    "left_value": "",
                    "right_value": json.dumps(item.get("row_data", {}), ensure_ascii=False, default=str),
                })
    return output_path
```

- [ ] **Step 7: Extend `report` unified entry**

In `report`, change supported formats from only `html` and `excel` to support `html`, `excel`, `xlsx`, `markdown`, `md`, and `csv`:

```python
    if format == "html":
        html_text = generate_html_report(diff_result, left_meta, right_meta)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_text)
            return output_path
        return html_text

    elif format in ("excel", "xlsx"):
        if not output_path:
            return json.dumps({"error": "output_required", "message": "Excel 格式必须指定 output_path"})
        return generate_excel_report(diff_result, left_meta, right_meta, output_path)

    elif format in ("markdown", "md"):
        markdown_text = generate_markdown_report(diff_result, left_meta, right_meta)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_text)
            return output_path
        return markdown_text

    elif format == "csv":
        if not output_path:
            return json.dumps({"error": "output_required", "message": "CSV 格式必须指定 output_path"})
        return generate_csv_report(diff_result, output_path)
```

- [ ] **Step 8: Extend CLI choices and output printing**

In CLI argparse, change:

```python
parser.add_argument("--format", choices=["html", "excel"], required=True, help="输出格式")
```

to:

```python
parser.add_argument("--format", choices=["html", "excel", "xlsx", "markdown", "md", "csv"], required=True, help="输出格式")
```

Change final print logic to:

```python
    if args.format in ("html", "markdown", "md") and not args.output:
        print(result)
    else:
        print(f"报告已生成: {result}")
```

- [ ] **Step 9: Run report tests to verify they pass**

Run:

```bash
python3 -m unittest discover -s backend/skills/table-diff/tests -p 'test_report.py'
```

Expected: PASS, 3 tests.

---

### Task 5: Update table-diff skill workflow

**Files:**
- Modify: `backend/skills/table-diff/SKILL.md`
- Test: manual grep/read review

- [ ] **Step 1: Update frontmatter description**

Replace line 3 description with:

```markdown
description: 对比两份表格文件并先向用户展示差异摘要。用户需要比较 xlsx 或 csv 表格、查找两份表的数据差异、分析表结构差异、识别主键、做行级或单元格级比对时使用。默认流程是先解析、分析、确认规则、执行比对，然后用 Markdown 表格 + 总结展示结果；只有用户明确要求时才生成 HTML、XLSX、Markdown 或 CSV 差异报告。
```

- [ ] **Step 2: Update feature description**

Replace the paragraph under `## 功能描述` with:

```markdown
表格比对技能。对两份表格文件执行结构分析、主键识别、行级/单元格级差异比对，并先在对话中展示差异摘要和明细预览。支持 xlsx 和 csv 输入格式，默认处理 1000 行以内。不要默认生成报告文件；只有用户看过比对结果并明确要求导出时，才生成 HTML、XLSX、Markdown 或 CSV 报告。
```

- [ ] **Step 3: Update downstream flow**

Replace `## 下游流转` section content with:

```markdown
## 下游流转
- 默认流程终点：在对话中输出差异摘要、列级差异表、差异明细预览和结论。
- 可选报告：用户确认需要后，生成 HTML、XLSX、Markdown 或 CSV 报告文件。
- v2 扩展：用户可选择合并策略 → 流转到 **table-merger** skill。
```

- [ ] **Step 4: Replace process overview**

Replace current `## 比对流程` intro and diagram with:

```markdown
## 比对流程

完整流程分为 5 个步骤，按顺序执行。Step 2 完成后必须暂停等待用户确认主键和规则；Step 4 完成后必须先向用户展示比对结果，不能自动生成报告。只有用户明确要求导出时，才执行 Step 5。

```
Step 1: 解析表格 ──→ Step 2: 结构分析与主键识别 ──→ [暂停：用户确认]
      ──→ Step 3: 执行比对 ──→ Step 4: 展示比对结果 ──→ [可选：用户要求导出]
      ──→ Step 5: 生成报告
```
```

- [ ] **Step 5: Update Step 3 ending**

Replace `**无需暂停，比对完自动进入 Step 4**` with:

```markdown
**比对完成后进入 Step 4：必须先展示结果摘要和明细预览，不得直接生成报告。**
```

- [ ] **Step 6: Insert new Step 4 display section before existing report section**

Insert before the current `### Step 4: 生成报告 (report.py)` heading:

```markdown
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
```

- [ ] **Step 7: Rename old Step 4 report section to Step 5 and update supported formats**

Change heading:

```markdown
### Step 4: 生成报告 (report.py)
```

to:

```markdown
### Step 5: 生成报告 (report.py，可选)
```

In its command block, change:

```bash
python3 scripts/report.py <diff_file> --left-meta <left_meta_file> --right-meta <right_meta_file> --format <html|excel> [--output <path>]
```

to:

```bash
python3 scripts/report.py <diff_file> --left-meta <left_meta_file> --right-meta <right_meta_file> --format <html|xlsx|markdown|csv> [--output <path>]
```

Update parameter description for `--format` to:

```markdown
| --format | string | 是 | `html`、`xlsx`/`excel`、`markdown`/`md` 或 `csv` |
```

- [ ] **Step 8: Replace report content section**

Replace the report content list with:

```markdown
**支持格式与推荐场景**：

| 格式 | 扩展名 | 推荐场景 | 特点 |
|------|--------|----------|------|
| XLSX | `.xlsx` | 默认推荐，业务人员查看、筛选、二次处理 | 多 Sheet、颜色高亮、Excel 可编辑 |
| HTML | `.html` | 浏览器查看、演示、轻量分享 | 颜色高亮、可筛选、视觉友好 |
| Markdown | `.md` | 粘贴到文档、Issue、PR、聊天工具 | 纯文本、易审阅、版本控制友好 |
| CSV | `.csv` | 程序处理、导入数据库/BI 工具 | 机器可读、只导出差异明细 |

**默认推荐顺序**：XLSX → HTML → Markdown → CSV。

**报告内容**：
- XLSX：概览、值变化明细、新增行、删除行、完整对比。
- HTML：概览卡片、列级摘要、差异明细、筛选按钮。
- Markdown：基本信息、摘要表、列级变更摘要、差异明细、总结。
- CSV：差异明细行，字段为 `type, primary_key, row_number, column, left_value, right_value`。

**流程终点，生成报告文件后发送给用户。**
```

- [ ] **Step 9: Update constraints**

Under `## 整体约束`, add:

```markdown
- 默认不生成报告：必须先展示 Step 4 的对话内比对结果。
- 重复主键：必须终止比对并提示用户更换主键或清洗数据，不能覆盖重复行。
- 明细预览：对话中最多展示前 20 条差异，完整内容通过报告导出。
- 报告安全：HTML 报告必须转义表格内容，不能把单元格内容当作 HTML 执行。
```

---

### Task 6: Verify all table-diff behavior

**Files:**
- Test: `backend/skills/table-diff/tests/test_diff.py`
- Test: `backend/skills/table-diff/tests/test_report.py`
- Review: `backend/skills/table-diff/SKILL.md`

- [ ] **Step 1: Run all table-diff unit tests**

Run:

```bash
python3 -m unittest discover -s backend/skills/table-diff/tests
```

Expected: PASS, 7 tests.

- [ ] **Step 2: Run CLI help for report formats**

Run:

```bash
python3 backend/skills/table-diff/scripts/report.py --help
```

Expected: help output includes `html`, `excel`, `xlsx`, `markdown`, `md`, and `csv` in `--format` choices.

- [ ] **Step 3: Search skill doc for old auto-report behavior**

Run:

```bash
grep -n "自动进入 Step 4\|流程终点：输出差异报告文件\|html|excel" backend/skills/table-diff/SKILL.md
```

Expected:
- No `自动进入 Step 4` match.
- No old `流程终点：输出差异报告文件` match.
- Any format references include the new supported set or recommendation table.

- [ ] **Step 4: Run repository diff review for changed files**

Run:

```bash
git diff -- backend/skills/table-diff
```

Expected:
- `SKILL.md` documents compare-first behavior.
- `diff.py` rejects duplicate primary keys and supports order-sensitive mode.
- `report.py` escapes HTML and supports HTML/XLSX/Markdown/CSV.
- Tests cover the new behavior.

---

## Self-Review

**Spec coverage:** This plan covers the requested global skill audit, compare-first workflow, table + summary presentation before report generation, and broader common report formats.

**Placeholder scan:** No TBD/TODO placeholders remain. Every code step includes exact file paths and concrete code.

**Type consistency:** New report format names are consistent across `SKILL.md`, `report.py`, CLI choices, and tests: `html`, `excel`/`xlsx`, `markdown`/`md`, `csv`.
