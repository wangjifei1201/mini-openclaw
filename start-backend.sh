#!/bin/bash

# Mini-OpenClaw 后端启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Mini-OpenClaw 后端服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 进入后端目录
cd "$BACKEND_DIR"

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[警告] 未找到 .env 文件${NC}"
    echo -e "正在从 .env.example 创建..."
    cp ".env.example" ".env"
    echo -e "${RED}请编辑 $BACKEND_DIR/.env 填入 API Key${NC}"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Python3${NC}"
    exit 1
fi

# 安装依赖
echo -e "${GREEN}[1/2] 检查并安装依赖...${NC}"
pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -q

# 启动服务
echo -e "${GREEN}[2/2] 启动后端服务...${NC}"
echo ""
echo -e "后端 API: ${YELLOW}http://localhost:8002${NC}"
echo -e "API 文档: ${YELLOW}http://localhost:8002/docs${NC}"
echo ""
echo -e "按 ${RED}Ctrl+C${NC} 停止服务"
echo -e "${BLUE}========================================${NC}"
echo ""

# 启动 uvicorn（前台运行，显示日志）
python3 -m uvicorn app:app --port 8002 --host 0.0.0.0 --reload
