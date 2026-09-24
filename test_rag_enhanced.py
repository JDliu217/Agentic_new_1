"""
测试增强版 RAG 服务
包含：意图识别、查询扩展、参考片段展示
"""
import requests
import json

# RAG 服务地址
RAG_SERVICE_URL = "http://localhost:8001"

def test_with_intent_and_expansion():
    """测试意图识别和查询扩展"""

    # 测试不同领域的问题
    test_cases = [
        {
            "question": "人工智能大模型的训练需要什么样的算力支持？",
            "expected_domain": "ai"
        },
        {
            "question": "股票投资的风险管理策略有哪些？",
            "expected_domain": "finance"
        },
        {
            "question": "合同违约的法律责任如何认定？",
            "expected_domain": "law"
        },
        {
            "question": "今天天气怎么样？",
            "expected_domain": "general"
        }
    ]

    for case in test_cases:
        print("\n" + "="*60)
        print(f"问题: {case['question']}")
        print(f"预期领域: {case['expected_domain']}")
        print("-"*60)

        response = requests.post(
            f"{RAG_SERVICE_URL}/chat",
            json={
                "question": case['question'],
                "use_rag": True,
                "top_k": 5,
                "search_type": "hybrid",
                "enable_query_expansion": True,
                "enable_intent_detection": True
            }
        )

        if response.status_code == 200:
            result = response.json()

            # 显示识别的领域
            print(f"\n识别领域: {result.get('domain', 'unknown')}")

            # 显示扩展查询
            if result.get('expanded_queries'):
                print(f"\n扩展查询:")
                for i, query in enumerate(result['expanded_queries'], 1):
                    print(f"  {i}. {query}")

            # 显示引用的片段
            if result.get('referenced_fragments'):
                print(f"\n引用片段 ({len(result['referenced_fragments'])}个):")
                for frag in result['referenced_fragments'][:3]:
                    print(f"  [{frag['index']}] 来源: {frag['source']} - {frag['section']}")
                    print(f"      相关度: {frag['score']:.3f}")
                    print(f"      内容: {frag['fragment'][:100]}...")

            # 显示回答
            print(f"\n回答:")
            print(result['answer'][:500] + "..." if len(result['answer']) > 500 else result['answer'])

        else:
            print(f"请求失败: {response.status_code}")
            print(response.text)

def test_domain_filter():
    """测试特定领域检索"""
    print("\n" + "="*60)
    print("测试 AI 领域问题检索")
    print("="*60)

    response = requests.post(
        f"{RAG_SERVICE_URL}/chat",
        json={
            "question": "深度学习模型的优化方法有哪些？",
            "use_rag": True,
            "top_k": 3,
            "search_type": "hybrid",
            "enable_query_expansion": True,
            "enable_intent_detection": True
        }
    )

    if response.status_code == 200:
        result = response.json()

        print(f"领域: {result.get('domain')}")

        # 显示完整的返回结构
        print("\n返回数据结构:")
        print(json.dumps({
            "domain": result.get('domain'),
            "expanded_queries": result.get('expanded_queries'),
            "sources_count": len(result.get('sources', [])),
            "fragments_count": len(result.get('referenced_fragments', [])),
            "answer_length": len(result.get('answer', ''))
        }, ensure_ascii=False, indent=2))

def test_general_question():
    """测试通用问题（不需要 RAG）"""
    print("\n" + "="*60)
    print("测试通用问题（直接 LLM 回答）")
    print("="*60)

    response = requests.post(
        f"{RAG_SERVICE_URL}/chat",
        json={
            "question": "请解释什么是递归？",
            "use_rag": False,
            "enable_intent_detection": True
        }
    )

    if response.status_code == 200:
        result = response.json()
        print(f"\n领域: {result.get('domain')}")
        print(f"使用 RAG: 否")
        print(f"\n回答: {result['answer'][:300]}...")

def main():
    """运行所有测试"""
    try:
        # 检查服务
        health = requests.get(f"{RAG_SERVICE_URL}/health")
        if health.status_code == 200:
            print("✓ RAG 服务正常")
            health_data = health.json()
            print(f"  - Milvus API: {health_data['milvus_api']}")
            print(f"  - LLM: {health_data['llm']}")

            # 运行测试
            test_with_intent_and_expansion()
            test_domain_filter()
            test_general_question()

        else:
            print("❌ RAG 服务未响应")

    except Exception as e:
        print(f"❌ 错误: {e}")
        print("请确保:")
        print("1. Milvus 正在运行")
        print("2. milvus_api.py 正在运行 (端口 8000)")
        print("3. rag_service.py 正在运行 (端口 8001)")

if __name__ == "__main__":
    main()