#!/bin/bash

# RAG 服务停止脚本

echo "================================================"
echo "        停止 RAG 服务"
echo "================================================"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 停止 RAG 服务
stop_rag_service() {
    echo -e "\n${YELLOW}停止 RAG 服务...${NC}"
    if [ -f pids/rag_service.pid ]; then
        PID=$(cat pids/rag_service.pid)
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            echo -e "${GREEN}✓ RAG 服务已停止 (PID: $PID)${NC}"
        else
            echo -e "${YELLOW}RAG 服务未运行${NC}"
        fi
        rm -f pids/rag_service.pid
    else
        # 尝试通过端口查找
        if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null ; then
            kill -9 $(lsof -t -i:8001)
            echo -e "${GREEN}✓ RAG 服务已停止${NC}"
        else
            echo -e "${YELLOW}RAG 服务未运行${NC}"
        fi
    fi
}

# 停止 Milvus API
stop_milvus_api() {
    echo -e "\n${YELLOW}停止 Milvus API...${NC}"
    if [ -f pids/milvus_api.pid ]; then
        PID=$(cat pids/milvus_api.pid)
        if ps -p $PID > /dev/null 2>&1; then
            kill $PID
            echo -e "${GREEN}✓ Milvus API 已停止 (PID: $PID)${NC}"
        else
            echo -e "${YELLOW}Milvus API 未运行${NC}"
        fi
        rm -f pids/milvus_api.pid
    else
        # 尝试通过端口查找
        if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
            kill -9 $(lsof -t -i:8000)
            echo -e "${GREEN}✓ Milvus API 已停止${NC}"
        else
            echo -e "${YELLOW}Milvus API 未运行${NC}"
        fi
    fi
}

# 停止 Milvus
stop_milvus() {
    echo -e "\n${YELLOW}停止 Milvus...${NC}"

    read -p "是否停止 Milvus 数据库？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker compose down
        echo -e "${GREEN}✓ Milvus 已停止${NC}"

        read -p "是否清理数据？(y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker compose down -v
            echo -e "${GREEN}✓ 数据已清理${NC}"
        fi
    else
        echo "保持 Milvus 运行"
    fi
}

# 清理日志
clean_logs() {
    echo -e "\n${YELLOW}清理日志...${NC}"
    read -p "是否清理日志文件？(y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf logs/*
        echo -e "${GREEN}✓ 日志已清理${NC}"
    fi
}

# 主流程
main() {
    stop_rag_service
    stop_milvus_api
    stop_milvus
    clean_logs

    echo -e "\n${GREEN}================================================${NC}"
    echo -e "${GREEN}        服务停止完成${NC}"
    echo -e "${GREEN}================================================${NC}"
}

# 运行
main