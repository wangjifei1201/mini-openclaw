"""
协同管理器 - 多Agent协同调度核心
"""
import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import settings


class CoordinationManager:
    """
    协同管理器

    负责：
    1. 任务状态同步
    2. Agent匹配与调度
    3. 资源冲突解决
    4. 协同文件管理
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.coordination_dir = base_dir / "workspace" / "coordination"
        self.tasks_dir = self.coordination_dir / "tasks"
        self.responses_dir = self.coordination_dir / "responses"
        self.notices_dir = self.coordination_dir / "notices"
        self.global_memory_dir = base_dir / "workspace" / "global_memory"

        # 确保目录存在
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self.notices_dir.mkdir(parents=True, exist_ok=True)

        # Agent注册表
        self._agents: Dict[str, Dict[str, Any]] = {}
        self._load_agent_registry()

        # 文件锁
        self._locks: Dict[str, float] = {}

    def _load_agent_registry(self) -> None:
        """加载Agent注册表"""
        rules_file = self.global_memory_dir / "COORDINATION_RULES.md"
        if rules_file.exists():
            # 从文件解析Agent信息
            # 这里简化处理，使用硬编码的默认值
            pass

        # 默认Agent注册
        self._agents = {
            "primary_agent": {
                "type": "primary",
                "status": "running",
                "skills": ["task_split", "agent_dispatch", "status_query"],
            },
            "coordinator_agent": {
                "type": "coordinator",
                "status": "running",
                "skills": ["status_query", "agent_dispatch"],
            },
            # ---- 通用智能体团队 (universal) ----
            "code_agent": {
                "type": "universal",
                "status": "idle",
                "skills": ["code_generation", "code_review", "debugging", "testing", "refactoring"],
            },
            "research_agent": {
                "type": "universal",
                "status": "idle",
                "skills": [
                    "web_research",
                    "information_extraction",
                    "fact_checking",
                    "document_parsing",
                    "report_generation",
                ],
            },
            "creative_agent": {
                "type": "universal",
                "status": "idle",
                "skills": ["content_writing", "copywriting", "translation", "document_generation", "creative_design"],
            },
            # ---- 领域智能体 (domain) ----
            "data_agent": {
                "type": "domain",
                "status": "idle",
                "skills": ["data_analysis", "table_processing", "visualization"],
            },
        }

    def register_agent(self, name: str, agent_type: str, skills: List[str]) -> None:
        """注册Agent"""
        self._agents[name] = {
            "type": agent_type,
            "status": "idle",
            "skills": skills,
        }
        self._update_coordination_snapshot()

    def unregister_agent(self, name: str) -> None:
        """注销Agent"""
        if name in self._agents:
            del self._agents[name]
            self._update_coordination_snapshot()

    def get_available_agents(self) -> Dict[str, Dict[str, Any]]:
        """Return agents that are not stopped (available for dispatch)"""
        return {name: info for name, info in self._agents.items() if info.get("status") != "stopped"}

    def update_agent_status(self, name: str, status: str, task_id: str = None) -> None:
        """更新Agent状态"""
        if name in self._agents:
            self._agents[name]["status"] = status
            self._agents[name]["current_task"] = task_id
            self._update_coordination_snapshot()

    def get_agent_status(self, name: str) -> Optional[Dict[str, Any]]:
        """获取Agent状态"""
        return self._agents.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有Agent"""
        result = []
        for name, info in self._agents.items():
            result.append(
                {
                    "agent_name": name,
                    "agent_type": info["type"],
                    "status": info["status"],
                    "skills": info["skills"],
                    "path": f"workspace/{name}/",
                }
            )
        return result

    def match_agent(self, task_type: str) -> Optional[str]:
        """
        根据任务类型匹配Agent（基于skills动态匹配）

        优先匹配 domain > universal > primary

        Args:
            task_type: 任务类型

        Returns:
            匹配的Agent名称，无匹配返回None
        """
        # 优先级：domain > universal
        for priority_type in ("domain", "universal"):
            for name, info in self._agents.items():
                if info.get("type") == priority_type and task_type in info.get("skills", []):
                    if info.get("status") in ["idle", "running"]:
                        return name
        return None

    def create_task(
        self,
        task_content: str,
        target_agent: str = None,
        task_type: str = None,
        parent_task_id: str = None,
    ) -> str:
        """
        创建任务文件

        Args:
            task_content: 任务内容
            target_agent: 目标Agent
            task_type: 任务类型
            parent_task_id: 父任务ID

        Returns:
            任务ID
        """
        task_id = f"TASK_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # 自动匹配Agent
        if not target_agent and task_type:
            target_agent = self.match_agent(task_type)

        # 构建任务文件内容
        content = f"""---
task_id: {task_id}
status: pending
target_agent: {target_agent or 'auto'}
task_type: {task_type or 'general'}
parent_task: {parent_task_id or 'none'}
created_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
updated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# 任务内容

{task_content}

## 完成标准

- [ ] 任务执行完成
- [ ] 结果已记录
"""

        task_file = self.tasks_dir / f"{task_id}.md"
        task_file.write_text(content, encoding="utf-8")

        # 更新协同状态
        self._update_coordination_snapshot()

        return task_id

    def update_task_status(self, task_id: str, status: str, result: str = None) -> None:
        """更新任务状态"""
        task_file = self.tasks_dir / f"{task_id}.md"
        if not task_file.exists():
            return

        content = task_file.read_text(encoding="utf-8")

        # 更新frontmatter中的状态
        lines = content.split("\n")
        in_frontmatter = False
        new_lines = []

        for line in lines:
            if line == "---":
                in_frontmatter = not in_frontmatter
                new_lines.append(line)
            elif in_frontmatter and line.startswith("status:"):
                new_lines.append(f"status: {status}")
            elif in_frontmatter and line.startswith("updated_at:"):
                new_lines.append(f"updated_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                new_lines.append(line)

        # 如果有结果，追加到文件末尾
        if result:
            new_lines.append(f"\n\n## 执行结果\n\n{result}")

        task_file.write_text("\n".join(new_lines), encoding="utf-8")

        # 更新协同状态
        self._update_coordination_snapshot()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        task_file = self.tasks_dir / f"{task_id}.md"
        if not task_file.exists():
            return None

        content = task_file.read_text(encoding="utf-8")
        return self._parse_task_file(content)

    def clear_tasks(self) -> int:
        """
        清除所有任务文件、响应文件和通知文件

        Returns:
            清除的任务文件数量
        """
        count = 0
        # 清除任务文件
        for task_file in self.tasks_dir.glob("TASK_*.md"):
            task_file.unlink()
            count += 1
        # 清除响应文件
        for resp_file in self.responses_dir.glob("RESPONSE_*.md"):
            resp_file.unlink()
        # 清除通知文件
        for notice_file in self.notices_dir.glob("NOTICE_*.json"):
            notice_file.unlink()
        # 重置 Agent 状态
        for name in self._agents:
            self._agents[name]["status"] = "idle"
            self._agents[name]["current_task"] = None
        self._update_coordination_snapshot()
        return count

    def list_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """列出所有任务"""
        tasks = []
        for task_file in self.tasks_dir.glob("TASK_*.md"):
            content = task_file.read_text(encoding="utf-8")
            task_info = self._parse_task_file(content)
            if task_info:
                if status is None or task_info.get("status") == status:
                    tasks.append(task_info)
        return tasks

    def _parse_task_file(self, content: str) -> Optional[Dict[str, Any]]:
        """解析任务文件"""
        try:
            lines = content.split("\n")
            frontmatter = {}
            in_frontmatter = False
            body_lines = []

            for line in lines:
                if line == "---":
                    in_frontmatter = not in_frontmatter
                    continue
                if in_frontmatter and ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()
                elif not in_frontmatter:
                    body_lines.append(line)

            return {
                "task_id": frontmatter.get("task_id"),
                "status": frontmatter.get("status"),
                "target_agent": frontmatter.get("target_agent"),
                "task_type": frontmatter.get("task_type"),
                "parent_task": frontmatter.get("parent_task"),
                "created_at": frontmatter.get("created_at"),
                "updated_at": frontmatter.get("updated_at"),
                "content": "\n".join(body_lines).strip(),
            }
        except Exception:
            return None

    def create_response(
        self,
        task_id: str,
        result: str,
        agent_name: str,
        files: List[str] = None,
    ) -> str:
        """创建响应文件"""
        response_id = f"RESPONSE_{task_id.replace('TASK_', '')}"

        content = f"""---
response_id: {response_id}
task_id: {task_id}
agent: {agent_name}
created_at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

# 执行结果

{result}

## 生成的文件

"""
        if files:
            for f in files:
                content += f"- {f}\n"
        else:
            content += "无\n"

        response_file = self.responses_dir / f"{response_id}.md"
        response_file.write_text(content, encoding="utf-8")

        # 更新任务状态
        self.update_task_status(task_id, "finished", result)

        return response_id

    def create_notice(
        self,
        notice_type: str,
        target_agent: str,
        content: str,
    ) -> str:
        """创建通知文件"""
        notice_id = f"NOTICE_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        notice_data = {
            "notice_id": notice_id,
            "type": notice_type,
            "target_agent": target_agent,
            "content": content,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

        notice_file = self.notices_dir / f"{notice_id}.json"
        notice_file.write_text(json.dumps(notice_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return notice_id

    def get_notices(self, target_agent: str = None) -> List[Dict[str, Any]]:
        """获取通知列表"""
        notices = []
        for notice_file in self.notices_dir.glob("NOTICE_*.json"):
            try:
                notice_data = json.loads(notice_file.read_text(encoding="utf-8"))
                if target_agent is None or notice_data.get("target_agent") == target_agent:
                    notices.append(notice_data)
            except Exception:
                continue
        return notices

    def acquire_lock(self, resource: str, agent: str, timeout: int = 30) -> bool:
        """
        获取资源锁

        Args:
            resource: 资源路径
            agent: 请求Agent
            timeout: 超时时间(秒)

        Returns:
            是否获取成功
        """
        lock_key = resource
        now = time.time()

        # 检查是否有锁
        if lock_key in self._locks:
            lock_time, lock_agent = self._locks[lock_key]
            # 检查是否超时
            if now - lock_time > timeout:
                # 超时释放
                del self._locks[lock_key]
            elif lock_agent == agent:
                # 同一Agent重入
                self._locks[lock_key] = (now, agent)
                return True
            else:
                # 被其他Agent持有
                return False

        # 获取锁
        self._locks[lock_key] = (now, agent)
        return True

    def release_lock(self, resource: str, agent: str) -> None:
        """释放资源锁"""
        lock_key = resource
        if lock_key in self._locks:
            _, lock_agent = self._locks[lock_key]
            if lock_agent == agent:
                del self._locks[lock_key]

    def _update_coordination_snapshot(self) -> None:
        """更新协同状态快照"""
        snapshot_file = self.coordination_dir / "COORDINATION_SNAPSHOT.md"

        # 收集Agent状态
        agent_status_lines = []
        for name, info in self._agents.items():
            agent_status_lines.append(
                f"| {name} | {info['type']} | {info['status']} | {info.get('current_task', '-')} |"
            )

        # 收集任务状态
        tasks = self.list_tasks()
        task_lines = []
        for task in tasks:
            if task["status"] in ["pending", "processing"]:
                task_lines.append(f"- [{task['status']}] {task['task_id']} -> {task['target_agent']}")

        content = f"""# 协同状态快照

> 此文件由Coordinator Agent自动维护，记录当前协同状态

## 更新时间

{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Agent状态

| Agent | 类型 | 状态 | 当前任务 |
|-------|------|------|----------|
{chr(10).join(agent_status_lines) if agent_status_lines else '| - | - | - | - |'}

## 任务队列

{chr(10).join(task_lines) if task_lines else '当前无活跃任务。'}

## 协同日志

暂无协同记录。
"""

        snapshot_file.write_text(content, encoding="utf-8")


# 全局单例
_coordination_manager: Optional[CoordinationManager] = None


def get_coordination_manager(base_dir: Path = None) -> CoordinationManager:
    """获取协同管理器单例"""
    global _coordination_manager
    if _coordination_manager is None and base_dir:
        _coordination_manager = CoordinationManager(base_dir)
    return _coordination_manager


def init_coordination_manager(base_dir: Path) -> CoordinationManager:
    """初始化协同管理器"""
    global _coordination_manager
    _coordination_manager = CoordinationManager(base_dir)
    return _coordination_manager
