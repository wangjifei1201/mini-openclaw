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
