#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging, argparse
from common_db import DB_CONFIG, normalize_satellites

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

LOG_GROWTH_NAME = "卫星LOG增长计数"
LOG_MARK_NAMES = [f"LOG标记{i}" for i in range(1, 11)]

def fetch_log_data(satellites, start_time, end_time):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    param_list = [LOG_GROWTH_NAME] + LOG_MARK_NAMES
    param_ph = ','.join(['%s'] * len(param_list))
    sql = f"""
        SELECT starname, name, tmcode, rvalval, createtime
        FROM tminfo
        WHERE starname IN ({sat_ph})
        AND createtime >= %s AND createtime < %s
        AND name IN ({param_ph})
        ORDER BY createtime ASC
    """
    params = satellites + [start_time, end_time] + param_list
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def extract_growth_segments(rows):
    """
    以卫星LOG增长计数 == 0 作为断段标志。
    返回段列表，每个段为 [(time, value), ...]（包含所有正值）。
    """
    segments = []
    current = []
    for row in rows:
        if row["name"] != LOG_GROWTH_NAME:
            continue
        t = row["createtime"]
        try:
            val = int(row["rvalval"])
        except:
            val = 0
        if val == 0:
            if current:
                segments.append(current)
                current = []
        else:
            current.append((t, val))
    if current:
        segments.append(current)
    return segments

def get_first_max_record(seg, rows):
    """返回段内最大值第一次出现的时间及该时间点的 LOG 标记"""
    if not seg:
        return None
    max_val = max(v for _, v in seg)
    max_time = None
    for t, v in seg:
        if v == max_val:
            max_time = t
            break
    if max_time is None:
        return None
    satellite = None
    log_marks = {}
    for row in rows:
        if row["createtime"] == max_time:
            if satellite is None:
                satellite = row["starname"]
            if row["name"].startswith("LOG标记"):
                val = row["rvalval"]
                if val and val != "0":
                    log_marks[row["name"]] = val
    if satellite is None:
        satellite = "未知卫星"
    return {
        "卫星编号": satellite,
        "增长时间": max_time,
        "最大增长计数": max_val,
        "LOG标记详情": log_marks
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON string containing parameters")
    args = parser.parse_args()
    try:
        inp = json.loads(args.json)
    except:
        print(json.dumps({"status":"error","data":[],"summary":"JSON解析失败"}))
        return
    inp["satellites"] = normalize_satellites(inp.get("satellites"))
    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    if not satellites or not start_time or not end_time:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return
    try:
        rows = fetch_log_data(satellites, start_time, end_time)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到LOG数据"}))
            return
        segments = extract_growth_segments(rows)
        results = []
        for seg in segments:
            # 只要段内最大值 > 0 即输出（代表有正数值）
            if max(v for _, v in seg) > 0:
                rec = get_first_max_record(seg, rows)
                if rec:
                    results.append(rec)
        summary = f"发现{len(results)}次LOG增长"
        print(json.dumps({"status":"success","data":results,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()