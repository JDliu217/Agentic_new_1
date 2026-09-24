#!/bin/bash

# RAG 服务一键启动脚本
# 功能：按顺序启动所有服务

set -e  # 遇到错误立即退出

echo "================================================"
echo "        RAG 服务启动器"
echo "================================================"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查前置条件
check_requirements() {
    echo -e "${YELLOW}检查环境...${NC}"

    # 检查 Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker 未安装${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Docker 已安装${NC}"

    # 检查 Python
    if ! command -v python &> /dev/null; then
        if ! command -v python3 &> /dev/null; then
            echo -e "${RED}❌ Python 未安装${NC}"
            exit 1
        fi
    fi
    echo -e "${GREEN}✓ Python 已安装${NC}"

    # 检查 .env 文件
    if [ ! -f .env ]; then
        echo -e "${RED}❌ .env 文件不存在${NC}"
        echo "请创建 .env 文件并添加: DASHSCOPE_API_KEY=your-key"
        exit 1
    fi
    echo -e "${GREEN}✓ .env 文件存在${NC}"
}

# 启动 Milvus
start_milvus() {
    echo -e "\n${YELLOW}[1/4] 启动 Milvus...${NC}"

    # 检查是否已运行
    if docker ps | grep -q milvus-standalone; then
        echo -e "${GREEN}✓ Milvus 已经在运行${NC}"
    else
        docker compose up -d
        echo "等待 Milvus 启动..."
        sleep 30

        # 测试连接
        if python3 test_milvus.py 2>/dev/null; then
            echo -e "${GREEN}✓ Milvus 启动成功${NC}"
        else
            echo -e "${YELLOW}⚠ Milvus 可能需要更多时间启动${NC}"
        fi
    fi
}

# 导入数据
import_data() {
    echo -e "\n${YELLOW}[2/4] 检查数据...${NC}"

    read -p "是否需要导入/重新导入数据？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "导入数据中..."
        python3 milvus_insert.py
        echo -e "${GREEN}✓ 数据导入完成${NC}"
    else
        echo "跳过数据导入"
    fi
}

# 启动 Milvus API
start_milvus_api() {
    echo -e "\n${YELLOW}[3/4] 启动 Milvus API...${NC}"

    # 检查端口
    if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}⚠ 端口 8000 已被占用${NC}"
        read -p "是否杀死占用进程？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $(lsof -t -i:8000)
            echo "已清理端口 8000"
        else
            echo -e "${RED}跳过 Milvus API 启动${NC}"
            return
        fi
    fi

    # 后台启动
    nohup python3 milvus_api.py > logs/milvus_api.log 2>&1 &
    echo $! > pids/milvus_api.pid
    sleep 3

    # 检查是否成功
    if curl -s http://localhost:8000/health > /dev/null; then
        echo -e "${GREEN}✓ Milvus API 启动成功 (PID: $(cat pids/milvus_api.pid))${NC}"
        echo "  访问: http://localhost:8000/docs"
    else
        echo -e "${RED}❌ Milvus API 启动失败${NC}"
    fi
}

# 启动 RAG 服务
start_rag_service() {
    echo -e "\n${YELLOW}[4/4] 启动 RAG 服务...${NC}"

    # 检查端口
    if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
        echo -e "${YELLOW}⚠ 端口 8001 已被占用${NC}"
        read -p "是否杀死占用进程？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill -9 $(lsof -t -i:8001)
            echo "已清理端口 8001"
        else
            echo -e "${RED}跳过 RAG 服务启动${NC}"
            return
        fi
    fi

    # 后台启动
    nohup python3 rag_service.py > logs/rag_service.log 2>&1 &
    echo $! > pids/rag_service.pid
    sleep 3

    # 检查是否成功
    if curl -s http://localhost:8001/health > /dev/null; then
        echo -e "${GREEN}✓ RAG 服务启动成功 (PID: $(cat pids/rag_service.pid))${NC}"
        echo "  访问: http://localhost:8001/docs"
    else
        echo -e "${RED}❌ RAG 服务启动失败${NC}"
    fi
}

# 显示状态
show_status() {
    echo -e "\n${GREEN}================================================${NC}"
    echo -e "${GREEN}        所有服务已启动！${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo "服务地址："
    echo "  • Milvus:     localhost:19530"
    echo "  • Attu:       http://localhost:3000"
    echo "  • Milvus API: http://localhost:8000/docs"
    echo "  • RAG 服务:   http://localhost:8001/docs"
    echo
    echo "测试命令："
    echo "  python3 test_rag.py"
    echo "  python3 test_rag_enhanced.py"
    echo
    echo "查看日志："
    echo "  tail -f logs/milvus_api.log"
    echo "  tail -f logs/rag_service.log"
    echo
    echo "停止服务："
    echo "  ./stop_rag_all.sh"
}

# 创建必要目录
mkdir -p logs pids

# 主流程
main() {
    check_requirements
    start_milvus
    import_data
    start_milvus_api
    start_rag_service
    show_status
}

# 捕获退出信号
trap 'echo -e "\n${RED}启动被中断${NC}"; exit 1' INT TERM

# 运行主流程
main