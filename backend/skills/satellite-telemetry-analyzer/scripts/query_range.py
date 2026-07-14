#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, pymysql, logging, argparse
from common_db import DB_CONFIG, normalize_satellites

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

def check_condition(value, cond):
    try:
        v = float(value)
    except:
        return False
    op = cond.get("operator")
    if op == "<":
        return v < cond["value"]
    elif op == "<=":
        return v <= cond["value"]
    elif op == ">":
        return v > cond["value"]
    elif op == ">=":
        return v >= cond["value"]
    elif op in ("==", "="):
        return v == cond["value"]
    elif op == "between":
        return cond["min"] <= v <= cond["max"]
    return False

def build_metrics_condition(metrics):
    if not metrics:
        return "", []
    conditions = []
    params = []
    for m in metrics:
        if isinstance(m, str):
            conditions.append("(name = %s)")
            params.append(m)
        elif isinstance(m, dict):
            typ = m.get("type")
            val = m.get("value")
            if typ == "name":
                conditions.append("(name = %s)")
                params.append(val)
            elif typ == "code":
                conditions.append("(tmcode = %s)")
                params.append(val)
            else:
                continue
        else:
            continue
    if not conditions:
        return "", []
    return " AND (" + " OR ".join(conditions) + ")", params

def build_extra_conditions_sql(extra_conditions):
    if not extra_conditions:
        return "", []
    subs = []
    params = []
    for ec in extra_conditions:
        name = ec.get("name")
        value = ec.get("value")
        if not name:
            continue
        subs.append(f"""
            EXISTS (
                SELECT 1 FROM tminfo t_inner
                WHERE t_inner.starname = tmain.starname
                  AND t_inner.createtime = tmain.createtime
                  AND t_inner.name = %s
                  AND t_inner.rvalval = %s
            )
        """)
        params.extend([name, value])
    if not subs:
        return "", []
    return " AND " + " AND ".join(subs), params

def query_and_check(satellites, start_time, end_time, metrics, condition, extra_conditions):
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    sat_ph = ','.join(['%s'] * len(satellites))
    base_sql = f"""
        SELECT starname, name, tmcode, rvalval, createtime
        FROM tminfo tmain
        WHERE starname IN ({sat_ph})
          AND createtime >= %s AND createtime < %s
    """
    params = satellites + [start_time, end_time]

    metrics_cond, metrics_params = build_metrics_condition(metrics)
    if not metrics_cond:
        raise ValueError("没有有效的指标条件")
    base_sql += metrics_cond
    params.extend(metrics_params)

    extra_cond, extra_params = build_extra_conditions_sql(extra_conditions)
    base_sql += extra_cond
    params.extend(extra_params)

    base_sql += " ORDER BY createtime ASC"
    logger.info(f"执行 SQL: {base_sql}")
    cursor.execute(base_sql, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # 只返回满足异常条件的原始记录（五个字段），不加额外说明
    abnormal = []
    for r in rows:
        if check_condition(r["rvalval"], condition):
            abnormal.append({
                "卫星名称": r["starname"],
                "遥测参数名称": r["name"],
                "遥测参数": r["tmcode"],
                "工程值": r["rvalval"],
                "系统接收时间": r["createtime"]
            })
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
    inp["satellites"] = normalize_satellites(inp.get("satellites"))
    satellites = inp.get("satellites", [])
    start_time = inp.get("start_time")
    end_time = inp.get("end_time")
    metrics = inp.get("metrics", [])
    condition = inp.get("condition")
    extra_conditions = inp.get("extra_conditions", [])

    if not satellites or not start_time or not end_time or not metrics or condition is None:
        print(json.dumps({"status":"error","data":[],"summary":"缺少必要参数"}))
        return

    try:
        abnormal = query_and_check(satellites, start_time, end_time, metrics, condition, extra_conditions)
        summary = f"发现{len(abnormal)}条异常"
        print(json.dumps({"status":"success","data":abnormal,"summary":summary}, ensure_ascii=False))
    except Exception as e:
        logger.exception("查询失败")
        print(json.dumps({"status":"error","data":[],"summary":str(e)}))

if __name__ == "__main__":
    main()