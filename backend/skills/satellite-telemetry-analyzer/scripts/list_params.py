#!/usr/bin/env python3
import sys, json, pymysql, logging, argparse
from common_db import DB_CONFIG, normalize_satellites

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def get_parameters(satellites=None, start_time=None, end_time=None):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    sql = "SELECT DISTINCT starname, name, tmcode FROM tminfo WHERE 1=1"
    params = []
    if satellites:
        placeholders = ','.join(['%s'] * len(satellites))
        sql += f" AND starname IN ({placeholders})"
        params.extend(satellites)
    if start_time:
        sql += " AND createtime >= %s"
        params.append(start_time)
    if end_time:
        sql += " AND createtime <= %s"
        params.append(end_time)
    sql += " ORDER BY starname, name"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="JSON string containing parameters")
    args = parser.parse_args()
    try:
        inp = json.loads(args.json)
    except Exception as e:
        print(json.dumps({"status":"error","data":[],"summary":f"JSON解析失败: {e}"}))
        return
    try:
        # 自动去除卫星名称中的空格
        inp["satellites"] = normalize_satellites(inp.get("satellites"))
        data = get_parameters(inp.get("satellites"), inp.get("start_time"), inp.get("end_time"))
        print(json.dumps({"status":"success","data":data,"summary":f"共{len(data)}个参数"}))
    except Exception as e:
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()