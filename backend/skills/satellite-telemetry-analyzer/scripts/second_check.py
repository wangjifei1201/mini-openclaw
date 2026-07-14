#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import json
import pymysql
import logging
import argparse
from datetime import datetime
from common_db import DB_CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def normalize_satellites(satellites):
    """去除卫星名称中的所有空格"""
    if not satellites:
        return satellites
    if isinstance(satellites, list):
        return [s.replace(" ", "") for s in satellites]
    return satellites

def fetch_data(db_config, satellites, start_time, end_time, param_name, param_code):
    conn = pymysql.connect(**db_config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sat_ph = ','.join(['%s'] * len(satellites))
    if param_code:
        sql = f"""
            SELECT starname, name, tmcode, rvalval, createtime
            FROM tminfo
            WHERE starname IN ({sat_ph})
            AND createtime >= %s AND createtime < %s
            AND tmcode = %s
            ORDER BY createtime ASC
        """
        params = satellites + [start_time, end_time, param_code]
    else:
        sql = f"""
            SELECT starname, name, tmcode, rvalval, createtime
            FROM tminfo
            WHERE starname IN ({sat_ph})
            AND createtime >= %s AND createtime < %s
            AND name = %s
            ORDER BY createtime ASC
        """
        params = satellites + [start_time, end_time, param_name]
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    logger.info(f"查询到 {len(rows)} 条记录")
    return rows

def parse_createtime_to_second(ts_str):
    """
    解析时间字符串，忽略毫秒，返回 datetime 对象（秒级精度）
    支持格式：
    - '%Y-%m-%d %H:%M:%S'
    - '%Y-%m-%d %H:%M:%S.%f'
    """
    # 如果包含小数点，截取到秒
    if '.' in ts_str:
        ts_str = ts_str.split('.')[0]
    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

def check_second_jump(rows):
    """
    检查参数值是否每秒增加1（忽略毫秒，只比较秒级时间差）
    相邻两条记录：
        时间差 = (当前时间 - 前一条时间).total_seconds()（此时为整数秒差）
        工程值差 = 当前工程值 - 前一条工程值
    如果 工程值差 > 时间差 + 0.5，视为异常。
    返回异常记录列表。
    """
    if len(rows) < 2:
        return []
    abnormal = []
    prev_row = rows[0]
    for i in range(1, len(rows)):
        cur_row = rows[i]
        try:
            prev_val = int(prev_row["rvalval"])
            cur_val = int(cur_row["rvalval"])
        except (ValueError, TypeError):
            prev_val = 0
            cur_val = 0
        try:
            prev_time = parse_createtime_to_second(prev_row["createtime"])
            cur_time = parse_createtime_to_second(cur_row["createtime"])
        except Exception as e:
            logger.warning(f"时间解析失败: {e}，跳过该记录")
            prev_row = cur_row
            continue
        time_diff = (cur_time - prev_time).total_seconds()   # 整数秒差
        val_diff = cur_val - prev_val
        # 允许小误差：工程值增加应该约等于时间差（每秒+1）
        if val_diff > time_diff + 0.5:
            abnormal.append({
                "卫星名称": cur_row["starname"],
                "遥测参数名称": cur_row["name"],
                "遥测参数代码": cur_row["tmcode"],
                "工程值": cur_row["rvalval"],
                "系统接收时间": cur_row["createtime"]
            })
        prev_row = cur_row
    return abnormal

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON string containing parameters")
    args = parser.parse_args()
    try:
        inp = json.loads(args.json)
    except Exception as e:
        print(json.dumps({"status":"error","data":[],"summary":f"JSON解析失败: {e}"}))
        return

    # 处理卫星名称中的空格
    if "satellites" in inp:
        inp["satellites"] = normalize_satellites(inp["satellites"])

    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    param_name = inp.get("param_name")
    param_code = inp.get("param_code")
    # 允许动态传入数据库配置
    db_config = inp.get("db_config", DB_CONFIG)

    if not satellites or not start_time or not end_time:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数: satellites, start_time, end_time"}))
        return

    if not param_name and not param_code:
        print(json.dumps({"status":"error","data":[],"summary":"缺少 param_name 或 param_code"}))
        return

    try:
        rows = fetch_data(db_config, satellites, start_time, end_time, param_name, param_code)
        if not rows:
            print(json.dumps({"status":"success","data":[],"summary":"未查询到数据"}))
            return
        abnormal = check_second_jump(rows)
        summary = f"发现 {len(abnormal)} 处跳变异常（工程值增长大于时间差）"
        print(json.dumps({"status":"success","data":abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("执行失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()