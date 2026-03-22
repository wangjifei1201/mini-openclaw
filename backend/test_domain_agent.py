#!/usr/bin/env python3
"""
Domain Agent 执行测试

演示 Domain Agent 如何真正执行任务
"""
import asyncio
import sys
from pathlib import Path

# 添加后端目录到路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from config import settings
from graph.coordinator import get_coordination_manager, init_coordination_manager
from graph.streaming_adapter import StreamingToolCallAdapter
from graph.task_dispatcher import TaskDispatcher, should_dispatch_to_domain_agent


async def test_domain_agent_execution():
    """测试 Domain Agent 真正执行任务"""

    print("=" * 60)
    print("  Domain Agent 执行测试")
    print("=" * 60)

    # 初始化
    init_coordination_manager(BASE_DIR)
    coordinator = get_coordination_manager()

    # 创建 LLM 实例
    print("\n[1] 初始化 LLM...")
    llm = StreamingToolCallAdapter(
        model=settings.OPENAI_CHAT_MODEL,
        api_key=settings.OPENAI_CHAT_API_KEY,
        base_url=settings.OPENAI_CHAT_BASE_URL,
        temperature=0.7,
        streaming=True,
    )
    print(f"    模型: {settings.OPENAI_CHAT_MODEL}")

    # 创建任务分发器
    dispatcher = TaskDispatcher(BASE_DIR, llm)

    # 测试任务
    test_tasks = [
        {
            "message": "请帮我计算 1 到 100 的所有整数之和，并给出计算过程",
            "expected_agent": "data_agent",
        },
        {
            "message": "帮我写一个Python函数，实现斐波那契数列",
            "expected_agent": "data_agent",
        },
    ]

    print("\n[2] 开始测试任务分发...\n")

    for i, task in enumerate(test_tasks, 1):
        print(f"\n--- 测试任务 {i} ---")
        print(f"消息: {task['message']}")

        # 分析任务
        analysis = dispatcher.analyze_task(task['message'])
        print(f"\n任务分析:")
        print(f"  需要分发: {analysis['need_dispatch']}")
        print(f"  任务类型: {analysis['task_type']}")
        print(f"  目标Agent: {analysis['target_agent']}")

        if analysis['need_dispatch'] and analysis['target_agent']:
            print(f"\n[执行] 调用 {analysis['target_agent']} 执行任务...")
            print("-" * 40)

            try:
                # 执行任务
                async for event in dispatcher.dispatch_task(
                    task_content=task['message'],
                    target_agent=analysis['target_agent'],
                ):
                    if event['type'] == 'dispatch_start':
                        print(f"\n🚀 {event['content']}")
                    elif event['type'] == 'token':
                        print(event['content'], end='', flush=True)
                    elif event['type'] == 'dispatch_end':
                        print(f"\n\n✅ 任务完成!")
                    elif event['type'] == 'dispatch_error':
                        print(f"\n❌ 任务失败: {event['error']}")
            except Exception as e:
                print(f"\n❌ 执行出错: {e}")
                print("   可能需要配置有效的 LLM API Key")
        else:
            print("\n任务不需要分发，由 Primary Agent 处理")

    # 最终状态
    print("\n" + "=" * 60)
    print("  最终状态")
    print("=" * 60)

    agents = coordinator.list_agents()
    print("\nAgent 状态:")
    for agent in agents:
        print(f"  - {agent['agent_name']}: {agent['status']}")

    tasks = coordinator.list_tasks()
    print(f"\n任务记录: {len(tasks)} 个")
    for task in tasks[-3:]:
        print(f"  - {task['task_id']}: {task['status']}")


def test_task_analysis():
    """测试任务分析功能"""

    print("\n" + "=" * 60)
    print("  任务分析测试 (不需要 LLM)")
    print("=" * 60)

    test_messages = [
        "帮我分析这份销售数据，生成月度报告",
        "请解析这个PDF文档并提取关键信息",
        "计算这些数据的平均值和标准差",
        "把Word文档转换成Markdown格式",
        "今天天气怎么样？",
        "你好，请介绍一下你自己",
    ]

    print("\n测试消息 -> 分析结果:\n")

    for msg in test_messages:
        analysis = should_dispatch_to_domain_agent(msg)

        print(f"📝 {msg[:30]}...")
        if analysis['need_dispatch']:
            print(f"   → 分发给: {analysis['target_agent']} ({analysis['task_type']})")
        else:
            print(f"   → 由 Primary Agent 处理")
        print()


async def main():
    """主函数"""

    # 先测试任务分析（不需要LLM）
    test_task_analysis()

    # 询问是否继续测试实际执行
    print("\n" + "-" * 60)
    response = input("是否继续测试 Domain Agent 实际执行? (需要配置LLM) [y/N]: ")

    if response.lower() == 'y':
        await test_domain_agent_execution()
    else:
        print("\n跳过实际执行测试。")
        print("提示: 要测试实际执行，请确保配置了有效的 LLM API Key")


if __name__ == "__main__":
    asyncio.run(main())
