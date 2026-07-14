#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞轮转速跳变检测脚本

功能说明：
    根据卫星遥测数据，检测飞轮转速是否发生跳变。
    跳变判定规则：计算每个飞轮转速参数的稳定基准值（取前5个波动不超过1的窗口平均值），
    若后续转速值与基准值的相对偏差超过10%（|值-基准|/基准 > 0.1），则标记为跳变异常。

输入参数（JSON格式，通过 --json 传递）：
    {
        "satellites": ["高分07B01星"],           // 卫星名称数组（支持多星）
        "start_time": "2025-08-20 00:00:00",     // 起始时间（左闭）
        "end_time": "2025-08-20 10:00:00",       // 结束时间（右开）
        "metrics": ["飞轮1转速", "飞轮2转速", "飞轮3转速", "飞轮4转速"]   // 要检测的参数名称列表
    }

输出参数案例（成功）：
    {
        "status": "success",
        "data": [
            {
                "卫星编号": "高分07B01星",
                "参数名称": "飞轮4转速",
                "参数代码": "ZT-C089",
                "时间": "2025-08-20 09:15:23.456",
                "工程值": 1999.0,
                "基准值": 1800.0,
                "偏差比例": 0.1106,
                "异常说明": "转速跳变"
            }
        ],
        "summary": "发现1处跳变"
    }

输出参数案例（无数据）：
    {
        "status": "success",
        "data": [],
        "summary": "未查询到数据"
    }

输出参数案例（错误）：
    {
        "status": "error",
        "data": [],
        "summary": "缺少必要参数"
    }
"""
import sys, json, pymysql, logging, argparse
from typing import List, Dict, Optional
from common_db import DB_CONFIG, normalize_satellites

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
        AND createtime >= %s AND createtime < %s
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