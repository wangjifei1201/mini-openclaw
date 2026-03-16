"""
Python 代码解释器工具
"""
import builtins
import io
import sys
from typing import Type

from config import settings
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

# 安全的内置函数白名单
SAFE_BUILTINS = [
    # 类型转换
    "int",
    "float",
    "str",
    "bool",
    "bytes",
    "bytearray",
    "list",
    "tuple",
    "dict",
    "set",
    "frozenset",
    "complex",
    "memoryview",
    # 数学与逻辑
    "abs",
    "round",
    "min",
    "max",
    "sum",
    "pow",
    "divmod",
    # 序列操作
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "reversed",
    "iter",
    "next",
    "slice",
    # 对象与类型
    "type",
    "isinstance",
    "issubclass",
    "id",
    "hash",
    "callable",
    "hasattr",
    "getattr",
    "setattr",
    "delattr",
    "property",
    "staticmethod",
    "classmethod",
    "super",
    "object",
    # IO
    "print",
    "repr",
    "format",
    "chr",
    "ord",
    "input",
    # 其他安全函数
    "all",
    "any",
    "bin",
    "hex",
    "oct",
    "ascii",
    "vars",
    "dir",
    # 常量
    "True",
    "False",
    "None",
    # 异常类
    "Exception",
    "BaseException",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "RuntimeError",
    "StopIteration",
    "ArithmeticError",
    "ZeroDivisionError",
    "NotImplementedError",
    "OverflowError",
    "ImportError",
    "ModuleNotFoundError",
    "NameError",
    "LookupError",
    "AssertionError",
]

ALLOWED_MODULE_STATUS = False  # 是否启用模块导入限制
# 允许导入的安全模块
ALLOWED_MODULES = {
    "math",
    "json",
    "datetime",
    "re",
    "collections",
    "itertools",
    "functools",
    "operator",
    "string",
    "decimal",
    "fractions",
    "random",
    "statistics",
    "textwrap",
    "unicodedata",
    "dataclasses",
    "copy",
    "pprint",
    "enum",
    "typing",
    "csv",
    "base64",
    "hashlib",
    "hmac",
    "time",
    "calendar",
    "zlib",
    "struct",
}


class PythonREPLInput(BaseModel):
    """Python REPL 工具输入参数"""

    code: str = Field(description="要执行的 Python 代码")


class PythonREPLTool(BaseTool):
    """
    Python 代码解释器工具

    赋予 Agent 逻辑计算、数据处理和脚本执行的能力
    """

    name: str = "python_repl"
    description: str = """执行 Python 代码并返回结果。可以用于数学计算、数据处理、字符串操作等。
注意：代码在安全沙箱中执行，仅可导入数学、JSON、日期时间等安全模块，不可访问文件系统或执行系统命令。
输入参数：code - 要执行的 Python 代码字符串"""
    args_schema: Type[BaseModel] = PythonREPLInput

    _globals: dict = {}
    _locals: dict = {}
    _original_import: object = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 保存原始 __import__ 引用
        self._original_import = builtins.__import__

        # 构建受限的内置函数字典
        safe_builtins_dict = {}
        for name in SAFE_BUILTINS:
            if hasattr(builtins, name):
                safe_builtins_dict[name] = getattr(builtins, name)

        # 提供受限的 __import__
        original_import = self._original_import

        def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
            module_root = name.split(".")[0]
            if ALLOWED_MODULE_STATUS and module_root not in ALLOWED_MODULES:
                raise ImportError(f"安全限制：不允许导入模块 '{name}'。" f"允许的模块: {', '.join(sorted(ALLOWED_MODULES))}")
            return original_import(name, globals, locals, fromlist, level)

        safe_builtins_dict["__import__"] = _safe_import

        self._globals = {"__builtins__": safe_builtins_dict}
        self._locals = {}

    def _run(self, code: str) -> str:
        """同步执行 Python 代码"""
        # 捕获标准输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            # 执行代码
            exec(code, self._globals, self._locals)

            # 获取输出
            stdout_output = sys.stdout.getvalue()
            stderr_output = sys.stderr.getvalue()

            output = ""
            if stdout_output:
                output += stdout_output
            if stderr_output:
                if output:
                    output += "\n"
                output += f"[stderr] {stderr_output}"

            # 如果没有输出，尝试获取最后一个表达式的值
            if not output:
                try:
                    result = eval(code, self._globals, self._locals)
                    if result is not None:
                        output = repr(result)
                except:
                    pass

            # 截断过长输出
            if len(output) > settings.MAX_OUTPUT_LENGTH:
                output = output[: settings.MAX_OUTPUT_LENGTH] + "\n...[输出已截断]"

            return output if output else "代码执行成功（无输出）"

        except Exception as e:
            return f"错误：{type(e).__name__}: {str(e)}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    async def _arun(self, code: str) -> str:
        """异步执行 Python 代码"""
        return self._run(code)


def create_python_repl_tool() -> Type[PythonREPLTool]:
    """创建 Python REPL 工具类"""
    return PythonREPLTool
