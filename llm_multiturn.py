import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

# 初始化客户端
client = OpenAI(
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

def print_messages(messages):
    """打印对话历史"""
    print("\n" + "="*50)
    print("当前对话历史 (messages):")
    print("="*50)
    for i, msg in enumerate(messages, 1):
        print(f"\n[{i}] {msg['role'].upper()}:")
        print(f"    {msg['content']}")
    print("="*50 + "\n")

def get_streaming_response(messages):
    """获取流式响应并实时打印"""
    response_text = ""

    # 创建流式完成请求
    completion = client.chat.completions.create(
        model="qwen-plus",
        messages=messages,
        stream=True,
        stream_options={"include_usage": True}
    )

    print("\n助手: ", end='', flush=True)

    # 流式输出响应
    for chunk in completion:
        if chunk.choices and len(chunk.choices) > 0:
            delta_content = chunk.choices[0].delta.content
            if delta_content:
                print(delta_content, end='', flush=True)
                response_text += delta_content

    print("\n")  # 响应结束后换行

    return response_text

def main():
    """主函数 - 多轮对话循环"""
    print("=" * 60)
    print("多轮对话系统已启动！")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'clear' 清空对话历史")
    print("输入 'history' 查看对话历史")
    print("=" * 60)

    # 初始化消息列表
    messages = [
        {"role": "system", "content": "You are a helpful assistant. 请用中文回答。"}
    ]

    while True:
        try:
            # 获取用户输入
            user_input = input("\n用户: ").strip()

            # 检查退出命令
            if user_input.lower() in ['quit', 'exit', '退出']:
                print("\n再见！感谢使用多轮对话系统。")
                break

            # 检查清空历史命令
            if user_input.lower() == 'clear':
                messages = [
                    {"role": "system", "content": "You are a helpful assistant. 请用中文回答。"}
                ]
                print("\n✓ 对话历史已清空")
                continue

            # 检查查看历史命令
            if user_input.lower() == 'history':
                print_messages(messages)
                continue

            # 如果输入为空，继续循环
            if not user_input:
                continue

            # 添加用户消息到历史
            messages.append({"role": "user", "content": user_input})

            # 获取并打印助手响应
            assistant_response = get_streaming_response(messages)

            # 添加助手响应到历史
            messages.append({"role": "assistant", "content": assistant_response})

            # 打印当前的messages内容
            print_messages(messages)

        except KeyboardInterrupt:
            print("\n\n程序被中断。再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            print("请重试...")

if __name__ == "__main__":
    main()