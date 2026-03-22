#!/usr/bin/env python3
"""
多Agent框架测试脚本

测试场景：
1. 查看Agent列表状态
2. 创建协同任务
3. 查询任务状态
4. 测试Agent匹配
5. 模拟任务执行和响应

使用方法：
python test_multi_agents.py
"""
import json
import sys
import time
from pathlib import Path

import requests

# 添加后端目录到路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# API 基础地址
API_BASE = "http://localhost:8002"


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def test_api_connection():
    """测试API连接"""
    print_section("测试 1: API 连接检查")
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            print("✓ 后端服务连接正常")
            return True
        else:
            print("✗ 后端服务响应异常")
            return False
    except Exception as e:
        print(f"✗ 无法连接后端服务: {e}")
        print("  请确保后端服务已启动: python app.py")
        return False


def test_list_agents():
    """测试Agent列表"""
    print_section("测试 2: 获取Agent列表")
    try:
        response = requests.get(f"{API_BASE}/api/agents")
        data = response.json()

        if data.get("code") == 200:
            agents = data.get("data", [])
            print(f"✓ 获取到 {len(agents)} 个Agent:\n")

            for agent in agents:
                status_icon = {"running": "🟢", "idle": "🔵", "busy": "🟡", "stopped": "🔴"}.get(agent["status"], "⚪")

                print(f"  {status_icon} {agent['agent_name']}")
                print(f"      类型: {agent['agent_type']}")
                print(f"      状态: {agent['status']}")
                print(f"      技能: {', '.join(agent['skills'])}")
                print()

            return agents
        else:
            print(f"✗ 获取Agent列表失败: {data}")
            return []
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return []


def test_create_task(task_content, target_agent=None, task_type=None):
    """测试创建任务"""
    print_section("测试 3: 创建协同任务")

    payload = {"task_content": task_content}
    if target_agent:
        payload["target_agent"] = target_agent
    if task_type:
        payload["task_type"] = task_type

    print(f"任务内容: {task_content}")
    if target_agent:
        print(f"目标Agent: {target_agent}")
    if task_type:
        print(f"任务类型: {task_type}")
    print()

    try:
        response = requests.post(f"{API_BASE}/api/coordination/tasks", json=payload)
        data = response.json()

        if data.get("code") == 200:
            task_id = data["data"]["task_id"]
            print(f"✓ 任务创建成功!")
            print(f"  任务ID: {task_id}")
            print(f"  分配Agent: {data['data']['target_agent']}")
            return task_id
        else:
            print(f"✗ 创建任务失败: {data}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return None


def test_query_task(task_id):
    """测试查询任务"""
    print_section("测试 4: 查询任务状态")

    try:
        response = requests.get(f"{API_BASE}/api/coordination/tasks?task_id={task_id}")
        data = response.json()

        if data.get("code") == 200:
            task = data.get("data", {})
            print(f"✓ 任务信息:\n")
            print(f"  任务ID: {task.get('task_id')}")
            print(f"  状态: {task.get('status')}")
            print(f"  目标Agent: {task.get('target_agent')}")
            print(f"  任务类型: {task.get('task_type')}")
            print(f"  创建时间: {task.get('created_at')}")
            print(f"  内容: {task.get('content', '')[:100]}...")
            return task
        else:
            print(f"✗ 查询失败: {data}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return None


def test_update_task_status(task_id, status):
    """测试更新任务状态"""
    print_section("测试 5: 更新任务状态")

    print(f"任务ID: {task_id}")
    print(f"新状态: {status}")
    print()

    try:
        response = requests.put(f"{API_BASE}/api/coordination/tasks/{task_id}/status?status={status}")
        data = response.json()

        if data.get("code") == 200:
            print(f"✓ 状态更新成功!")
            return True
        else:
            print(f"✗ 更新失败: {data}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False


def test_coordination_snapshot():
    """测试获取协同快照"""
    print_section("测试 6: 获取协同状态快照")

    try:
        response = requests.get(f"{API_BASE}/api/coordination/snapshot")
        data = response.json()

        if data.get("code") == 200:
            print("✓ 协同状态快照:\n")
            print(data["data"]["content"])
            return True
        else:
            print(f"✗ 获取失败: {data}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False


def test_agent_control(agent_name, action):
    """测试Agent控制（启停）"""
    print_section("测试 7: Agent启停控制")

    print(f"Agent: {agent_name}")
    print(f"操作: {action}")
    print()

    try:
        response = requests.post(f"{API_BASE}/api/agents/control", json={"agent_name": agent_name, "action": action})
        data = response.json()

        if data.get("success"):
            print(f"✓ 操作成功!")
            print(f"  新状态: {data['new_status']}")
            return True
        else:
            print(f"✗ 操作失败: {data}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return False


def test_list_all_tasks():
    """测试列出所有任务"""
    print_section("测试 8: 列出所有任务")

    try:
        response = requests.get(f"{API_BASE}/api/coordination/tasks")
        data = response.json()

        if data.get("code") == 200:
            tasks = data.get("data", [])
            print(f"✓ 当前任务数: {len(tasks)}\n")

            for task in tasks:
                status_icon = {"pending": "⏳", "processing": "🔄", "finished": "✅", "failed": "❌"}.get(
                    task["status"], "❓"
                )

                print(f"  {status_icon} {task['task_id']}")
                print(f"      状态: {task['status']}")
                print(f"      Agent: {task['target_agent']}")
                print()

            return tasks
        else:
            print(f"✗ 获取失败: {data}")
            return []
    except Exception as e:
        print(f"✗ 请求失败: {e}")
        return []


def run_full_test_scenario():
    """运行完整测试场景"""
    print("\n" + "🚀" * 25)
    print("  多Agent框架完整测试场景")
    print("🚀" * 25)

    # 1. 测试连接
    if not test_api_connection():
        return

    # 2. 获取Agent列表
    agents = test_list_agents()
    if not agents:
        print("警告: 没有可用的Agent")

    # 3. 创建数据处理任务（自动匹配data_agent）
    task_id_1 = test_create_task(
        task_content="分析销售数据，生成月度报告。数据包含CSV格式的销售记录，需要计算总销售额、平均值和趋势分析。", task_type="data_processing"
    )

    # 4. 创建文档分析任务（自动匹配doc_agent）
    task_id_2 = test_create_task(task_content="解析PDF文档，提取关键信息并生成摘要。文档包含产品规格说明书。", task_type="document_analysis")

    # 5. 创建指定Agent的任务
    task_id_3 = test_create_task(
        task_content="执行Python数据分析脚本，计算统计数据。", target_agent="data_agent", task_type="data_analysis"
    )

    # 6. 查询任务状态
    if task_id_1:
        test_query_task(task_id_1)

    # 7. 更新任务状态（模拟执行中）
    if task_id_1:
        test_update_task_status(task_id_1, "processing")
        time.sleep(1)

    # 8. 再次查询确认状态已更新
    if task_id_1:
        test_query_task(task_id_1)

    # 9. 完成任务
    if task_id_1:
        test_update_task_status(task_id_1, "finished")

    # 10. 列出所有任务
    test_list_all_tasks()

    # 11. 获取协同快照
    test_coordination_snapshot()

    # 12. 测试Agent控制（仅对domain agent）
    print("\n提示: 仅测试启停功能，不影响primary和coordinator")
    test_agent_control("data_agent", "stop")
    time.sleep(1)
    test_agent_control("data_agent", "start")

    # 最终状态
    print_section("测试完成 - 最终状态")
    test_list_agents()
    test_list_all_tasks()

    print("\n" + "✨" * 25)
    print("  所有测试完成!")
    print("✨" * 25)


def quick_test():
    """快速测试"""
    print("\n🔄 快速测试模式\n")

    if not test_api_connection():
        return

    test_list_agents()
    test_list_all_tasks()
    test_coordination_snapshot()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="多Agent框架测试脚本")
    parser.add_argument("--quick", action="store_true", help="快速测试模式")
    parser.add_argument("--full", action="store_true", help="完整测试模式")

    args = parser.parse_args()

    if args.quick:
        quick_test()
    elif args.full:
        run_full_test_scenario()
    else:
        # 默认运行完整测试
        run_full_test_scenario()
