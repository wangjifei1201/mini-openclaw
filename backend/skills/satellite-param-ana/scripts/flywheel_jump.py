#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging
from typing import List, Dict, Optional
from common_db import DB_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def fetch_flywheel_data(satellites, start_time, end_time, metrics: List[str]) -> List[Dict]:
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    met_ph = ','.join(['%s'] * len(metrics))
    sql = f"""
        SELECT starname, name, tmcode, rvalval, createtime
        FROM tminfo
        WHERE starname IN ({sat_ph})
        AND createtime BETWEEN %s AND %s
        AND name IN ({met_ph})
        ORDER BY createtime ASC
    """
    params = satellites + [start_time, end_time] + metrics
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def calculate_baseline(values: List[float]) -> Optional[float]:
    window_size = 5
    n = len(values)
    for i in range(n - window_size + 1):
        window = values[i:i+window_size]
        valid = True
        for j in range(1, window_size):
            if abs(window[j] - window[j-1]) > 1:
                valid = False
                break
        if valid:
            return sum(window) / window_size
    return None

def get_param_baseline(data: List[Dict]) -> Optional[float]:
    if not data:
        return None
    values = []
    for row in data:
        try:
            v = float(row["rvalval"])
            values.append(v)
        except:
            continue
    if len(values) < 5:
        return None
    return calculate_baseline(values)

def detect_jumps(param_data: List[Dict], baseline: float) -> List[Dict]:
    abnormal = []
    for row in param_data:
        try:
            val = float(row["rvalval"])
        except:
            continue
        if baseline == 0:
            continue
        deviation = abs(val - baseline) / baseline
        if deviation > 0.1:
            abnormal.append({
                "卫星编号": row["starname"],
                "参数名称": row["name"],
                "参数代码": row["tmcode"],
                "时间": row["createtime"],
                "工程值": val,
                "基准值": round(baseline, 2),
                "偏差比例": round(deviation, 4),
                "异常说明": "转速跳变"
            })
    return abnormal

def main():
    raw = sys.stdin.read()
    try:
        inp = json.loads(raw) if raw.strip() else {}
    except:
        print(json.dumps({"status":"error","data":[],"summary":"JSON解析失败"}))
        return
    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    metrics = inp.get("metrics", [])
    if not satellites or not start_time or not end_time or not metrics:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return
    try:
        rows = fetch_flywheel_data(satellites, start_time, end_time, metrics)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到数据"}))
            return
        param_groups = {}
        for row in rows:
            param_groups.setdefault(row["name"], []).append(row)
        all_abnormal = []
        for pname, data_list in param_groups.items():
            baseline = get_param_baseline(data_list)
            if baseline is None:
                logger.warning(f"参数 {pname} 无法获取基准值")
                continue
            jumps = detect_jumps(data_list, baseline)
            all_abnormal.extend(jumps)
        summary = f"发现{len(all_abnormal)}处跳变"
        print(json.dumps({"status":"success","data":all_abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()