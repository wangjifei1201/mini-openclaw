"""
测试 terminal_tool.py 的安全检查功能
"""
from pathlib import Path

import pytest
from tools.terminal_tool import TerminalTool


@pytest.fixture
def root_dir(tmp_path):
    return tmp_path


@pytest.fixture
def terminal_tool(root_dir):
    return TerminalTool(root_dir=root_dir)


def test_safe_command(terminal_tool):
    """测试安全命令"""
    result = terminal_tool._run("echo hello")
    assert "hello" in result


def test_dangerous_command(terminal_tool):
    """测试高危命令拦截"""
    result = terminal_tool._run("rm -rf /")
    assert "高危操作" in result


def test_path_outside_sandbox(terminal_tool, root_dir):
    """测试路径越界"""
    result = terminal_tool._run("cat /etc/passwd")
    assert "沙箱目录外" in result


def test_heredoc_with_path(terminal_tool):
    """测试包含路径的 heredoc"""
    command = """cat > test.html << 'EOF'
<!DOCTYPE html>
<html>
<body>/* some css */</body>
</html>
EOF"""
    result = terminal_tool._run(command)
    assert "安全限制" not in result  # 应该不被拦截


def test_long_command(terminal_tool):
    """测试过长命令"""
    long_cmd = "echo " + "a" * 10001
    result = terminal_tool._run(long_cmd)
    assert "命令过长" in result
