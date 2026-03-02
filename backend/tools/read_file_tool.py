"""
文件读取工具 - 沙箱化的文件读取
"""
from pathlib import Path
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool


class ReadFileInput(BaseModel):
    """文件读取工具输入参数"""
    path: str = Field(description="要读取的文件路径（相对于项目根目录）")


class ReadFileTool(BaseTool):
    """
    文件读取工具
    
    用于精准读取本地指定文件的内容，是 Agent Skills 机制的核心依赖
    """
    name: str = "read_file"
    description: str = """读取项目目录内的文件内容。这是学习和使用技能的核心工具。
当需要使用某个技能时，必须先用此工具读取对应的 SKILL.md 文件。
输入参数：path - 文件的相对路径（如 ./skills/pdf/SKILL.md）
注意：路径中包含空格或特殊字符时无需转义，直接传入原始路径即可。"""
    args_schema: Type[BaseModel] = ReadFileInput
    
    root_dir: Path = Field(default=None)
    max_length: int = 10000
    
    def __init__(self, root_dir: Path, max_length: int = 10000, **kwargs):
        super().__init__(**kwargs)
        self.root_dir = root_dir
        self.max_length = max_length
    
    def _normalize_path(self, path: str) -> str:
        """规范化路径，处理 LLM 可能传入的各种格式"""
        # 去除首尾空白
        path = path.strip()
        # 移除 LLM 可能包裹的引号
        if (path.startswith('"') and path.endswith('"')) or \
           (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]
        # 统一路径分隔符
        path = path.replace("\\", "/")
        # 去除首尾空白（引号内可能还有空格）
        path = path.strip()
        return path
    
    def _is_path_safe(self, path: str) -> bool:
        """检查路径是否安全（防止路径遍历攻击）"""
        # 解析路径
        try:
            # 处理相对路径
            if path.startswith("./"):
                path = path[2:]
            elif path.startswith("/"):
                return False  # 禁止绝对路径
            
            # 解析完整路径
            full_path = (self.root_dir / path).resolve()
            
            # 检查是否在根目录内
            return str(full_path).startswith(str(self.root_dir.resolve()))
        except Exception:
            return False
    
    def _run(self, path: str) -> str:
        """同步读取文件"""
        # 规范化路径
        path = self._normalize_path(path)
        
        # 安全检查
        if not self._is_path_safe(path):
            return "错误：不允许访问项目目录以外的文件。"
        
        try:
            # 处理路径
            if path.startswith("./"):
                path = path[2:]
            
            file_path = self.root_dir / path
            
            # 检查文件是否存在
            if not file_path.exists():
                return f"错误：文件不存在 - {path}"
            
            if not file_path.is_file():
                return f"错误：{path} 不是一个文件"
            
            # 读取文件内容
            content = file_path.read_text(encoding="utf-8")
            
            # 截断过长内容
            if len(content) > self.max_length:
                content = content[:self.max_length] + "\n...[内容已截断]"
            
            return content if content else "文件为空"
            
        except UnicodeDecodeError:
            return "错误：文件编码不支持（非 UTF-8）"
        except PermissionError:
            return "错误：没有读取权限"
        except Exception as e:
            return f"错误：{type(e).__name__}: {str(e)}"
    
    async def _arun(self, path: str) -> str:
        """异步读取文件"""
        return self._run(path)


def create_read_file_tool(root_dir: Path) -> ReadFileTool:
    """创建文件读取工具实例"""
    return ReadFileTool(root_dir=root_dir)
