"""
测试 RAG 服务的客户端示例
"""
import requests
import json

# RAG 服务地址
RAG_SERVICE_URL = "http://localhost:8001"

def test_simple_chat():
    """测试简单对话"""
    print("\n=== 测试 RAG 对话 ===")

    response = requests.post(
        f"{RAG_SERVICE_URL}/chat",
        json={
            "question": "人工智能在医疗领域有哪些应用？",
            "use_rag": True,
            "top_k": 5,
            "search_type": "hybrid"
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"\n问题: 人工智能在医疗领域有哪些应用？")
        print(f"\n回答: {result['answer']}")
        print(f"\n参考来源:")
        for source in result['sources']:
            print(f"  - {source['source']}: {source['section']} (相关度: {source['score']:.2f})")
    else:
        print(f"请求失败: {response.text}")

def test_without_rag():
    """测试不使用 RAG 的对话"""
    print("\n=== 测试普通对话（不使用 RAG）===")

    response = requests.post(
        f"{RAG_SERVICE_URL}/chat",
        json={
            "question": "今天天气怎么样？",
            "use_rag": False
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"\n问题: 今天天气怎么样？")
        print(f"\n回答: {result['answer']}")
    else:
        print(f"请求失败: {response.text}")

def test_conversation_with_history():
    """测试带历史的对话"""
    print("\n=== 测试多轮对话 ===")

    session_id = "test-session-001"

    # 第一轮对话
    response1 = requests.post(
        f"{RAG_SERVICE_URL}/chat/with-history",
        params={"session_id": session_id},
        json={
            "question": "什么是人工智能？",
            "use_rag": True,
            "top_k": 3
        }
    )

    if response1.status_code == 200:
        result1 = response1.json()
        print(f"\n第一轮 - 问: 什么是人工智能？")
        print(f"答: {result1['answer'][:200]}...")

    # 第二轮对话（会记住上下文）
    response2 = requests.post(
        f"{RAG_SERVICE_URL}/chat/with-history",
        params={"session_id": session_id},
        json={
            "question": "它在制造业有什么应用？",  # "它"指代人工智能
            "use_rag": True,
            "top_k": 3
        }
    )

    if response2.status_code == 200:
        result2 = response2.json()
        print(f"\n第二轮 - 问: 它在制造业有什么应用？")
        print(f"答: {result2['answer'][:200]}...")
        print(f"\n对话历史长度: {result2['history_length']} 条消息")

def test_streaming():
    """测试流式输出"""
    print("\n=== 测试流式输出 ===")

    response = requests.post(
        f"{RAG_SERVICE_URL}/chat/stream",
        json={
            "question": "介绍一下大模型技术",
            "use_rag": True,
            "top_k": 3
        },
        stream=True
    )

    print("问: 介绍一下大模型技术")
    print("答: ", end='')

    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if data['type'] == 'content':
                    print(data['data'], end='', flush=True)
                elif data['type'] == 'done':
                    print("\n[完成]")
                    break

if __name__ == "__main__":
    # 检查服务健康
    try:
        health = requests.get(f"{RAG_SERVICE_URL}/health")
        if health.status_code == 200:
            print("✓ RAG 服务正常运行")
            health_data = health.json()
            print(f"  - Milvus API: {health_data['milvus_api']}")
            print(f"  - LLM: {health_data['llm']}")

        # 运行测试
        test_simple_chat()
        test_without_rag()
        test_conversation_with_history()
        # test_streaming()  # 流式输出测试（可选）

    except Exception as e:
        print(f"❌ 无法连接 RAG 服务: {e}")
        print("请确保 rag_service.py 正在运行 (端口 8001)")