"""
命令行操作工具 - 沙箱化的 Shell 命令执行
"""
import asyncio
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Optional, Type

try:
    from pydantic import BaseModel, Field
except ImportError:
    from pydantic.v1 import BaseModel, Field

from config import settings
from langchain_core.tools import BaseTool

# 高危命令黑名单
DANGEROUS_COMMANDS = settings.DANGEROUS_COMMANDS

# 需要从环境变量中移除的敏感密钥
SENSITIVE_ENV_KEYS = settings.SENSITIVE_ENV_KEYS


class TerminalInput(BaseModel):
    """终端工具输入参数"""

    command: str = Field(description="要执行的 Shell 命令")


class TerminalTool(BaseTool):
    """
    沙箱化的终端工具

    允许 Agent 在受限的安全环境下执行 Shell 命令
    """

    name: str = "terminal"
    description: str = """执行 Shell 命令。可以用于文件操作、系统命令等。
注意：命令执行受沙箱限制，仅可操作项目目录内的文件，高危命令和越界路径访问会被拦截。
输入参数：command - 要执行的命令字符串"""
    args_schema: Type[BaseModel] = TerminalInput

    root_dir: Path = Field(default=None)

    def __init__(self, root_dir: Path, **kwargs):
        super().__init__(root_dir=root_dir, **kwargs)

    def _is_dangerous(self, command: str) -> Optional[str]:
        """检查命令是否在黑名单中，返回拦截原因或None"""
        cmd_lower = command.lower().strip()
        for dangerous in DANGEROUS_COMMANDS:
            # 使用正则表达式匹配单词边界，避免误杀包含子串的合法命令
            if re.search(r'\b' + re.escape(dangerous.lower()) + r'\b', cmd_lower):
                return f"错误：该命令包含高危操作 '{dangerous}'，被安全策略拦截。"
        return None

    def _is_path_in_sandbox(self, path_str: str) -> bool:
        """检查路径是否在沙箱目录内"""
        try:
            # 处理相对路径：基于 root_dir 解析
            if not path_str.startswith("/"):
                target = (self.root_dir / path_str).resolve()
            else:
                target = Path(path_str).resolve()
            sandbox = self.root_dir.resolve()
            return str(target).startswith(str(sandbox))
        except Exception:
            return False

    def _check_command_paths(self, command: str) -> Optional[str]:
        """
        检查命令中的路径是否越界。
        返回 None 表示安全，返回字符串表示拦截原因。
        """
        # 移除 heredoc 内容，避免误判
        cleaned_command = self._remove_heredoc(command)

        try:
            parts = shlex.split(cleaned_command)
        except ValueError:
            # shlex 解析失败时回退到简单分割
            parts = cleaned_command.split()

        for part in parts:
            # 检测绝对路径参数（跳过 /dev/null 等常用路径）
            if part.startswith("/") and not part.startswith("/dev/"):
                if not self._is_path_in_sandbox(part):
                    return f"安全限制：不允许访问沙箱目录外的路径 ({part})"

        # 检测 cd 到沙箱外
        cd_match = re.search(r'\bcd\s+([^\s;&|]+)', cleaned_command)
        if cd_match:
            cd_target = cd_match.group(1)
            # 去除可能的引号
            cd_target = cd_target.strip('"\'')
            if cd_target.startswith("/"):
                if not self._is_path_in_sandbox(cd_target):
                    return f"安全限制：不允许切换到沙箱目录外 ({cd_target})"
            elif cd_target.startswith(".."):
                # 相对路径，解析后检查
                resolved = (self.root_dir / cd_target).resolve()
                if not str(resolved).startswith(str(self.root_dir.resolve())):
                    return "安全限制：不允许切换到沙箱目录外"

        return None

    def _remove_heredoc(self, command: str) -> str:
        """移除命令中的 heredoc 内容，避免路径检查误判"""
        # 匹配 << 'EOF' 或 << EOF 等
        heredoc_pattern = r'<<\s*[\'""]?(\w+)[\'""]?\s*(.*?)\s*\1'
        return re.sub(heredoc_pattern, '', command, flags=re.DOTALL)

    def _run(self, command: str) -> str:
        """同步执行命令"""
        # 检查命令长度，避免过长命令
        if len(command) > 10000:  # 假设最大10KB
            return "错误：命令过长，拒绝执行。"

        # 检查高危命令
        danger_error = self._is_dangerous(command)
        if danger_error:
            return danger_error

        # 检查路径越界
        path_error = self._check_command_paths(command)
        if path_error:
            return path_error

        try:
            # 构建安全的环境变量
            safe_env = {**os.environ}
            for key in SENSITIVE_ENV_KEYS:
                safe_env.pop(key, None)
            safe_env["HOME"] = str(self.root_dir)

            # 在沙箱目录下执行命令
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                timeout=settings.COMMAND_TIMEOUT,
                env=safe_env,
            )

            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                if output:
                    output += "\n"
                output += f"[stderr] {result.stderr}"

            if result.returncode != 0:
                output += f"\n[退出码: {result.returncode}]"

            # 截断过长输出
            if len(output) > settings.MAX_OUTPUT_LENGTH:
                output = output[: settings.MAX_OUTPUT_LENGTH] + "\n...[输出已截断]"

            return output if output else "命令执行成功（无输出）"

        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{settings.COMMAND_TIMEOUT}秒）"
        except Exception as e:
            return f"错误：命令执行失败 - {str(e)}"

    async def _arun(self, command: str) -> str:
        """异步执行命令"""
        # 检查命令长度，避免过长命令
        if len(command) > 100000:  # 假设最大100KB
            return "错误：命令过长，拒绝执行。"

        # 检查高危命令
        danger_error = self._is_dangerous(command)
        if danger_error:
            return danger_error

        # 检查路径越界
        path_error = self._check_command_paths(command)
        if path_error:
            return path_error

        try:
            # 构建安全的环境变量
            safe_env = {**os.environ}
            for key in SENSITIVE_ENV_KEYS:
                safe_env.pop(key, None)
            safe_env["HOME"] = str(self.root_dir)

            # 在沙箱目录下异步执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(self.root_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=safe_env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=settings.COMMAND_TIMEOUT)
            except asyncio.TimeoutError:
                process.kill()
                return f"错误：命令执行超时（{settings.COMMAND_TIMEOUT}秒）"

            output = ""
            if stdout:
                output += stdout.decode('utf-8', errors='replace')
            if stderr:
                if output:
                    output += "\n"
                output += f"[stderr] {stderr.decode('utf-8', errors='replace')}"

            if process.returncode != 0:
                output += f"\n[退出码: {process.returncode}]"

            # 截断过长输出
            if len(output) > settings.MAX_OUTPUT_LENGTH:
                output = output[: settings.MAX_OUTPUT_LENGTH] + "\n...[输出已截断]"

            return output if output else "命令执行成功（无输出）"

        except Exception as e:
            return f"错误：命令执行失败 - {str(e)}"


def create_terminal_tool(root_dir: Path) -> TerminalTool:
    """创建终端工具实例"""
    return TerminalTool(root_dir=root_dir)
