#!/usr/bin/env python3
"""
会议行动项自动跟踪脚本
"""
import json
import sys
from datetime import datetime

def update_tracker(task_description, owner, deadline, deliverable, status="未开始"):
    """将新的行动项更新至总跟踪表"""
    new_task = {
        "task": task_description,
        "owner": owner,
        "deadline": deadline,
        "deliverable": deliverable,
        "status": status,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    # 此处逻辑为将new_task追加到团队的跟踪表格（如CSV文件或数据库）
    # 示例中仅打印结果
    print(f"任务已更新至跟踪器：{json.dumps(new_task, ensure_ascii=False)}")

if __name__ == "__main__":
    # 通过命令行参数接收任务信息
    update_tracker(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
