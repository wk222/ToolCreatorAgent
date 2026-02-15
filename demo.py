"""
演示程序：展示智能体的自主工具创建能力

运行方式：
python demo.py
"""
import os
from agent import create_tool_creator_agent


def print_section(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def demo_create_and_use_tool():
    """演示1：创建工具并使用"""
    print_section("演示1：创建工具并使用")
    
    # 创建智能体
    agent = create_tool_creator_agent(
        model="gpt-4",
        thread_id="demo-session-1"
    )
    
    # 步骤1：创建工具
    print("👤 用户: 创建一个计算圆面积的工具，输入半径，返回面积")
    response = agent.chat("创建一个计算圆面积的工具，输入半径，返回面积")
    print(f"🤖 助手: {response}\n")
    
    # 步骤2：使用工具
    print("👤 用户: 用这个工具计算半径为5的圆的面积")
    response = agent.chat("用这个工具计算半径为5的圆的面积")
    print(f"🤖 助手: {response}\n")
    
    # 步骤3：再次使用
    print("👤 用户: 再算一下半径为10的")
    response = agent.chat("再算一下半径为10的")
    print(f"🤖 助手: {response}\n")


def demo_cross_session_persistence():
    """演示2：跨会话持久化"""
    print_section("演示2：跨会话持久化")
    
    # 第一个会话：创建工具
    print("🔹 第一个会话（创建工具）\n")
    agent1 = create_tool_creator_agent(
        model="gpt-4",
        thread_id="persistence-demo"
    )
    
    print("👤 用户: 创建一个计算矩形面积的工具")
    response = agent1.chat("创建一个计算矩形面积的工具，输入长和宽，返回面积")
    print(f"🤖 助手: {response}\n")
    
    # 模拟会话结束
    del agent1
    print("💤 会话结束...\n")
    
    # 第二个会话：使用之前创建的工具
    print("🔹 第二个会话（使用之前的工具）\n")
    agent2 = create_tool_creator_agent(
        model="gpt-4",
        thread_id="persistence-demo"  # 同一个 thread_id
    )
    
    print("👤 用户: 计算长为8、宽为5的矩形面积")
    response = agent2.chat("计算长为8、宽为5的矩形面积")
    print(f"🤖 助手: {response}\n")
    
    print("✅ 工具在第二个会话中自动恢复并使用！")


def demo_multiple_tools():
    """演示3：创建多个工具"""
    print_section("演示3：创建多个工具")
    
    agent = create_tool_creator_agent(
        model="gpt-4",
        thread_id="multi-tools-demo"
    )
    
    # 创建工具1
    print("👤 用户: 创建一个华氏度转摄氏度的工具")
    response = agent.chat("创建一个华氏度转摄氏度的工具，公式是 (F - 32) * 5/9")
    print(f"🤖 助手: {response}\n")
    
    # 创建工具2
    print("👤 用户: 再创建一个摄氏度转华氏度的工具")
    response = agent.chat("再创建一个摄氏度转华氏度的工具，公式是 C * 9/5 + 32")
    print(f"🤖 助手: {response}\n")
    
    # 使用工具1
    print("👤 用户: 100华氏度是多少摄氏度？")
    response = agent.chat("100华氏度是多少摄氏度？")
    print(f"🤖 助手: {response}\n")
    
    # 使用工具2
    print("👤 用户: 那25摄氏度是多少华氏度？")
    response = agent.chat("那25摄氏度是多少华氏度？")
    print(f"🤖 助手: {response}\n")
    
    # 查看工具列表
    print("📋 已创建的工具:")
    tools = agent.list_tools()
    for name, desc in tools.items():
        print(f"  - {name}: {desc}")


def demo_tool_export_import():
    """演示4：工具导出和导入"""
    print_section("演示4：工具导出和导入")
    
    # 会话A：创建工具并导出
    print("🔹 会话A：创建工具\n")
    agentA = create_tool_creator_agent(
        model="gpt-4",
        thread_id="export-demo"
    )
    
    print("👤 用户: 创建一个计算BMI的工具")
    response = agentA.chat("创建一个计算BMI的工具，公式是 体重(kg) / 身高(m)²")
    print(f"🤖 助手: {response}\n")
    
    # 导出工具
    export_file = "my_tools.json"
    agentA.export_tools(export_file)
    print(f"📤 工具已导出到 {export_file}\n")
    
    # 会话B：导入工具
    print("🔹 会话B：导入工具\n")
    agentB = create_tool_creator_agent(
        model="gpt-4",
        thread_id="import-demo"  # 不同的 thread_id
    )
    
    agentB.import_tools(export_file)
    print(f"📥 工具已从 {export_file} 导入\n")
    
    print("👤 用户: 计算体重70kg、身高1.75m的BMI")
    response = agentB.chat("计算体重70kg、身高1.75m的BMI")
    print(f"🤖 助手: {response}\n")
    
    print("✅ 工具在不同会话间成功分享！")
    
    # 清理
    if os.path.exists(export_file):
        os.remove(export_file)
        print(f"\n🗑️  已删除示例文件 {export_file}")


def demo_complex_tool():
    """演示5：创建复杂工具"""
    print_section("演示5：创建复杂工具")
    
    agent = create_tool_creator_agent(
        model="gpt-4",
        thread_id="complex-demo"
    )
    
    print("👤 用户: 创建一个评分工具，根据分数给出等级")
    prompt = """
    创建一个评分工具，功能：
    - 输入：score（分数，0-100）
    - 输出：等级和评语
    - 规则：
      * 90-100: A 优秀
      * 80-89: B 良好  
      * 70-79: C 中等
      * 60-69: D 及格
      * 0-59: F 不及格
    """
    response = agent.chat(prompt)
    print(f"🤖 助手: {response}\n")
    
    # 测试不同分数
    test_scores = [95, 75, 50]
    for score in test_scores:
        print(f"👤 用户: 评估分数 {score}")
        response = agent.chat(f"评估分数 {score}")
        print(f"🤖 助手: {response}\n")


def main():
    """主函数"""
    print("\n" + "🚀" * 30)
    print("    具有自主工具创建能力的智能体系统 - 演示程序")
    print("🚀" * 30)
    
    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  警告: 未设置 OPENAI_API_KEY 环境变量")
        print("请运行: export OPENAI_API_KEY='your-api-key'")
        return
    
    # 运行演示
    demos = [
        ("演示1: 创建工具并使用", demo_create_and_use_tool),
        ("演示2: 跨会话持久化", demo_cross_session_persistence),
        ("演示3: 创建多个工具", demo_multiple_tools),
        ("演示4: 工具导出和导入", demo_tool_export_import),
        ("演示5: 创建复杂工具", demo_complex_tool),
    ]
    
    print("\n可用的演示:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    
    print("\n请选择要运行的演示（输入数字，或按回车运行全部）: ", end="")
    choice = input().strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(demos):
        # 运行选中的演示
        _, demo_func = demos[int(choice) - 1]
        demo_func()
    else:
        # 运行所有演示
        for _, demo_func in demos:
            try:
                demo_func()
            except Exception as e:
                print(f"\n❌ 演示出错: {e}\n")
    
    print("\n" + "🎉" * 30)
    print("    演示完成！")
    print("🎉" * 30 + "\n")


if __name__ == "__main__":
    main()

