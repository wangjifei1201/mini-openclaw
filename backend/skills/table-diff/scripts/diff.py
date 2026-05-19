#!/usr/bin/env python3
"""
table-differ: 表格核心比对引擎
根据主键和规则执行行级 + 单元格级比对
"""

import json
import sys
from collections import defaultdict


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


def normalize_value(val, case_sensitive: bool = False, null_equals_empty: bool = True):
    """规范化值用于比较"""
    # 空值等价处理
    if null_equals_empty:
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return "__NULL__"

    if val is None:
        return "__NULL__"

    if isinstance(val, str):
        if not case_sensitive:
            val = val.lower()
        val = val.strip()
        if null_equals_empty and val == "":
            return "__NULL__"

    return val


def values_equal(left_val, right_val, column: str, tolerance: dict,
                 case_sensitive: bool, null_equals_empty: bool,
                 left_dtype: str = None, right_dtype: str = None) -> bool:
    """比较两个值是否相等"""
    l_norm = normalize_value(left_val, case_sensitive, null_equals_empty)
    r_norm = normalize_value(right_val, case_sensitive, null_equals_empty)

    # 空值等价
    if l_norm == "__NULL__" and r_norm == "__NULL__":
        return True
    if l_norm == "__NULL__" or r_norm == "__NULL__":
        return False

    # 数值容差
    if column in tolerance and tolerance[column] is not None:
        try:
            l_num = float(left_val) if left_val is not None else None
            r_num = float(right_val) if right_val is not None else None
            if l_num is not None and r_num is not None:
                return abs(l_num - r_num) <= tolerance[column]
        except (ValueError, TypeError):
            pass

    # 数值类型的默认比较（int 和 float 同值）
    if left_dtype in ("integer", "float") and right_dtype in ("integer", "float"):
        try:
            return float(str(left_val)) == float(str(right_val))
        except (ValueError, TypeError):
            pass

    # 字符串比较
    return str(l_norm) == str(r_norm)


def get_dtypes_map(table: dict) -> dict:
    """获取列名 → dtype 的映射"""
    return {col["name"]: col["dtype"] for col in table["meta"]["columns"]}


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


def diff(left: dict, right: dict, rules: dict) -> dict:
    """执行比对"""
    primary_key = rules.get("primary_key", [])
    ignore_columns = rules.get("ignore_columns", [])
    tolerance = rules.get("tolerance", {})
    case_sensitive = rules.get("case_sensitive", False)
    null_equals_empty = rules.get("null_equals_empty", True)
    ignore_order = rules.get("ignore_order", True)

    # === 校验 ===
    if not primary_key:
        return {"error": "invalid_rules", "message": "primary_key 不能为空"}

    left_col_names = set(col["name"] for col in left["meta"]["columns"])
    right_col_names = set(col["name"] for col in right["meta"]["columns"])

    missing_in_left = [k for k in primary_key if k not in left_col_names]
    missing_in_right = [k for k in primary_key if k not in right_col_names]
    if missing_in_left or missing_in_right:
        return {
            "error": "primary_key_missing",
            "message": f"主键列不存在：左表缺 {missing_in_left}，右表缺 {missing_in_right}"
        }

    if not left.get("data") or not right.get("data"):
        return {"error": "empty_data", "message": "表数据为空"}

    # === 确定比对列 ===
    compare_columns = sorted(
        left_col_names & right_col_names - set(primary_key) - set(ignore_columns)
    )

    left_dtypes = get_dtypes_map(left)
    right_dtypes = get_dtypes_map(right)

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

    left_keys = set(left_index.keys())
    right_keys = set(right_index.keys())

    # === 行级分类 ===
    matched_keys = left_keys & right_keys
    left_only_keys = left_keys - right_keys
    right_only_keys = right_keys - left_keys

    diffs = []
    column_change_counts = defaultdict(int)

    # --- left_only ---
    for key in sorted(left_only_keys, key=sort_key):
        row = left_index[key]
        pk_dict = _extract_pk(row, primary_key, key)
        diffs.append({
            "type": "left_only",
            "primary_key": pk_dict,
            "row_data": {k: v for k, v in row.items() if k not in primary_key}
        })

    # --- right_only ---
    for key in sorted(right_only_keys, key=sort_key):
        row = right_index[key]
        pk_dict = _extract_pk(row, primary_key, key)
        diffs.append({
            "type": "right_only",
            "primary_key": pk_dict,
            "row_data": {k: v for k, v in row.items() if k not in primary_key}
        })

    # --- matched: 单元格级比对 ---
    value_changed_count = 0
    unchanged_count = 0

    for key in sorted(matched_keys, key=sort_key):
        left_row = left_index[key]
        right_row = right_index[key]

        changes = []
        for col in compare_columns:
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
                    "right_value": _serialize(r_val)
                })
                column_change_counts[col] += 1

        if changes:
            pk_dict = _extract_pk(left_row, primary_key, key)
            diffs.append({
                "type": "value_changed",
                "primary_key": pk_dict,
                "changes": changes
            })
            value_changed_count += 1
        else:
            unchanged_count += 1

    # === 统计 ===
    total_matched = len(matched_keys)
    total_left = len(left_keys)
    total_right = len(right_keys)
    change_rate = round(value_changed_count / total_matched, 4) if total_matched > 0 else 0

    # 列级统计
    column_diff_summary = {}
    for col in compare_columns:
        changed = column_change_counts.get(col, 0)
        rate = round(changed / total_matched, 4) if total_matched > 0 else 0
        if changed > 0:
            column_diff_summary[col] = {
                "changed_count": changed,
                "change_rate": rate
            }

    diffs = sorted(diffs, key=lambda item: sort_key(tuple(item.get("primary_key", {}).values())))

    return {
        "comparison_mode": "key_based",
        "compare_columns": compare_columns,
        "summary": {
            "total_left": total_left,
            "total_right": total_right,
            "matched": total_matched,
            "left_only": len(left_only_keys),
            "right_only": len(right_only_keys),
            "value_changed": value_changed_count,
            "unchanged": unchanged_count,
            "change_rate": change_rate
        },
        "diffs": diffs,
        "column_diff_summary": column_diff_summary
    }


def _extract_pk(row: dict, primary_key: list, key) -> dict:
    """提取主键字典"""
    if len(primary_key) == 1:
        return {primary_key[0]: key}
    return {col: row.get(col) for col in primary_key}


def _serialize(val):
    """序列化值用于 JSON 输出"""
    if val is None:
        return None
    if isinstance(val, float):
        # 避免浮点精度问题
        if val == int(val):
            return int(val)
        return round(val, 6)
    return val


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="表格比对引擎")
    parser.add_argument("left_file", help="左表 JSON 文件路径")
    parser.add_argument("right_file", help="右表 JSON 文件路径")
    parser.add_argument("--rules", required=True, help="比对规则 JSON 文件路径")
    parser.add_argument("--output", default=None, help="输出文件路径")

    args = parser.parse_args()

    with open(args.left_file, "r", encoding="utf-8") as f:
        left = json.load(f)
    with open(args.right_file, "r", encoding="utf-8") as f:
        right = json.load(f)
    with open(args.rules, "r", encoding="utf-8") as f:
        rules = json.load(f)

    result = diff(left, right, rules)

    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
