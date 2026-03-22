"""
协同工具 - Agent间协同操作的核心工具
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from graph.coordinator import get_coordination_manager


class CreateTaskInput(BaseModel):
    """创建任务输入参数"""
    task_content: str = Field(description="任务内容描述")
    target_agent: Optional[str] = Field(default=None, description="目标Agent名称，不指定则自动匹配")
    task_type: Optional[str] = Field(default=None, description="任务类型：data_processing, document_analysis等")


class CreateTaskTool(BaseTool):
    """创建协同任务工具"""

    name: str = "create_task"
    description: str = """创建一个协同任务，分发给其他Agent执行。
输入参数：
- task_content: 任务内容描述
- target_agent: 目标Agent名称（可选，不指定则自动匹配）
- task_type: 任务类型（可选，用于自动匹配Agent）

使用场景：
- 需要其他Agent协助完成任务时
- 复杂任务需要拆分执行时"""
    args_schema: Type[BaseModel] = CreateTaskInput

    def _run(
        self,
        task_content: str,
        target_agent: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        task_id = coordinator.create_task(
            task_content=task_content,
            target_agent=target_agent,
            task_type=task_type,
        )

        return f"任务已创建：{task_id}\n目标Agent：{target_agent or '自动匹配'}\n可使用 query_task 查询任务状态"

    async def _arun(
        self,
        task_content: str,
        target_agent: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> str:
        """异步执行"""
        return self._run(task_content, target_agent, task_type)


class QueryTaskInput(BaseModel):
    """查询任务输入参数"""
    task_id: str = Field(description="任务ID")


class QueryTaskTool(BaseTool):
    """查询任务状态工具"""

    name: str = "query_task"
    description: str = """查询协同任务的状态和结果。
输入参数：
- task_id: 任务ID

返回信息：
- 任务状态：pending/processing/finished/failed
- 执行结果：如果任务已完成"""
    args_schema: Type[BaseModel] = QueryTaskInput

    def _run(self, task_id: str) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        task = coordinator.get_task(task_id)
        if not task:
            return f"错误：任务不存在 - {task_id}"

        result = f"""任务ID：{task['task_id']}
状态：{task['status']}
目标Agent：{task['target_agent']}
创建时间：{task['created_at']}
更新时间：{task['updated_at']}
"""
        if task['status'] == 'finished':
            # 查找响应文件
            response_id = f"RESPONSE_{task_id.replace('TASK_', '')}"
            response_file = coordinator.responses_dir / f"{response_id}.md"
            if response_file.exists():
                result += f"\n执行结果：\n{response_file.read_text(encoding='utf-8')}"

        return result

    async def _arun(self, task_id: str) -> str:
        """异步执行"""
        return self._run(task_id)


class ListAgentsTool(BaseTool):
    """列出所有Agent工具"""

    name: str = "list_agents"
    description: str = """列出所有可用的Agent及其状态。
返回信息：
- Agent名称
- Agent类型
- 当前状态
- 可用技能"""

    def _run(self) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        agents = coordinator.list_agents()
        if not agents:
            return "当前无可用Agent"

        lines = ["可用Agent列表：", ""]
        for agent in agents:
            lines.append(f"- {agent['agent_name']} ({agent['agent_type']})")
            lines.append(f"  状态：{agent['status']}")
            lines.append(f"  技能：{', '.join(agent['skills'])}")
            lines.append("")

        return "\n".join(lines)

    async def _arun(self) -> str:
        """异步执行"""
        return self._run()


class CreateResponseInput(BaseModel):
    """创建响应输入参数"""
    task_id: str = Field(description="任务ID")
    result: str = Field(description="执行结果")
    files: Optional[List[str]] = Field(default=None, description="生成的文件路径列表")


class CreateResponseTool(BaseTool):
    """创建任务响应工具"""

    name: str = "create_response"
    description: str = """创建任务响应，报告执行结果。
输入参数：
- task_id: 任务ID
- result: 执行结果描述
- files: 生成的文件路径列表（可选）

使用场景：
- Domain Agent完成任务后报告结果"""
    args_schema: Type[BaseModel] = CreateResponseInput

    agent_name: str = "unknown_agent"

    def _run(
        self,
        task_id: str,
        result: str,
        files: Optional[List[str]] = None,
    ) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        response_id = coordinator.create_response(
            task_id=task_id,
            result=result,
            agent_name=self.agent_name,
            files=files,
        )

        return f"响应已创建：{response_id}\n任务状态已更新为 finished"

    async def _arun(
        self,
        task_id: str,
        result: str,
        files: Optional[List[str]] = None,
    ) -> str:
        """异步执行"""
        return self._run(task_id, result, files)


class QueryCoordinationInput(BaseModel):
    """查询协同状态输入参数"""
    query_type: str = Field(description="查询类型：agents/tasks/snapshot")


class QueryCoordinationTool(BaseTool):
    """查询协同状态工具"""

    name: str = "query_coordination"
    description: str = """查询多Agent协同状态。
输入参数：
- query_type: 查询类型
  - agents: 所有Agent状态
  - tasks: 所有任务状态
  - snapshot: 协同状态快照"""
    args_schema: Type[BaseModel] = QueryCoordinationInput

    def _run(self, query_type: str) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        if query_type == "agents":
            agents = coordinator.list_agents()
            return json.dumps(agents, ensure_ascii=False, indent=2)

        elif query_type == "tasks":
            tasks = coordinator.list_tasks()
            return json.dumps(tasks, ensure_ascii=False, indent=2)

        elif query_type == "snapshot":
            snapshot_file = coordinator.coordination_dir / "COORDINATION_SNAPSHOT.md"
            if snapshot_file.exists():
                return snapshot_file.read_text(encoding="utf-8")
            return "协同状态快照不存在"

        else:
            return f"错误：未知的查询类型 - {query_type}"

    async def _arun(self, query_type: str) -> str:
        """异步执行"""
        return self._run(query_type)


class WriteFileInput(BaseModel):
    """写入文件输入参数"""
    path: str = Field(description="文件路径（相对于协同目录）")
    content: str = Field(description="文件内容")


class WriteFileTool(BaseTool):
    """写入文件工具（仅协同目录）"""

    name: str = "write_file"
    description: str = """将内容写入协同目录下的文件。
输入参数：
- path: 文件路径（相对于协同目录）
- content: 文件内容

注意：仅能在coordination目录下操作文件"""
    args_schema: Type[BaseModel] = WriteFileInput

    root_dir: Path = None

    def __init__(self, root_dir: Path = None, **kwargs):
        super().__init__(**kwargs)
        self.root_dir = root_dir

    def _run(self, path: str, content: str) -> str:
        """同步执行"""
        coordinator = get_coordination_manager()
        if not coordinator:
            return "错误：协同管理器未初始化"

        # 安全检查：确保路径在协同目录内
        if ".." in path or path.startswith("/"):
            return "错误：非法路径"

        # 限制在协同目录内
        full_path = coordinator.coordination_dir / path

        # 确保父目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            full_path.write_text(content, encoding="utf-8")
            return f"文件已保存：{path}"
        except Exception as e:
            return f"错误：写入失败 - {str(e)}"

    async def _arun(self, path: str, content: str) -> str:
        """异步执行"""
        return self._run(path, content)


# 工具创建函数
def create_task_tool() -> CreateTaskTool:
    """创建任务工具"""
    return CreateTaskTool()


def query_task_tool() -> QueryTaskTool:
    """查询任务工具"""
    return QueryTaskTool()


def list_agents_tool() -> ListAgentsTool:
    """列出Agent工具"""
    return ListAgentsTool()


def create_response_tool(agent_name: str) -> CreateResponseTool:
    """创建响应工具"""
    tool = CreateResponseTool()
    tool.agent_name = agent_name
    return tool


def query_coordination_tool() -> QueryCoordinationTool:
    """查询协同状态工具"""
    return QueryCoordinationTool()


def write_file_tool(root_dir: Path = None) -> WriteFileTool:
    """创建写入文件工具"""
    return WriteFileTool(root_dir=root_dir)


def get_coordination_tools() -> List[BaseTool]:
    """获取所有协同工具"""
    return [
        create_task_tool(),
        query_task_tool(),
        list_agents_tool(),
        query_coordination_tool(),
    ]