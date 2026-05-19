import csv
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from report import openpyxl, report


def formula_diff_result():
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
                "primary_key": {"@id": "\t=pk"},
                "row_number": " +12",
                "changes": [
                    {"column": "@column", "left_value": "=SUM(1,1)", "right_value": "  -2"}
                ],
            },
            {
                "type": "left_only",
                "primary_key": {"id": "-left"},
                "row_data": {"name": "+left", "amount": "@left"},
            },
            {
                "type": "right_only",
                "primary_key": {"id": "@right"},
                "row_data": {"name": "=right", "amount": "\r+right"},
            },
        ],
        "column_diff_summary": {
            "@column": {"changed_count": 1, "change_rate": 1.0},
            "+summary": {"changed_count": 1, "change_rate": 1.0},
        },
    }


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

    def test_html_report_uses_explicit_filter_event_argument(self):
        html = report(diff_result(), LEFT_META, RIGHT_META, "html")

        self.assertIn('onclick="filter(event, \'all\')"', html)
        self.assertIn('onclick="filter(event, \'value_changed\')"', html)
        self.assertIn('onclick="filter(event, \'left_only\')"', html)
        self.assertIn('onclick="filter(event, \'right_only\')"', html)
        self.assertIn("function filter(event, type) {", html)

    def test_markdown_report_escapes_row_number_content(self):
        diff = diff_result()
        diff["diffs"][0]["row_number"] = '1|<b>x</b>\nnext'

        markdown = report(diff, LEFT_META, RIGHT_META, "markdown")

        self.assertIn("1\\|&lt;b&gt;x&lt;/b&gt;<br>next", markdown)
        self.assertNotIn("| 1|<b>x</b>", markdown)
        self.assertNotIn("1|<b>x</b>\nnext", markdown)

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

    def test_csv_report_escapes_formula_like_fields(self):
        with tempfile.NamedTemporaryFile(suffix=".csv") as tmp:
            output_path = report(formula_diff_result(), LEFT_META, RIGHT_META, "csv", tmp.name)
            self.assertEqual(output_path, tmp.name)
            tmp.seek(0)
            content = tmp.read().decode("utf-8-sig")

        rows = list(csv.DictReader(io.StringIO(content)))
        for row in rows:
            for value in row.values():
                self.assertFalse(value.lstrip().startswith(("=", "+", "-", "@")), value)

        self.assertEqual(rows[0]["primary_key"], "'@id=\t=pk")
        self.assertEqual(rows[0]["row_number"], "' +12")
        self.assertEqual(rows[0]["column"], "'@column")
        self.assertEqual(rows[0]["left_value"], "'=SUM(1,1)")
        self.assertEqual(rows[0]["right_value"], "'  -2")
        self.assertEqual(rows[1]["left_value"], '{"amount": "@left", "name": "+left"}')
        self.assertEqual(rows[2]["right_value"], '{"amount": "\\r+right", "name": "=right"}')

    def test_excel_report_escapes_formula_like_cells(self):
        if openpyxl is None:
            self.skipTest("openpyxl is not installed")
        with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
            output_path = report(formula_diff_result(), LEFT_META, RIGHT_META, "xlsx", tmp.name)
            self.assertEqual(output_path, tmp.name)
            wb = openpyxl.load_workbook(tmp.name, data_only=False)

        for ws in wb.worksheets:
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        self.assertFalse(cell.value.lstrip().startswith(("=", "+", "-", "@")), cell.value)

        self.assertEqual(wb["概览"]["A14"].value, "'@column")
        self.assertEqual(wb["概览"]["A15"].value, "'+summary")
        self.assertEqual(wb["值变化明细"]["A2"].value, "'\t=pk")
        self.assertEqual(wb["值变化明细"]["B2"].value, "'@column")
        self.assertEqual(wb["值变化明细"]["C2"].value, "'=SUM(1,1)")
        self.assertEqual(wb["值变化明细"]["D2"].value, "'  -2")
        self.assertEqual(wb["新增行"]["A2"].value, "'@right")
        self.assertEqual(wb["新增行"]["B2"].value, "'=right")
        self.assertEqual(wb["新增行"]["C2"].value, "'\r+right")
        self.assertEqual(wb["删除行"]["A2"].value, "'-left")
        self.assertEqual(wb["删除行"]["B2"].value, "'+left")
        self.assertEqual(wb["删除行"]["C2"].value, "'@left")
        self.assertEqual(wb["完整对比"]["B2"].value, "'\t=pk")
        self.assertEqual(wb["完整对比"]["C2"].value, "'=SUM(1,1)")
        self.assertEqual(wb["完整对比"]["D2"].value, "'  -2")
    def test_function_csv_without_output_returns_json_error(self):
        result = report(diff_result(), LEFT_META, RIGHT_META, "csv")

        self.assertEqual(json.loads(result)["error"], "output_required")

    def test_function_xlsx_without_output_returns_json_error(self):
        result = report(diff_result(), LEFT_META, RIGHT_META, "xlsx")

        self.assertEqual(json.loads(result)["error"], "output_required")

    def test_cli_csv_without_output_exits_nonzero(self):
        self.assert_cli_requires_output_for_format("csv")

    def test_cli_xlsx_without_output_exits_nonzero(self):
        self.assert_cli_requires_output_for_format("xlsx")

    def test_cli_excel_without_output_exits_nonzero(self):
        self.assert_cli_requires_output_for_format("excel")

    def assert_cli_requires_output_for_format(self, report_format):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            diff_file = tmpdir_path / "diff.json"
            left_meta_file = tmpdir_path / "left_meta.json"
            right_meta_file = tmpdir_path / "right_meta.json"
            diff_file.write_text(json.dumps(diff_result(), ensure_ascii=False), encoding="utf-8")
            left_meta_file.write_text(json.dumps(LEFT_META, ensure_ascii=False), encoding="utf-8")
            right_meta_file.write_text(json.dumps(RIGHT_META, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "report.py"),
                    str(diff_file),
                    "--left-meta",
                    str(left_meta_file),
                    "--right-meta",
                    str(right_meta_file),
                    "--format",
                    report_format,
                ],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        combined_output = result.stdout + result.stderr
        self.assertIn("--output is required for csv/xlsx/excel formats", combined_output)
        self.assertNotIn("报告已生成", combined_output)


if __name__ == "__main__":
    unittest.main()
