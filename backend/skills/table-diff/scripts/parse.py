#!/usr/bin/env python3
"""
file-parser: 解析表格文件，提取结构元信息和数据内容
支持格式：.xlsx, .csv
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


def detect_encoding(file_path: str) -> str:
    """检测 CSV 文件编码，UTF-8 优先，失败回退 GBK"""
    for enc in ["utf-8", "gbk", "gb2312", "latin-1"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return "utf-8"


def serialize_cell_value(value):
    """将单元格值转换为 JSON 安全的中间值"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    return str(value)


def coerce_csv_value(value):
    """转换 CSV 字符串值，保持既有数值推断行为"""
    if value is None:
        return None
    val = value.strip()
    if val == "":
        return None
    try:
        if "." in val:
            return float(val)
        return int(val)
    except ValueError:
        return val


def infer_dtype(values: list) -> str:
    """推断列数据类型"""
    non_null = [v for v in values if v is not None and v != ""]
    if not non_null:
        return "string"

    # 尝试 integer：所有值必须是纯整数（不含小数点，或小数部分为零）
    try:
        all_int = True
        for v in non_null:
            s = str(v)
            # 含小数点的，检查小数部分是否为零
            if "." in s:
                if float(s) != int(float(s)):
                    all_int = False
                    break
            # 不含小数点的，必须是合法整数
            elif not s.lstrip("-").isdigit():
                all_int = False
                break
        if all_int:
            return "integer"
    except (ValueError, TypeError):
        pass

    # 尝试 float
    try:
        for v in non_null:
            float(str(v))
        return "float"
    except (ValueError, TypeError):
        pass

    # 尝试 datetime（简单判断）
    import re
    dt_pattern = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
    if all(dt_pattern.match(str(v)) for v in non_null):
        return "datetime"

    return "string"


def build_table_result(file_path: str, sheet_name: str, headers: list, data_rows: list) -> dict:
    """根据已截取的数据行构建统一返回结构"""
    col_data = {h: [] for h in headers}
    for row in data_rows:
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            col_data[h].append(serialize_cell_value(val))

    # 构建列元信息
    columns_meta = []
    for i, h in enumerate(headers):
        values = col_data[h]
        non_null = [v for v in values if v is not None and v != ""]
        null_count = len(values) - len(non_null)
        unique_vals = list(set(str(v) for v in non_null))
        sample_values = unique_vals[:3]

        columns_meta.append({
            "name": serialize_cell_value(h),
            "index": i,
            "dtype": infer_dtype(non_null),
            "null_count": null_count,
            "unique_count": len(unique_vals),
            "sample_values": [serialize_cell_value(v) for v in sample_values]
        })

    # 构建数据行
    data = []
    for row in data_rows:
        row_dict = {}
        for i, h in enumerate(headers):
            val = row[i] if i < len(row) else None
            row_dict[h] = serialize_cell_value(val)
        data.append(row_dict)

    return {
        "meta": {
            "source_file": os.path.basename(file_path),
            "sheet_name": serialize_cell_value(sheet_name),
            "row_count": len(data_rows),
            "col_count": len(headers),
            "columns": columns_meta
        },
        "data": data
    }


def parse_xlsx(file_path: str, sheet_name: str = None, max_rows: int = 1000) -> dict:
    """解析 .xlsx 文件"""
    if openpyxl is None:
        return {"error": "dependency_missing", "message": "openpyxl 未安装，请执行 pip install openpyxl"}

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    try:
        sheets = wb.sheetnames

        if sheet_name:
            if sheet_name not in sheets:
                return {"error": "sheet_not_found", "message": f"Sheet '{sheet_name}' 不存在", "available_sheets": sheets}
            ws = wb[sheet_name]
        else:
            ws = wb[sheets[0]]
            sheet_name = sheets[0]

        row_iter = ws.iter_rows(values_only=True)
        header_row = next(row_iter, None)
        if header_row is None:
            return {"error": "empty_file", "message": "文件内容为空"}

        # 第一行作为表头
        headers = [str(h) if h is not None else f"column_{i}" for i, h in enumerate(header_row)]
        data_rows = []
        for row in row_iter:
            # 跳过全空行，不计入 max_rows
            if not any(v is not None for v in row):
                continue
            data_rows.append(tuple(serialize_cell_value(v) for v in row))
            if len(data_rows) >= max_rows:
                break
    finally:
        wb.close()

    return build_table_result(file_path, sheet_name, headers, data_rows)


def parse_csv(file_path: str, max_rows: int = 1000) -> dict:
    """解析 .csv 文件"""
    encoding = detect_encoding(file_path)

    with open(file_path, "r", encoding=encoding) as f:
        reader = csv.reader(f)
        header_row = next(reader, None)
        if header_row is None:
            return {"error": "empty_file", "message": "文件内容为空"}

        headers = [str(h).strip() if h.strip() else f"column_{i}" for i, h in enumerate(header_row)]
        data_rows = []
        for row in reader:
            # 跳过全空行，不计入 max_rows
            if not any(v.strip() for v in row if v):
                continue
            data_rows.append(tuple(serialize_cell_value(coerce_csv_value(row[i])) if i < len(row) else None for i in range(len(headers))))
            if len(data_rows) >= max_rows:
                break

    return build_table_result(file_path, None, headers, data_rows)


def parse(file_path: str, sheet_name: str = None, max_rows: int = 1000) -> dict:
    """统一入口"""
    if not os.path.exists(file_path):
        return {"error": "file_not_found", "message": f"文件不存在: {file_path}"}

    ext = Path(file_path).suffix.lower()
    if ext == ".xlsx":
        return parse_xlsx(file_path, sheet_name, max_rows)
    elif ext == ".csv":
        return parse_csv(file_path, max_rows)
    else:
        return {"error": "unsupported_format", "message": f"不支持的格式: {ext}，仅支持 .xlsx 和 .csv"}


if __name__ == "__main__":
    # CLI 调用方式：python parse.py <file_path> [--sheet <name>] [--max-rows <n>]
    import argparse

    parser = argparse.ArgumentParser(description="表格文件解析器")
    parser.add_argument("file_path", help="文件路径")
    parser.add_argument("--sheet", default=None, help="Sheet 名称（仅 xlsx）")
    parser.add_argument("--max-rows", type=int, default=1000, help="最大读取行数")
    parser.add_argument("--output", default=None, help="输出文件路径，不指定则输出到 stdout")

    args = parser.parse_args()

    result = parse(args.file_path, args.sheet, args.max_rows)

    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
