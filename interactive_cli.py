"""
交互式CLI - 工具创建智能体
允许用户通过命令行与智能体交互，创建和使用工具
"""
import json
from langchain_openai import ChatOpenAI
from core import ToolStorage, get_tool_creator_tools, DynamicToolMiddleware
from core.tool_creator import get_dynamic_tools
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver


def load_config():
    """加载配置文件"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


class InteractiveCLI:
    def __init__(self):
        """初始化CLI"""
        self.config = load_config()
        self.llm_config = self.config['llm_config']
        self.agent_config = self.config['agent_config']
        self.storage = ToolStorage()
        self.middleware = DynamicToolMiddleware()
        self.agent = None
        self.thread_id = self.agent_config['thread_id']
        
    def initialize_agent(self):
        """初始化智能体"""
        print("初始化智能体...")
        
        # 创建模型
        llm = ChatOpenAI(
            base_url=self.llm_config['api_base'],
            api_key=self.llm_config['api_key'],
            model=self.llm_config['model'],
            temperature=self.llm_config['temperature']
        )
        
        # 获取工具
        creator_tools = get_tool_creator_tools(self.storage)
        dynamic_tools = get_dynamic_tools(self.storage)
        all_tools = creator_tools + dynamic_tools
        
        # 创建智能体
        self.agent = create_agent(
            model=llm,
            tools=all_tools,
            system_prompt="""你是一个具有工具创建能力的智能助手。

你的能力：
1. 创建工具：当用户要求创建工具时，使用 create_custom_tool 函数
2. 使用工具：可以调用已创建的动态工具
3. 查看工具：可以列出所有已创建的工具

创建工具时的注意事项：
- 工具代码必须设置 result 变量来返回结果
- 仔细理解用户需求，创建实用的工具
- 为工具提供清晰的名称和描述

请友好地与用户交互，帮助他们创建和使用工具。""",
            middleware=[self.middleware],
            checkpointer=MemorySaver()
        )
        
        print("✅ 智能体初始化完成！\n")
        
    def show_tools(self):
        """显示所有已创建的工具"""
        tools = self.storage.list_tools()
        if not tools:
            print("\n📦 当前没有已创建的工具\n")
            return
        
        print("\n" + "=" * 60)
        print("  已创建的工具列表")
        print("=" * 60)
        
        for name, info in tools.items():
            print(f"\n🔧 {name}")
            print(f"   描述: {info['description']}")
            print(f"   参数: ", end="")
            if info['parameters']:
                params = [f"{p['name']}({p['type']})" for p in info['parameters']]
                print(", ".join(params))
            else:
                print("无")
            print(f"   使用次数: {info['usage_count']}")
        
        print("\n" + "=" * 60 + "\n")
    
    def show_help(self):
        """显示帮助信息"""
        print("\n" + "=" * 60)
        print("  命令列表")
        print("=" * 60)
        print()
        print("  /help    - 显示此帮助信息")
        print("  /tools   - 显示所有已创建的工具")
        print("  /clear   - 清除所有工具")
        print("  /reset   - 重置会话")
        print("  /quit    - 退出程序")
        print()
        print("  其他输入会发送给智能体处理")
        print("=" * 60 + "\n")
        
    def chat(self, message):
        """与智能体对话"""
        if not self.agent:
            print("❌ 智能体未初始化")
            return
        
        try:
            # ⭐ 修复点1：记录对话前的工具数量
            tools_before = len(self.storage.tools)
            
            config_dict = {
                "configurable": {
                    "thread_id": self.thread_id
                }
            }
            
            response = self.agent.invoke(
                {
                    "messages": [{
                        "role": "user",
                        "content": message
                    }]
                },
                config=config_dict
            )
            
            # 提取回复
            messages = response.get("messages", [])
            
            # ⭐ 修复点2：检测是否创建了新工具
            tools_after = len(self.storage.tools)
            created_new_tool = False
            
            for msg in messages:
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get('name') if isinstance(tc, dict) else getattr(tc, 'name', None)
                        if tool_name == 'create_custom_tool':
                            created_new_tool = True
                            break
            
            # ⭐ 修复点3：如果创建了新工具，重新初始化智能体
            if created_new_tool or tools_after > tools_before:
                print(f"\n[INFO] 检测到新工具创建（{tools_before} -> {tools_after}），重新加载工具...")
                self.initialize_agent()
                print(f"[INFO] 工具重新加载完成！当前可用工具数：{tools_after}\n")
            
            # 显示消息
            if messages:
                # 显示所有消息（包括工具调用）
                for msg in messages:
                    if hasattr(msg, 'content') and msg.content:
                        if msg.type == 'ai':
                            print(f"\n🤖 助手: {msg.content}")
                    elif hasattr(msg, 'tool_calls') and msg.tool_calls:
                        # 显示工具调用信息
                        for tool_call in msg.tool_calls:
                            print(f"\n🔧 调用工具: {tool_call.get('name', 'unknown')}")
                
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_tools(self):
        """清除所有工具"""
        confirm = input("⚠️  确认清除所有工具？(yes/no): ")
        if confirm.lower() in ['yes', 'y']:
            tools = list(self.storage.list_tools().keys())
            for tool_name in tools:
                self.storage.remove_tool(tool_name)
            print("✅ 已清除所有工具")
            # 重新初始化智能体以更新工具列表
            self.initialize_agent()
        else:
            print("❌ 取消操作")
    
    def reset_session(self):
        """重置会话"""
        import time
        self.thread_id = f"test_session_{int(time.time())}"
        print(f"✅ 会话已重置，新会话ID: {self.thread_id}")
    
    def run(self):
        """运行CLI"""
        print("\n" + "=" * 60)
        print("    🤖 工具创建智能体 - 交互式CLI")
        print("=" * 60)
        print()
        print("欢迎使用工具创建智能体！")
        print("你可以让我创建各种工具，然后使用它们。")
        print()
        print("输入 /help 查看命令列表")
        print("=" * 60 + "\n")
        
        # 初始化智能体
        try:
            self.initialize_agent()
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            return
        
        # 主循环
        while True:
            try:
                user_input = input("\n👤 你: ").strip()
                
                if not user_input:
                    continue
                
                # 处理命令
                if user_input.startswith('/'):
                    command = user_input.lower()
                    
                    if command == '/quit' or command == '/exit':
                        print("\n👋 再见！\n")
                        break
                    elif command == '/help':
                        self.show_help()
                    elif command == '/tools':
                        self.show_tools()
                    elif command == '/clear':
                        self.clear_tools()
                    elif command == '/reset':
                        self.reset_session()
                    else:
                        print(f"❌ 未知命令: {command}")
                        print("输入 /help 查看可用命令")
                else:
                    # 发送给智能体
                    self.chat(user_input)
                    
            except KeyboardInterrupt:
                print("\n\n👋 再见！\n")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")


def main():
    """主函数"""
    cli = InteractiveCLI()
    cli.run()


if __name__ == "__main__":
    main()

