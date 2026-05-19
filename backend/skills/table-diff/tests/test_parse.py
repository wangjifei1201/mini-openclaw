import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import parse as parse_module
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

    def test_parse_xls_skips_empty_rows_and_limits_to_two_non_empty_rows(self):
        if xlrd is None or xlwt is None:
            self.skipTest("xlrd/xlwt is not installed")

        self.assertIs(parse_module.openpyxl, openpyxl)
        self.assertIs(parse_module.parse_csv, parse_csv)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.xls"
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("Sheet1")
            rows = [
                ["name", "score"],
                ["alice", 91],
                ["", ""],
                ["bob", 88],
                ["carol", 77],
            ]

            for row_index, row in enumerate(rows):
                for col_index, value in enumerate(row):
                    sheet.write(row_index, col_index, value)

            workbook.save(str(path))
            result = parse(str(path), max_rows=2)

        self.assertNotIn("error", result)
        self.assertEqual(
            result["data"],
            [
                {"name": "alice", "score": 91.0},
                {"name": "bob", "score": 88.0},
            ],
        )
        self.assertEqual(result["meta"]["row_count"], 2)

    def test_parse_xls_preserves_created_at_string_in_json_output(self):
        if xlrd is None or xlwt is None:
            self.skipTest("xlrd/xlwt is not installed")

        self.assertIs(parse_module.openpyxl, openpyxl)
        self.assertIs(parse_module.parse_csv, parse_csv)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "created-at.xls"
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet("Sheet1")
            sheet.write(0, 0, "created_at")
            sheet.write(1, 0, "2024-01-02 03:04:05")
            workbook.save(str(path))

            result = parse(str(path), max_rows=1)
            payload = json.dumps(result, ensure_ascii=False)

        self.assertNotIn("error", result)
        self.assertEqual(result["data"][0]["created_at"], "2024-01-02 03:04:05")
        self.assertIn("2024-01-02 03:04:05", payload)
        self.assertIn(
            "2024-01-02 03:04:05",
            result["meta"]["columns"][0]["sample_values"],
        )


if __name__ == "__main__":
    unittest.main()
