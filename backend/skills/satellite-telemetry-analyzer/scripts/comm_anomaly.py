#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging, argparse
from common_db import DB_CONFIG, normalize_satellites

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def fetch_data(satellites, start_time, end_time, power_param, status_param, count_param):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    param_names = [power_param, status_param, count_param]
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
    logger.info(f"查询到 {len(rows)} 条原始记录")
    return rows

def extract_power_intervals(rows, power_param, power_on_value):
    """
    根据原始记录序列，提取通电时间段（包含该时间段内的所有记录）。
    返回列表，每个元素为 (start_time, end_time, interval_rows)
    """
    intervals = []
    current_rows = []
    in_power = False
    for row in rows:
        if row["name"] == power_param:
            if row["rvalval"] == power_on_value:
                # 开始通电，如果之前有未结束的区间，先结束（不应该发生）
                if in_power:
                    # 理论上不应该连续两个通电，但为了安全，结束前一个
                    intervals.append((current_rows[0]["createtime"], current_rows[-1]["createtime"], current_rows))
                in_power = True
                current_rows = [row]   # 包含通电记录本身
            else:
                # 断电或其他状态
                if in_power:
                    intervals.append((current_rows[0]["createtime"], current_rows[-1]["createtime"], current_rows))
                    in_power = False
                    current_rows = []
                else:
                    # 不在通电期间，忽略
                    pass
        else:
            # 其他参数
            if in_power:
                current_rows.append(row)
    # 如果最后仍处于通电状态
    if in_power and current_rows:
        intervals.append((current_rows[0]["createtime"], current_rows[-1]["createtime"], current_rows))
    logger.info(f"通电区间个数: {len(intervals)}")
    for idx, (st, et, rows_int) in enumerate(intervals):
        logger.info(f"区间{idx+1}: 起点 {st}, 终点 {et}, 包含 {len(rows_int)} 条记录")
    return intervals

def check_interval(interval_rows, status_param, count_param, status_abnormal_value):
    comm_records = []
    count_records = []
    count_values = []
    for row in interval_rows:
        t = row["createtime"]
        name = row["name"]
        val = row["rvalval"]
        if name == status_param:
            comm_records.append({
                "卫星编号": row["starname"],
                "遥测参数名称": status_param,
                "遥测参数代码": row.get("tmcode", ""),
                "系统接收时间": t,
                "工程值": val
            })
        elif name == count_param:
            try:
                val_int = int(val)
            except:
                val_int = 0
            count_values.append(val_int)
            count_records.append({
                "卫星编号": row["starname"],
                "遥测参数名称": count_param,
                "遥测参数代码": row.get("tmcode", ""),
                "系统接收时间": t,
                "工程值": val
            })
    has_invalid = any(rec["工程值"] == status_abnormal_value for rec in comm_records)
    count_increased = False
    if len(count_values) >= 2:
        for i in range(1, len(count_values)):
            if count_values[i] > count_values[i-1]:
                count_increased = True
                break
    logger.info(f"区间内通信无效存在: {has_invalid}, 计数增加: {count_increased}")
    if has_invalid and count_increased:
        all_records = comm_records + count_records
        all_records.sort(key=lambda x: x["系统接收时间"])
        return all_records
    return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON string containing parameters")
    args = parser.parse_args()
    try:
        inp = json.loads(args.json)
    except:
        print(json.dumps({"status":"error","data":[],"summary":"JSON解析失败"}))
        return
    # 解析 inp 后
    inp["satellites"] = normalize_satellites(inp.get("satellites"))
    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    power_param = inp.get("power_param")
    status_param = inp.get("status_param")
    count_param = inp.get("count_param")
    power_on_value = inp.get("power_on_value", "通电")
    status_abnormal_value = inp.get("status_abnormal_value", "通信无效")

    if not satellites or not start_time or not end_time or not power_param or not status_param or not count_param:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return

    try:
        rows = fetch_data(satellites, start_time, end_time, power_param, status_param, count_param)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到通信数据"}))
            return
        intervals = extract_power_intervals(rows, power_param, power_on_value)
        all_abnormal = []
        for st, et, interval_rows in intervals:
            res = check_interval(interval_rows, status_param, count_param, status_abnormal_value)
            if res:
                all_abnormal.extend(res)
        summary = f"发现{len(all_abnormal)}条异常记录（通信无效且计数增加）"
        print(json.dumps({"status":"success","data":all_abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()