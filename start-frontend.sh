#!/bin/bash

# Mini-OpenClaw 前端启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Mini-OpenClaw 前端服务${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 进入前端目录
cd "$FRONTEND_DIR"

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Node.js${NC}"
    exit 1
fi

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}[错误] 未找到 npm${NC}"
    exit 1
fi

# 安装依赖
if [ ! -d "node_modules" ]; then
    echo -e "${GREEN}[1/2] 安装前端依赖...${NC}"
    npm install
else
    echo -e "${GREEN}[1/2] 依赖已安装${NC}"
fi

# 获取本机 IP
if command -v ifconfig &> /dev/null; then
    LOCAL_IP=$(ifconfig | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}')
else
    LOCAL_IP="localhost"
fi

# 启动服务
echo -e "${GREEN}[2/2] 启动前端服务...${NC}"
echo ""
echo -e "本机访问:   ${YELLOW}http://localhost:3001${NC}"
echo -e "局域网访问: ${YELLOW}http://${LOCAL_IP}:3001${NC}"
echo ""
echo -e "${RED}注意: 请确保后端服务已在端口 8002 启动${NC}"
echo ""
echo -e "按 ${RED}Ctrl+C${NC} 停止服务"
echo -e "${BLUE}========================================${NC}"
echo ""

# 启动 Next.js 开发服务器
npm run dev
