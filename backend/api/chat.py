"""
聊天 API - SSE 流式对话

支持两种执行模式：
1. 单Agent模式 - 直接使用 AgentManager 执行
2. 多Agent模式 - 通过策略分析决定是否分发给 Domain Agent
"""
import json
import time
from typing import Optional

from config import get_multi_agent_mode
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from graph import agent_manager
from graph.llm_task_planner import get_task_planner
from graph.task_dispatcher import get_task_dispatcher
from graph.task_executor import get_task_executor
from pydantic import BaseModel
from utils.token_tracker import estimate_tokens, get_token_tracker

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""

    message: str
    session_id: str
    stream: bool = True


async def _multi_agent_generator(
    message: str,
    session_id: str,
    plan,
    is_first_message: bool,
):
    """
    多Agent执行的SSE事件生成器

    编排 TaskExecutor + TaskDispatcher + TokenTracker 的完整流程。
    遍历 todos 串行执行，每个 todo 委托给对应的 Agent。

    Args:
        message: 用户消息
        session_id: 会话ID
        plan: ExecutionPlan from LLMTaskPlanner
        is_first_message: 是否为首条消息
    """
    task_executor = get_task_executor()
    task_dispatcher = get_task_dispatcher()
    tracker = get_token_tracker()

    # Step 1: 发送策略决策事件
    first_domain_agent = next(
        (t.agent_name for t in plan.todos if t.agent_name != "primary_agent"),
        None,
    )
    yield {
        "type": "strategy_decided",
        "strategy": plan.strategy,
        "task_type": "multi_agent",
        "target_agent": first_domain_agent,
        "confidence": plan.confidence,
        "reason": plan.reason,
        "sub_tasks": None,
    }

    # Step 2: 创建任务（使用 LLM 生成的 plan）
    task_id = task_executor.create_task_from_plan(message, plan, session_id)
    task_info = task_executor.get_task(task_id)
    todos = task_info.get("todos", []) if task_info else []

    # 启动 Token 追踪
    tracker.start_task(task_id)

    # 动态初始化 agent_status（从 plan 提取涉及的 agent）
    involved_agents = set(t.agent_name for t in plan.todos)
    involved_agents.add("coordinator_agent")
    agent_status = {agent: "idle" for agent in involved_agents}
    agent_status["coordinator_agent"] = "processing"

    yield {
        "type": "task_created",
        "task_id": task_id,
        "message": message,
        "todos": todos,
        "agent_status": agent_status,
    }

    # Step 3: 遍历 todos 串行执行
    all_content = ""
    all_tool_calls = []
    last_stats_time = time.time()

    try:
        for todo in todos:
            todo_id = todo["id"]
            todo_agent = todo.get("agent", "primary_agent")

            # 更新 todo 状态为 in_progress
            task_executor.update_todo_status(task_id, todo_id, "in_progress")
            yield {
                "type": "todo_update",
                "task_id": task_id,
                "todo_id": todo_id,
                "old_status": "pending",
                "new_status": "in_progress",
                "agent": todo_agent,
            }

            # 更新 agent 状态
            old_agent_status = agent_status.get(todo_agent, "idle")
            agent_status[todo_agent] = "processing"
            yield {
                "type": "agent_status",
                "task_id": task_id,
                "agent_name": todo_agent,
                "old_status": old_agent_status,
                "new_status": "processing",
            }

            # 执行 todo
            todo_content = ""
            todo_result = ""

            try:
                if todo_agent != "primary_agent" and task_dispatcher:
                    # Domain Agent 执行
                    task_prompt = f"任务: {todo.get('content', message)}\n\n原始用户请求: {message}"
                    async for event in task_dispatcher.dispatch_task(
                        task_content=task_prompt,
                        target_agent=todo_agent,
                        task_id=task_id,
                        session_id=session_id,
                    ):
                        event_type = event.get("type", "")

                        if event_type == "token":
                            content = event.get("content", "")
                            todo_content += content
                            all_content += content
                            yield event

                        elif event_type in ("tool_start", "tool_end", "new_response"):
                            if event_type == "tool_end":
                                all_tool_calls.append(
                                    {
                                        "tool": event.get("tool", ""),
                                        "input": event.get("input", ""),
                                        "output": event.get("output", ""),
                                    }
                                )
                            yield event

                        elif event_type == "dispatch_end":
                            todo_result = event.get("result", todo_content)

                        elif event_type == "dispatch_error":
                            error_msg = event.get("error", "Unknown error")
                            yield {
                                "type": "error",
                                "error": f"[{todo_agent}] {error_msg}",
                                "agent_name": todo_agent,
                            }
                            todo_result = f"Error: {error_msg}"

                else:
                    # Primary Agent 执行
                    todo_prompt = f"{todo.get('content', message)}\n\n原始用户请求: {message}"

                    # 估算输入 token
                    estimated_input = estimate_tokens(todo_prompt)

                    async for event in agent_manager.astream(todo_prompt, session_id):
                        event_type = event.get("type", "")

                        if event_type == "token":
                            content = event.get("content", "")
                            todo_content += content
                            all_content += content
                            # 附加 agent_name
                            event["agent_name"] = "primary_agent"
                            event["task_id"] = task_id
                            yield event

                        elif event_type in ("tool_start", "tool_end"):
                            event["agent_name"] = "primary_agent"
                            event["task_id"] = task_id
                            if event_type == "tool_end":
                                all_tool_calls.append(
                                    {
                                        "tool": event.get("tool", ""),
                                        "input": event.get("input", ""),
                                        "output": event.get("output", ""),
                                    }
                                )
                                # 记录工具调用
                                tracker.record_tool_call(
                                    event.get("tool", "unknown"),
                                    task_id,
                                    "primary_agent",
                                )
                            yield event

                        elif event_type == "new_response":
                            event["agent_name"] = "primary_agent"
                            yield event

                        elif event_type == "done":
                            todo_result = event.get("content", todo_content)
                            # 记录 LLM 调用
                            estimated_output = estimate_tokens(todo_content)
                            tracker.record_llm_call(
                                agent="primary_agent",
                                input_tokens=estimated_input,
                                output_tokens=estimated_output,
                                task_id=task_id,
                            )

                        elif event_type == "error":
                            event["agent_name"] = "primary_agent"
                            yield event
                            todo_result = f"Error: {event.get('error', '')}"

                # Todo 完成
                task_executor.update_todo_status(task_id, todo_id, "completed", todo_result)
                yield {
                    "type": "todo_update",
                    "task_id": task_id,
                    "todo_id": todo_id,
                    "old_status": "in_progress",
                    "new_status": "completed",
                    "agent": todo_agent,
                    "result": (todo_result[:200] + "...") if len(todo_result) > 200 else todo_result,
                }

            except Exception as e:
                # Todo 执行失败，标记为 failed 但不中断整个流程
                error_msg = str(e)
                task_executor.update_todo_status(task_id, todo_id, "failed", error_msg)
                yield {
                    "type": "todo_update",
                    "task_id": task_id,
                    "todo_id": todo_id,
                    "old_status": "in_progress",
                    "new_status": "failed",
                    "agent": todo_agent,
                    "result": error_msg,
                }

            # 恢复 agent 状态
            agent_status[todo_agent] = "idle"
            yield {
                "type": "agent_status",
                "task_id": task_id,
                "agent_name": todo_agent,
                "old_status": "busy",
                "new_status": "idle",
            }

            # 限频发送 stats_update（每个 todo 完成后强制发送）
            stats = tracker.get_task_stats(task_id)
            if stats:
                yield {
                    "type": "stats_update",
                    "task_id": task_id,
                    **stats,
                }
                last_stats_time = time.time()

        # Step 4: 任务完成
        task_executor.complete_task(task_id, all_content[:500] if all_content else "")

        final_stats = tracker.get_task_stats(task_id)
        yield {
            "type": "task_complete",
            "task_id": task_id,
            "summary": all_content[:500] if all_content else "",
            "final_stats": final_stats,
        }

        # 保存消息到 session
        agent_manager.session_manager.save_message(session_id, "user", message)
        agent_manager.session_manager.save_message(
            session_id, "assistant", all_content, all_tool_calls if all_tool_calls else None
        )

        # 发送 done 事件（保持与单Agent模式一致）
        yield {
            "type": "done",
            "content": all_content,
            "session_id": session_id,
            "tool_calls": all_tool_calls,
        }

        # 首条消息自动生成标题
        if is_first_message:
            try:
                title = await agent_manager.generate_title(message)
                agent_manager.session_manager.update_title(session_id, title)
                yield {
                    "type": "title",
                    "session_id": session_id,
                    "title": title,
                }
            except Exception:
                pass

    except Exception as e:
        # 整体任务失败
        task_executor.fail_task(task_id, str(e))
        yield {
            "type": "error",
            "error": f"多Agent任务执行失败: {str(e)}",
            "task_id": task_id,
        }


async def event_generator(message: str, session_id: str, is_first_message: bool):
    """
    SSE 事件生成器

    根据多Agent模式和策略分析结果，选择执行路径：
    - 多Agent模式 + MULTI策略 → _multi_agent_generator()
    - 其他情况 → 原有单Agent流程

    Args:
        message: 用户消息
        session_id: 会话ID
        is_first_message: 是否为首条消息
    """
    # 检查多Agent模式
    multi_agent_mode = get_multi_agent_mode()

    if multi_agent_mode:
        planner = get_task_planner()
        if planner:
            plan = await planner.plan_execution(message)

            if plan.strategy == "multi":
                # 多Agent执行路径
                async for event in _multi_agent_generator(message, session_id, plan, is_first_message):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                return
            else:
                # 单Agent但仍发送策略信息
                yield f"data: {json.dumps({'type': 'strategy_decided', 'strategy': 'single', 'task_type': None, 'target_agent': None, 'confidence': plan.confidence, 'reason': plan.reason, 'sub_tasks': None}, ensure_ascii=False)}\n\n"

    # ============ 原有单Agent流程（完全不变） ============
    # 记录响应段
    segments = []
    current_segment = ""
    current_tool_calls = []

    async for event in agent_manager.astream(message, session_id):
        event_type = event.get("type", "")

        # RAG 检索结果
        if event_type == "retrieval":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Token 输出
        elif event_type == "token":
            content = event.get("content", "")
            current_segment += content
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 工具调用开始
        elif event_type == "tool_start":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 工具调用结束
        elif event_type == "tool_end":
            current_tool_calls.append(
                {
                    "tool": event.get("tool", ""),
                    "input": event.get("input", ""),
                    "output": event.get("output", ""),
                }
            )
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 新响应段开始
        elif event_type == "new_response":
            # 保存当前段
            if current_segment:
                segments.append(
                    {
                        "content": current_segment,
                        "tool_calls": current_tool_calls.copy(),
                    }
                )
            current_segment = ""
            current_tool_calls = []
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 完成
        elif event_type == "done":
            # 保存最后一段
            final_content = event.get("content", "")
            if final_content or current_segment:
                segments.append(
                    {
                        "content": final_content or current_segment,
                        "tool_calls": event.get("tool_calls", []),
                    }
                )

            # 保存用户消息
            agent_manager.session_manager.save_message(session_id, "user", message)

            # 保存每段助手消息
            for seg in segments:
                agent_manager.session_manager.save_message(
                    session_id, "assistant", seg["content"], seg.get("tool_calls")
                )

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 首条消息自动生成标题
            if is_first_message:
                try:
                    title = await agent_manager.generate_title(message)
                    agent_manager.session_manager.update_title(session_id, title)
                    yield f"data: {json.dumps({'type': 'title', 'session_id': session_id, 'title': title}, ensure_ascii=False)}\n\n"
                except Exception:
                    pass

        # 错误
        elif event_type == "error":
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    聊天接口 - SSE 流式输出

    事件类型：
    - retrieval: RAG 检索结果
    - token: LLM 输出的 token
    - tool_start: 工具调用开始
    - tool_end: 工具调用结束
    - new_response: 新的响应段开始
    - done: 完成
    - title: 自动生成的标题（首条消息）
    - error: 错误

    多Agent模式额外事件：
    - strategy_decided: 策略决策结果
    - task_created: 任务创建
    - todo_update: Todo状态更新
    - agent_status: Agent状态变更
    - stats_update: 统计数据更新
    - task_complete: 任务完成
    """
    # 检查是否为首条消息
    history = agent_manager.session_manager.load_session(request.session_id)
    is_first_message = len(history) == 0

    if request.stream:
        return StreamingResponse(
            event_generator(request.message, request.session_id, is_first_message),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # 非流式响应
        full_content = ""
        tool_calls = []

        async for event in agent_manager.astream(request.message, request.session_id):
            if event.get("type") == "token":
                full_content += event.get("content", "")
            elif event.get("type") == "done":
                tool_calls = event.get("tool_calls", [])

        # 保存消息
        agent_manager.session_manager.save_message(request.session_id, "user", request.message)
        agent_manager.session_manager.save_message(request.session_id, "assistant", full_content, tool_calls)

        return {
            "content": full_content,
            "tool_calls": tool_calls,
            "session_id": request.session_id,
        }
