#!/usr/bin/env python3
"""
table-analyzer: 对比两份表结构，识别主键候选，输出比对建议
"""

import json
import os
import sys
from itertools import combinations


# 主键关键词加权词表
KEY_KEYWORDS = ["id", "编号", "号", "代码", "code", "key", "键", "序号", "no"]


def get_column_map(table: dict) -> dict:
    """提取列名 → meta 的映射"""
    return {col["name"]: col for col in table["meta"]["columns"]}


def analyze_structure(left: dict, right: dict) -> dict:
    """分析两表结构差异"""
    left_cols = get_column_map(left)
    right_cols = get_column_map(right)

    left_names = set(left_cols.keys())
    right_names = set(right_cols.keys())

    common = sorted(left_names & right_names)
    left_only = sorted(left_names - right_names)
    right_only = sorted(right_names - left_names)

    # 类型不一致
    type_mismatch = []
    for name in common:
        lt = left_cols[name]["dtype"]
        rt = right_cols[name]["dtype"]
        if lt != rt:
            type_mismatch.append({"column": name, "left_type": lt, "right_type": rt})

    return {
        "common_columns": common,
        "left_only_columns": left_only,
        "right_only_columns": right_only,
        "type_mismatch": type_mismatch,
        "row_count": {
            "left": left["meta"]["row_count"],
            "right": right["meta"]["row_count"]
        }
    }


def keyword_boost(col_name: str) -> float:
    """列名含关键词时加权"""
    name_lower = col_name.lower()
    for kw in KEY_KEYWORDS:
        if kw in name_lower:
            return 0.2
    return 0.0


def check_uniqueness(col_name: str, table: dict) -> bool:
    """检查列在表中是否唯一"""
    col_map = get_column_map(table)
    if col_name not in col_map:
        return False
    meta = col_map[col_name]
    return meta["unique_count"] == table["meta"]["row_count"] and meta["null_count"] == 0


def compute_combination_unique(col_names: list, table: dict) -> bool:
    """检查多列组合是否唯一"""
    if not table.get("data"):
        return False

    seen = set()
    for row in table["data"]:
        key = tuple(str(row.get(c, "")) for c in col_names)
        if key in seen:
            return False
        seen.add(key)
    return True


def find_primary_key_candidates(left: dict, right: dict, struct_diff: dict) -> list:
    """主键识别：单列 → 组合列"""
    candidates = []
    common = struct_diff["common_columns"]
    left_row_count = left["meta"]["row_count"]
    right_row_count = right["meta"]["row_count"]

    if not common:
        return candidates

    left_cols = get_column_map(left)
    right_cols = get_column_map(right)

    # === Step 1-4: 单列检测 ===
    for col_name in common:
        l_meta = left_cols[col_name]
        r_meta = right_cols[col_name]

        # 跳过有空值的列
        if l_meta["null_count"] > 0 or r_meta["null_count"] > 0:
            continue

        # 唯一性
        l_unique = l_meta["unique_count"] == left_row_count
        r_unique = r_meta["unique_count"] == right_row_count

        if not l_unique and not r_unique:
            continue

        # 计算 confidence
        confidence = 0.7
        confidence += keyword_boost(col_name)

        if l_unique and r_unique:
            pass  # 两端都唯一，保持 confidence
        elif l_unique or r_unique:
            confidence -= 0.3  # 仅一端唯一

        confidence = min(confidence, 1.0)

        # 生成 reason
        reasons = []
        if l_unique and r_unique:
            reasons.append("两表均唯一")
        elif l_unique:
            reasons.append("仅左表唯一")
        else:
            reasons.append("仅右表唯一")
        if keyword_boost(col_name) > 0:
            reasons.append("列名含关键词")

        candidates.append({
            "columns": [col_name],
            "confidence": round(confidence, 2),
            "reason": "，".join(reasons)
        })

    # === Step 5: 组合键探测 ===
    # 仅在单列无高置信度候选（max confidence < 0.8）时触发
    max_single_conf = max((c["confidence"] for c in candidates), default=0)
    if max_single_conf < 0.8:
        # 筛选 unique_count > row_count * 0.5 的列作为候选池
        left_pool = [c for c in common
                     if left_cols[c]["null_count"] == 0
                     and left_cols[c]["unique_count"] > left_row_count * 0.5]
        right_pool = [c for c in common
                      if right_cols[c]["null_count"] == 0
                      and right_cols[c]["unique_count"] > right_row_count * 0.5]
        pool = sorted(set(left_pool) & set(right_pool))

        # 尝试 2 列组合
        for combo in combinations(pool, 2):
            combo_list = list(combo)
            l_ok = compute_combination_unique(combo_list, left)
            r_ok = compute_combination_unique(combo_list, right)

            if l_ok and r_ok:
                confidence = 0.65 + sum(keyword_boost(c) for c in combo_list) * 0.5
                confidence = min(confidence, 0.9)

                candidates.append({
                    "columns": combo_list,
                    "confidence": round(confidence, 2),
                    "reason": f"组合键（{' + '.join(combo_list)}），两表均唯一"
                })

        # 尝试 3 列组合
        if not any(c["confidence"] >= 0.65 for c in candidates):
            for combo in combinations(pool, 3):
                combo_list = list(combo)
                l_ok = compute_combination_unique(combo_list, left)
                r_ok = compute_combination_unique(combo_list, right)

                if l_ok and r_ok:
                    confidence = 0.5
                    candidates.append({
                        "columns": combo_list,
                        "confidence": round(confidence, 2),
                        "reason": f"三列组合键（{' + '.join(combo_list)}），两表均唯一"
                    })

    # 按 confidence 降序排列
    candidates.sort(key=lambda x: x["confidence"], reverse=True)
    return candidates[:5]


def generate_suggestion(candidates: list, struct_diff: dict) -> dict:
    """基于分析结果生成比对建议"""
    warnings = []

    # 推荐主键
    if candidates:
        best = candidates[0]
        recommended_key = best["columns"]
        if best["confidence"] < 0.5:
            warnings.append(f"推荐主键置信度较低（{best['confidence']}），建议手动确认")
    else:
        recommended_key = []
        warnings.append("未找到自动识别的主键候选，请手动指定")

    # 右表独有列默认忽略
    ignore_columns = list(struct_diff["right_only_columns"])
    if ignore_columns:
        warnings.append(f"右表多出列：{'、'.join(ignore_columns)}，比对时将被忽略")

    # 类型不一致警告
    for m in struct_diff["type_mismatch"]:
        warnings.append(f"列 '{m['column']}' 类型不一致：左表 {m['left_type']}，右表 {m['right_type']}")

    # 左表独有列也提示
    if struct_diff["left_only_columns"]:
        warnings.append(f"左表多出列：{'、'.join(struct_diff['left_only_columns'])}，仅存在于左表")

    # 比对规则默认值
    recommended_rules = {
        "primary_key": recommended_key,
        "ignore_columns": ignore_columns,
        "tolerance": {},
        "case_sensitive": False,
        "null_equals_empty": True,
        "ignore_order": True
    }

    return {
        "recommended_key": recommended_key,
        "recommended_rules": recommended_rules,
        "warnings": warnings
    }


def analyze(left: dict, right: dict) -> dict:
    """统一入口"""
    # 校验输入
    if not left.get("meta") or not right.get("meta"):
        return {"error": "invalid_input", "message": "输入格式非法，需要 file-parser 的完整输出"}

    struct_diff = analyze_structure(left, right)

    if not struct_diff["common_columns"]:
        return {
            "error": "no_common_columns",
            "message": "两表无任何共有列，无法进行匹配比对",
            "structure_diff": struct_diff
        }

    candidates = find_primary_key_candidates(left, right, struct_diff)
    suggestion = generate_suggestion(candidates, struct_diff)

    return {
        "structure_diff": struct_diff,
        "primary_key_candidates": candidates,
        "suggestion": suggestion
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="表格结构分析与主键识别")
    parser.add_argument("left_file", help="左表 JSON 文件路径（file-parser 输出）")
    parser.add_argument("right_file", help="右表 JSON 文件路径（file-parser 输出）")
    parser.add_argument("--output", default=None, help="输出文件路径")

    args = parser.parse_args()

    with open(args.left_file, "r", encoding="utf-8") as f:
        left = json.load(f)
    with open(args.right_file, "r", encoding="utf-8") as f:
        right = json.load(f)

    result = analyze(left, right)

    output = json.dumps(result, ensure_ascii=False, indent=2, default=str)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)
