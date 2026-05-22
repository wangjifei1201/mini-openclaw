#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging
from common_db import DB_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

POWER_PARAM = "主份双频导航通断"
COMM_STATUS_PARAM = "导航通信状态"
COUNT_PARAM = "主份导航通信异常计数"

def fetch_nav_data(satellites, start_time, end_time):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    param_list = [POWER_PARAM, COMM_STATUS_PARAM, COUNT_PARAM]
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

def extract_power_intervals(time_dict):
    sorted_times = sorted(time_dict.keys())
    intervals = []
    current = []
    in_power = False
    for t in sorted_times:
        power_val = time_dict[t].get(POWER_PARAM)
        if power_val == "通电":
            if not in_power:
                in_power = True
            current.append(t)
        else:
            if in_power:
                intervals.append(current)
                current = []
                in_power = False
    if in_power and current:
        intervals.append(current)
    return intervals

def check_interval(time_points, time_dict):
    comm_records = []
    count_records = []
    count_values = []
    for t in time_points:
        data = time_dict[t]
        if COMM_STATUS_PARAM in data:
            comm_records.append({
                "卫星编号": data["starname"],
                "遥测参数名称": COMM_STATUS_PARAM,
                "遥测参数代码": "",
                "系统接收时间": t,
                "工程值": data[COMM_STATUS_PARAM]
            })
        if COUNT_PARAM in data:
            val_str = data.get(COUNT_PARAM, "0")
            try:
                val_int = int(val_str)
            except:
                val_int = 0
            count_values.append(val_int)
            count_records.append({
                "卫星编号": data["starname"],
                "遥测参数名称": COUNT_PARAM,
                "遥测参数代码": "",
                "系统接收时间": t,
                "工程值": val_str
            })
    has_invalid = any(rec["工程值"] == "通信无效" for rec in comm_records)
    count_increased = False
    if len(count_values) >= 2:
        for i in range(1, len(count_values)):
            if count_values[i] > count_values[i-1]:
                count_increased = True
                break
    if has_invalid and count_increased:
        all_records = comm_records + count_records
        all_records.sort(key=lambda x: x["系统接收时间"])
        return all_records
    return None

def enrich_with_code(records, original_rows):
    code_map = {}
    for row in original_rows:
        key = (row["createtime"], row["name"])
        code_map[key] = row.get("tmcode", "")
    for rec in records:
        key = (rec["系统接收时间"], rec["遥测参数名称"])
        rec["遥测参数代码"] = code_map.get(key, "")
    return records

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
        rows = fetch_nav_data(satellites, start_time, end_time)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到导航数据"}))
            return
        time_dict = group_by_time(rows)
        intervals = extract_power_intervals(time_dict)
        all_abnormal = []
        for interval in intervals:
            res = check_interval(interval, time_dict)
            if res:
                all_abnormal.extend(enrich_with_code(res, rows))
        summary = f"发现{len(all_abnormal)}条异常记录（通信无效且计数增加）"
        print(json.dumps({"status":"success","data":all_abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()