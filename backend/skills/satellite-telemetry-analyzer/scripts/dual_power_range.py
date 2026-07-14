#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
双通电条件下的参数范围判断脚本
功能：在指定时间范围内，当两个通断参数同时为“通电”时，收集目标参数的值，判断是否超出给定范围。
输入JSON参数：
{
    "satellites": ["高分07C01星"],
    "start_time": "2025-07-30 00:00:00",
    "end_time": "2025-07-31 00:00:00",
    "power1_param": "成像处理箱通断",
    "power2_param": "焦面通断",
    "target_param": "负载电流",
    "power_on_value": "通电",          // 可选，默认"通电"
    "low_threshold": 2.50,            // 可选，默认下限
    "high_threshold": 4.25            // 可选，默认上限
}
输出：
{
    "status": "success",
    "data": [异常记录列表],
    "summary": "发现X条异常"
}
"""

import sys, json, pymysql, logging, argparse
from common_db import DB_CONFIG, normalize_satellites

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def fetch_all_data(db_config, satellites, start_time, end_time, param_names):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    param_ph = ','.join(['%s'] * len(param_names))
    sql = f"""
        SELECT starname, name, tmcode, rvalval, createtime
        FROM tminfo
        WHERE starname IN ({sat_ph})
        AND createtime >= %s AND createtime < %s
        AND name IN ({param_ph})
        ORDER BY createtime ASC
    """
    params = satellites + [start_time, end_time] + param_names
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

def get_power_intervals(time_dict, power1_param, power2_param, power_on_value):
    sorted_times = sorted(time_dict.keys())
    intervals = []
    in_power = False
    start_time = None
    for t in sorted_times:
        data = time_dict[t]
        p1 = data.get(power1_param)
        p2 = data.get(power2_param)
        if p1 == power_on_value and p2 == power_on_value:
            if not in_power:
                in_power = True
                start_time = t
        else:
            if in_power:
                intervals.append((start_time, t))
                in_power = False
    if in_power:
        intervals.append((start_time, sorted_times[-1]))
    return intervals

def query_target_in_intervals(db_config, satellites, intervals, target_param):
    if not intervals:
        return []
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    all_records = []
    for start, end in intervals:
        sql = f"""
            SELECT starname, name, tmcode, rvalval, createtime
            FROM tminfo
            WHERE starname IN ({sat_ph})
            AND createtime >= %s AND createtime < %s
            AND name = %s
            ORDER BY createtime ASC
        """
        cursor.execute(sql, satellites + [start, end, target_param])
        rows = cursor.fetchall()
        all_records.extend(rows)
    cursor.close()
    conn.close()
    return all_records

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    args = parser.parse_args()
    try:
        inp = json.loads(args.json)
    except Exception as e:
        print(json.dumps({"status":"error","data":[],"summary":f"JSON解析失败: {e}"}))
        return
    inp["satellites"] = normalize_satellites(inp.get("satellites"))
    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    power1_param = inp.get("power1_param")
    power2_param = inp.get("power2_param")
    target_param = inp.get("target_param")
    power_on_value = inp.get("power_on_value", "通电")
    low = inp.get("low_threshold")
    high = inp.get("high_threshold")
    db_config = inp.get("db_config", DB_CONFIG)

    if not satellites or not start_time or not end_time or not power1_param or not power2_param or not target_param:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return

    try:
        # 查询所有三个参数的数据
        param_names = [power1_param, power2_param, target_param]
        rows = fetch_all_data(db_config, satellites, start_time, end_time, param_names)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到数据"}))
            return

        time_dict = group_by_time(rows)
        intervals = get_power_intervals(time_dict, power1_param, power2_param, power_on_value)
        target_records = query_target_in_intervals(db_config, satellites, intervals, target_param)

        abnormal = []
        for rec in target_records:
            try:
                val = float(rec["rvalval"])
            except:
                continue
            if low is not None and val < low:
                abnormal.append({
                    "卫星编号": rec["starname"],
                    "遥测参数名称": rec["name"],
                    "遥测参数代码": rec["tmcode"],
                    "系统接收时间": rec["createtime"],
                    "工程值": rec["rvalval"]
                })
            elif high is not None and val > high:
                abnormal.append({
                    "卫星编号": rec["starname"],
                    "遥测参数名称": rec["name"],
                    "遥测参数代码": rec["tmcode"],
                    "系统接收时间": rec["createtime"],
                    "工程值": rec["rvalval"]
                })
        summary = f"发现{len(abnormal)}条异常"
        print(json.dumps({"status":"success","data":abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()