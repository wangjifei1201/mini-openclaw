#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging
from datetime import datetime
from common_db import DB_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

DEFAULT_SECOND_PARAMS = ["卫星时间秒", "卫星运行时间秒", "PPS计数", "调用姿控时间整秒"]

def parse_createtime(tstr):
    if '.' in tstr:
        tstr = tstr.split('.')[0]
    return datetime.strptime(tstr, "%Y-%m-%d %H:%M:%S")

def fetch_data(satellites, start_time, end_time, param_name=None, param_code=None):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    base_sql = f"SELECT starname, name, tmcode, rvalval, createtime FROM tminfo WHERE starname IN ({sat_ph}) AND createtime BETWEEN %s AND %s"
    params = satellites + [start_time, end_time]
    if param_name:
        sql = base_sql + " AND name = %s ORDER BY createtime ASC"
        params.append(param_name)
    elif param_code:
        sql = base_sql + " AND tmcode = %s ORDER BY createtime ASC"
        params.append(param_code)
    else:
        name_ph = ','.join(['%s'] * len(DEFAULT_SECOND_PARAMS))
        sql = base_sql + f" AND name IN ({name_ph}) ORDER BY createtime ASC"
        params.extend(DEFAULT_SECOND_PARAMS)
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def check_increment(data):
    abnormal = []
    for i in range(1, len(data)):
        prev, cur = data[i-1], data[i]
        if prev["starname"] != cur["starname"] or prev["name"] != cur["name"]:
            continue
        try:
            t1 = parse_createtime(prev["createtime"])
            t2 = parse_createtime(cur["createtime"])
            delta_sec = int((t2 - t1).total_seconds())
        except:
            abnormal.append({"卫星编号": cur["starname"], "遥测参数名称": cur["name"], "遥测参数代码": cur["tmcode"], "工程值": cur["rvalval"], "系统接收时间": cur["createtime"], "异常说明": "时间格式错误"})
            continue
        if delta_sec <= 0:
            abnormal.append({"卫星编号": cur["starname"], "遥测参数名称": cur["name"], "遥测参数代码": cur["tmcode"], "工程值": cur["rvalval"], "系统接收时间": cur["createtime"], "异常说明": f"时间倒流或不变 (间隔{delta_sec}秒)"})
            continue
        try:
            val_prev = int(prev["rvalval"])
            val_cur = int(cur["rvalval"])
            delta_val = val_cur - val_prev
        except:
            abnormal.append({"卫星编号": cur["starname"], "遥测参数名称": cur["name"], "遥测参数代码": cur["tmcode"], "工程值": cur["rvalval"], "系统接收时间": cur["createtime"], "异常说明": "工程值非数字"})
            continue
        if delta_val > delta_sec:
            abnormal.append({"卫星编号": cur["starname"], "遥测参数名称": cur["name"], "遥测参数代码": cur["tmcode"], "工程值": cur["rvalval"], "系统接收时间": cur["createtime"], "异常说明": f"应增{delta_sec}秒，实际增{delta_val}秒"})
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
    param_name = inp.get("param_name")
    param_code = inp.get("param_code")
    if not satellites or not start_time or not end_time:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return
    try:
        data = fetch_data(satellites, start_time, end_time, param_name, param_code)
        if not data:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到数据"}))
            return
        abnormal = check_increment(data)
        summary = f"发现{len(abnormal)}处异常"
        print(json.dumps({"status":"success","data":abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()