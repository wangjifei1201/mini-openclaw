#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging
from common_db import DB_CONFIG

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
        AND createtime BETWEEN %s AND %s
        AND name IN ({param_ph})
        ORDER BY createtime ASC
    """
    params = satellites + [start_time, end_time] + param_list
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def group_by_time(rows):
    time_dict = {}
    for row in rows:
        t = row["createtime"]
        if t not in time_dict:
            time_dict[t] = {"starname": row["starname"]}
        time_dict[t][row["name"]] = row["rvalval"]
    return time_dict

def extract_growth_segments(time_dict):
    sorted_times = sorted(time_dict.keys())
    growth_values = []
    for t in sorted_times:
        val = time_dict[t].get(LOG_GROWTH_NAME)
        try:
            int_val = int(val) if val is not None else 0
        except:
            int_val = 0
        growth_values.append((t, int_val))
    segments = []
    current = []
    for t, v in growth_values:
        if v > 0:
            current.append((t, v))
        else:
            if current:
                segments.append(current)
                current = []
    if current:
        segments.append(current)
    return segments

def process_segments(segments, time_dict):
    results = []
    for seg in segments:
        if not seg:
            continue
        max_val = max(v for _, v in seg)
        max_time = None
        for t, v in seg:
            if v == max_val:
                max_time = t
                break
        if max_time is None:
            continue
        satellite = time_dict[max_time].get("starname", "未知卫星")
        log_marks = {}
        for mark_name in LOG_MARK_NAMES:
            val = time_dict[max_time].get(mark_name)
            if val and val != "0":
                log_marks[mark_name] = val
        results.append({
            "卫星编号": satellite,
            "增长时间": max_time,
            "最大增长计数": max_val,
            "LOG标记详情": log_marks
        })
    return results

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
    if not satellites or not start_time or not end_time:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return
    try:
        rows = fetch_log_data(satellites, start_time, end_time)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到LOG数据"}))
            return
        time_dict = group_by_time(rows)
        segments = extract_growth_segments(time_dict)
        results = process_segments(segments, time_dict)
        summary = f"发现{len(results)}次LOG增长"
        print(json.dumps({"status":"success","data":results,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()