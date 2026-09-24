#!/bin/bash

# Milvus 启动脚本

echo "======================================"
echo "Milvus 服务管理工具"
echo "======================================"

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    echo "访问: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    echo "正在安装 Docker Compose..."

    # macOS 用户通常 Docker Desktop 已包含 docker compose
    echo "提示：如果你使用 Docker Desktop，可以使用 'docker compose' 代替 'docker-compose'"
    exit 1
fi

# 选择操作
echo ""
echo "请选择操作："
echo "1) 启动 Milvus"
echo "2) 停止 Milvus"
echo "3) 重启 Milvus"
echo "4) 查看状态"
echo "5) 查看日志"
echo "6) 清理数据（危险）"
echo "0) 退出"
echo ""

read -p "请输入选项 (0-6): " choice

case $choice in
    1)
        echo "正在启动 Milvus..."
        # 尝试使用 docker compose（新版本）或 docker-compose（旧版本）
        if docker compose version &> /dev/null; then
            docker compose up -d
        else
            docker-compose up -d
        fi

        echo ""
        echo "✓ Milvus 正在启动，请等待约 30 秒..."
        echo ""
        echo "服务地址："
        echo "  - Milvus: localhost:19530"
        echo "  - MinIO Console: http://localhost:9001"
        echo "  - 健康检查: http://localhost:9091/healthz"
        echo ""
        echo "检查服务状态："
        sleep 5
        if docker compose version &> /dev/null; then
            docker compose ps
        else
            docker-compose ps
        fi
        ;;

    2)
        echo "正在停止 Milvus..."
        if docker compose version &> /dev/null; then
            docker compose down
        else
            docker-compose down
        fi
        echo "✓ Milvus 已停止"
        ;;

    3)
        echo "正在重启 Milvus..."
        if docker compose version &> /dev/null; then
            docker compose restart
        else
            docker-compose restart
        fi
        echo "✓ Milvus 已重启"
        ;;

    4)
        echo "Milvus 服务状态："
        echo ""
        if docker compose version &> /dev/null; then
            docker compose ps
        else
            docker-compose ps
        fi
        echo ""
        echo "容器状态："
        docker ps | grep milvus
        ;;

    5)
        echo "查看最近的日志（按 Ctrl+C 退出）："
        echo ""
        if docker compose version &> /dev/null; then
            docker compose logs -f --tail=50
        else
            docker-compose logs -f --tail=50
        fi
        ;;

    6)
        echo "⚠️  警告：此操作将删除所有 Milvus 数据！"
        read -p "确定要继续吗？(输入 YES 确认): " confirm
        if [ "$confirm" = "YES" ]; then
            echo "正在清理数据..."
            if docker compose version &> /dev/null; then
                docker compose down -v
            else
                docker-compose down -v
            fi
            rm -rf volumes/
            echo "✓ 数据已清理"
        else
            echo "操作已取消"
        fi
        ;;

    0)
        echo "退出"
        exit 0
        ;;

    *)
        echo "无效选项"
        exit 1
        ;;
esac

echo ""
echo "======================================"