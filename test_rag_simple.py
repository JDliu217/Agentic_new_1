"""
测试简化版 RAG 服务
"""

import requests
import json

# 服务地址
RAG_URL = "http://localhost:8002"

def test_simple_rag():
    """测试简单 RAG 功能"""

    print("=" * 60)
    print("测试简化版 RAG 服务")
    print("=" * 60)

    # 测试问题列表
    test_questions = [
        "什么是人工智能？",
        "机器学习和深度学习的区别是什么？",
        "大语言模型是如何工作的？",
        "Python 编程有什么特点？",
        "如何开始学习 AI？"
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n[测试 {i}]")
        print(f"问题: {question}")
        print("-" * 40)

        try:
            # 发送请求
            response = requests.post(
                f"{RAG_URL}/chat",
                json={
                    "question": question,
                    "top_k": 5
                }
            )

            if response.status_code == 200:
                result = response.json()

                # 显示答案
                print(f"回答:\n{result['answer'][:500]}...")  # 只显示前500字符

                # 显示来源
                if result['sources']:
                    print(f"\n参考来源:")
                    for source in result['sources']:
                        print(f"  - {source}")
            else:
                print(f"错误: {response.status_code}")
                print(response.text)

        except Exception as e:
            print(f"请求失败: {e}")

        print("-" * 60)

def test_custom_question():
    """交互式测试"""
    print("\n" + "=" * 60)
    print("交互式测试 - 输入 'quit' 退出")
    print("=" * 60)

    while True:
        question = input("\n请输入你的问题: ").strip()

        if question.lower() == 'quit':
            print("退出测试")
            break

        if not question:
            continue

        try:
            # 发送请求
            response = requests.post(
                f"{RAG_URL}/chat",
                json={
                    "question": question,
                    "top_k": 5
                }
            )

            if response.status_code == 200:
                result = response.json()
                print("\n回答:")
                print(result['answer'])

                if result['sources']:
                    print("\n参考来源:")
                    for source in result['sources']:
                        print(f"  - {source}")
            else:
                print(f"错误: {response.text}")

        except Exception as e:
            print(f"请求失败: {e}")

def quick_test():
    """快速测试 - 单个问题"""
    question = "什么是 RAG 技术？"

    print(f"问题: {question}")
    print("-" * 40)

    response = requests.post(
        f"{RAG_URL}/chat",
        json={
            "question": question,
            "top_k": 3
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"回答:\n{result['answer']}")
        print(f"\n来源: {result['sources']}")
    else:
        print(f"错误: {response.text}")

if __name__ == "__main__":
    import sys

    # 检查服务是否运行
    try:
        health = requests.get(f"{RAG_URL}/health", timeout=2)
        if health.status_code != 200:
            print("⚠️ 简化版 RAG 服务未运行")
            print("请先运行: python rag_service_simple.py")
            sys.exit(1)
    except:
        print("⚠️ 无法连接到简化版 RAG 服务")
        print("请先运行: python rag_service_simple.py")
        sys.exit(1)

    # 运行测试
    print("选择测试模式:")
    print("1. 批量测试")
    print("2. 交互式测试")
    print("3. 快速测试")

    choice = input("\n请选择 (1/2/3): ").strip()

    if choice == "1":
        test_simple_rag()
    elif choice == "2":
        test_custom_question()
    elif choice == "3":
        quick_test()
    else:
        quick_test()  # 默认快速测试