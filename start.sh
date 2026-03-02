#!/bin/bash

# Mini-OpenClaw 一键启动脚本
# 同时启动后端和前端服务

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Mini-OpenClaw 一键启动${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 .env 文件
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "${YELLOW}[警告] 未找到 .env 文件${NC}"
    echo -e "正在从 .env.example 创建..."
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    echo -e "${RED}请编辑 $BACKEND_DIR/.env 填入 API Key 后重新运行${NC}"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Python3${NC}"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Node.js${NC}"
    exit 1
fi

# 安装后端依赖
echo -e "${GREEN}[1/4] 检查后端依赖...${NC}"
cd "$BACKEND_DIR"
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -q 2>/dev/null

# 安装前端依赖
echo -e "${GREEN}[2/4] 检查前端依赖...${NC}"
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
    npm install --silent 2>/dev/null
fi

# 启动后端（后台运行，输出到日志）
echo -e "${GREEN}[3/4] 启动后端服务 (端口 8002)...${NC}"
cd "$BACKEND_DIR"
python3 -m uvicorn app:app --port 8002 --host 0.0.0.0 > /tmp/mini-openclaw-backend.log 2>&1 &
BACKEND_PID=$!

# 等待后端启动并检查
echo -e "      等待后端启动..."
sleep 5

# 检查后端是否成功启动
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}[错误] 后端启动失败，查看日志:${NC}"
    cat /tmp/mini-openclaw-backend.log
    exit 1
fi

# 检查后端是否响应
if curl -s http://127.0.0.1:8002/health > /dev/null 2>&1; then
    echo -e "      ${GREEN}后端启动成功${NC}"
else
    echo -e "${YELLOW}      后端正在初始化，请稍候...${NC}"
    sleep 3
fi

# 启动前端（后台运行）
echo -e "${GREEN}[4/4] 启动前端服务 (端口 3000)...${NC}"
cd "$FRONTEND_DIR"
npm run dev > /tmp/mini-openclaw-frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 3

# 获取本机 IP
if command -v ifconfig &> /dev/null; then
    LOCAL_IP=$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}')
else
    LOCAL_IP="localhost"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Mini-OpenClaw 已启动！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "前端访问:   ${YELLOW}http://localhost:3000${NC}"
echo -e "局域网访问: ${YELLOW}http://${LOCAL_IP}:3000${NC}"
echo ""
echo -e "后端 API:   ${YELLOW}http://localhost:8002${NC}"
echo -e "API 文档:   ${YELLOW}http://localhost:8002/docs${NC}"
echo ""
echo -e "后端日志:   ${YELLOW}/tmp/mini-openclaw-backend.log${NC}"
echo -e "前端日志:   ${YELLOW}/tmp/mini-openclaw-frontend.log${NC}"
echo ""
echo -e "按 ${RED}Ctrl+C${NC} 停止所有服务"
echo -e "${BLUE}========================================${NC}"
echo ""

# 捕获退出信号
cleanup() {
    echo ""
    echo -e "${YELLOW}正在停止服务...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    # 确保杀掉所有相关进程
    pkill -f "uvicorn app:app" 2>/dev/null
    pkill -f "next dev" 2>/dev/null
    echo -e "${GREEN}服务已停止${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 持续运行，等待用户中断
while true; do
    # 检查进程是否还在运行
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}[警告] 后端服务已停止${NC}"
        cleanup
    fi
    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}[警告] 前端服务已停止${NC}"
        cleanup
    fi
    sleep 5
done
