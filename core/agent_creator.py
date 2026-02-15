"""
动态智能体创建器 - 核心创新模块

实现智能体的元元编程能力：
1. 主智能体根据需求自主创建子智能体
2. 子智能体具有独立的角色、工具和能力
3. 支持智能体间的任务委派和协作
4. 子智能体可持久化和跨会话复用

这是"工具创建"能力的升级版——"智能体创建"能力
"""
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from langchain.tools import BaseTool
from langchain_openai import ChatOpenAI
import json
import time
import os

from .agent_storage import AgentStorage, AgentDefinition, AgentContext
from .tool_storage import ToolStorage


class AgentCreatorInput(BaseModel):
    """智能体创建器的输入参数模型"""
    agent_name: str = Field(
        description="智能体名称（英文+下划线，如 data_analyst）"
    )
    role: str = Field(
        description="智能体角色（如：数据分析师、代码审查员、文档撰写者）"
    )
    description: str = Field(
        description="智能体功能描述，清晰说明该智能体的专长和用途"
    )
    system_prompt: str = Field(
        description="""智能体的系统提示词，定义其行为和能力。
示例：
"你是一个专业的数据分析师，擅长：
1. 数据清洗和预处理
2. 统计分析和可视化
3. 生成分析报告
请用专业但易懂的语言回答问题。"
"""
    )
    capabilities: str = Field(
        description="""能力标签（JSON数组格式），用于分类和查找。
示例：["数据分析", "Python", "可视化"]
""",
        default="[]"
    )
    model: str = Field(
        description="使用的模型（目前只有 gemini-3-flash-preview）",
        default="gemini-3-flash-preview"
    )
    temperature: float = Field(
        description="温度参数（0-1，越高越有创造性）",
        default=0.7
    )


class AgentCreatorTool(BaseTool):
    """
    动态智能体创建器 - 核心创新
    
    让主智能体能够创建专门化的子智能体
    """
    name: str = "create_agent"
    description: str = """
🤖 智能体制造器 - 创建专门化的子智能体

**核心能力**：
- ✅ 动态创建具有特定角色的子智能体
- ✅ 子智能体在当前对话中持久化
- ✅ 可以委派任务给子智能体
- ✅ 支持多智能体协作

**适用场景**：
1. 需要特定领域专家（如数据分析师、代码审查员）
2. 需要分工协作完成复杂任务
3. 需要不同风格/角色的回答
4. 构建智能体团队

**示例**：
"创建一个数据分析师智能体，专门负责分析销售数据"
"创建一个代码审查员，帮我检查代码质量"
"""
    args_schema: Type[BaseModel] = AgentCreatorInput
    
    # 存储引用
    agent_storage: Any = Field(default=None, exclude=True)
    tool_storage: Any = Field(default=None, exclude=True)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, agent_storage=None, tool_storage=None, **kwargs):
        super().__init__(agent_storage=agent_storage, tool_storage=tool_storage, **kwargs)
    
    def _run(
        self,
        agent_name: str,
        role: str,
        description: str,
        system_prompt: str,
        capabilities: str = "[]",
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.7
    ) -> str:
        """执行智能体创建"""
        
        # 验证名称格式
        if not agent_name.replace('_', '').isalnum():
            return json.dumps({
                "success": False,
                "error": "智能体名称只能包含字母、数字和下划线"
            }, ensure_ascii=False)
        
        # 解析能力标签
        try:
            caps = json.loads(capabilities) if isinstance(capabilities, str) else capabilities
            if not isinstance(caps, list):
                caps = []
        except:
            caps = []
        
        # 创建智能体定义
        agent_def = AgentDefinition(
            name=agent_name,
            role=role,
            description=description,
            system_prompt=system_prompt,
            tools=[],  # 子智能体可以使用的工具（后续可扩展）
            model=model,
            temperature=temperature,
            capabilities=caps,
            created_at=time.time(),
            usage_count=0,
            enabled=True
        )
        
        # 保存到存储
        if not self.agent_storage.add_agent(agent_def):
            return json.dumps({
                "success": False,
                "error": f"智能体 '{agent_name}' 已存在"
            }, ensure_ascii=False)
        
        # 获取智能体目录路径 (推断)
        agent_dir = os.path.join(self.agent_storage.base_dir, agent_name)
        
        return json.dumps({
            "success": True,
            "agent_name": agent_name,
            "message": f"✅ 智能体 '{agent_name}' 创建成功！",
            "usage": f"现在可以使用 delegate_to_agent 工具将任务委派给 {agent_name}",
            "details": {
                "role": role,
                "description": description,
                "capabilities": caps,
                "directory": agent_dir,
                "tools_dir": os.path.join(agent_dir, "tools")
            }
        }, ensure_ascii=False)


class DelegateToAgentInput(BaseModel):
    """任务委派工具的输入参数"""
    agent_name: str = Field(
        description="目标智能体名称"
    )
    task: str = Field(
        description="要委派的任务描述"
    )
    context: str = Field(
        description="任务上下文信息（可选）",
        default=""
    )


class DelegateToAgentTool(BaseTool):
    """
    任务委派工具 - 将任务委派给子智能体执行
    """
    name: str = "delegate_to_agent"
    description: str = """
📤 任务委派器 - 将任务委派给子智能体

**使用方法**：
1. 指定目标智能体名称
2. 描述要执行的任务
3. 提供必要的上下文

**示例**：
delegate_to_agent(
    agent_name="data_analyst",
    task="分析这份销售数据，找出增长趋势",
    context="数据包含2024年1-6月的销售记录"
)
"""
    args_schema: Type[BaseModel] = DelegateToAgentInput
    
    agent_storage: Any = Field(default=None, exclude=True)
    tool_storage: Any = Field(default=None, exclude=True)
    llm_factory: Any = Field(default=None, exclude=True)  # LLM工厂函数
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, agent_storage=None, tool_storage=None, llm_factory=None, **kwargs):
        super().__init__(
            agent_storage=agent_storage,
            tool_storage=tool_storage,
            llm_factory=llm_factory,
            **kwargs
        )
    
    def _run(
        self,
        agent_name: str,
        task: str,
        context: str = ""
    ) -> str:
        """执行任务委派"""
        
        # 获取智能体定义
        agent_def = self.agent_storage.get_agent(agent_name)
        if not agent_def:
            available = list(self.agent_storage.agents.keys())
            return json.dumps({
                "success": False,
                "error": f"智能体 '{agent_name}' 不存在",
                "available_agents": available
            }, ensure_ascii=False)
        
        # 检查是否启用
        if not agent_def.enabled:
            return json.dumps({
                "success": False,
                "error": f"智能体 '{agent_name}' 已被禁用，请先在管理面板中启用后再委派任务"
            }, ensure_ascii=False)
        
        # 增加使用计数
        self.agent_storage.increment_usage(agent_name)
        
        try:
            # 准备子智能体的工具存储
            # 获取该智能体专属的工具目录
            agent_dir = os.path.join(self.agent_storage.base_dir, agent_name)
            agent_tools_dir = os.path.join(agent_dir, "tools")
            
            # 创建专门针对该智能体的工具存储实例
            # 这样子智能体只能访问和管理自己的工具
            agent_tool_storage = ToolStorage(base_dir=agent_tools_dir)
            
            # 创建智能体实例
            agent_instance = create_sub_agent_instance(
                agent_def=agent_def,
                tool_storage=agent_tool_storage,
                llm_factory=self.llm_factory
            )
            
            # 调用子智能体
            response = agent_instance.invoke(task, context)
            
            return json.dumps({
                "success": True,
                "agent_name": agent_name,
                "role": agent_def.role,
                "task": task,
                "response": response,
                "usage_count": agent_def.usage_count
            }, ensure_ascii=False, indent=2)
            
        except Exception as e:
            import traceback
            return json.dumps({
                "success": False,
                "agent_name": agent_name,
                "error": str(e),
                "traceback": traceback.format_exc()
            }, ensure_ascii=False)


class ListAgentsInput(BaseModel):
    """列出智能体工具的输入"""
    capability_filter: str = Field(
        description="按能力筛选（可选）",
        default=""
    )


class ListAgentsTool(BaseTool):
    """列出所有已创建的智能体"""
    name: str = "list_agents"
    description: str = "📋 列出所有已创建的子智能体及其信息"
    args_schema: Type[BaseModel] = ListAgentsInput
    
    agent_storage: Any = Field(default=None, exclude=True)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, agent_storage=None, **kwargs):
        super().__init__(agent_storage=agent_storage, **kwargs)
    
    def _run(self, capability_filter: str = "") -> str:
        if capability_filter:
            agents = self.agent_storage.get_agents_by_capability(capability_filter)
            agent_list = [a.to_dict() for a in agents]
        else:
            agent_list = [a.to_dict() for a in self.agent_storage.agents.values()]
        
        return json.dumps({
            "success": True,
            "count": len(agent_list),
            "agents": agent_list
        }, ensure_ascii=False, indent=2)


class RemoveAgentInput(BaseModel):
    """删除智能体工具的输入"""
    agent_name: str = Field(description="要删除的智能体名称")


class RemoveAgentTool(BaseTool):
    """删除已创建的智能体"""
    name: str = "remove_agent"
    description: str = "🗑️ 删除一个已创建的子智能体"
    args_schema: Type[BaseModel] = RemoveAgentInput
    
    agent_storage: Any = Field(default=None, exclude=True)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, agent_storage=None, **kwargs):
        super().__init__(agent_storage=agent_storage, **kwargs)
    
    def _run(self, agent_name: str) -> str:
        if self.agent_storage.remove_agent(agent_name):
            return json.dumps({
                "success": True,
                "message": f"✅ 智能体 '{agent_name}' 已删除"
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "success": False,
                "error": f"智能体 '{agent_name}' 不存在"
            }, ensure_ascii=False)


# ========== 工厂函数 ==========

def get_agent_creator_tools(
    agent_storage: AgentStorage,
    tool_storage=None,
    llm_factory=None
) -> List[BaseTool]:
    """
    获取智能体创建相关的所有工具
    
    Args:
        agent_storage: AgentStorage 实例
        tool_storage: ToolStorage 实例（可选，用于给子智能体分配工具）
        llm_factory: LLM工厂函数（可选）
        
    Returns:
        工具列表
    """
    return [
        AgentCreatorTool(agent_storage=agent_storage, tool_storage=tool_storage),
        DelegateToAgentTool(
            agent_storage=agent_storage,
            tool_storage=tool_storage,
            llm_factory=llm_factory
        ),
        ListAgentsTool(agent_storage=agent_storage),
        RemoveAgentTool(agent_storage=agent_storage)
    ]


def create_sub_agent_instance(
    agent_def: AgentDefinition,
    tool_storage=None,
    llm_factory=None
):
    """
    根据智能体定义创建实际的智能体实例
    
    这是一个高级功能，可以创建具有完整工具能力的子智能体
    
    Args:
        agent_def: 智能体定义
        tool_storage: 工具存储（用于获取子智能体可用的工具）
        llm_factory: LLM工厂函数
        
    Returns:
        可调用的智能体实例
    """
    from langchain.agents import create_agent
    
    # 创建LLM
    if llm_factory:
        llm = llm_factory(model=agent_def.model, temperature=agent_def.temperature)
    else:
        llm = ChatOpenAI(model=agent_def.model, temperature=agent_def.temperature)
    
    # 获取子智能体可用的工具
    tools = []
    if tool_storage:
        from .tool_creator import get_dynamic_tools
        all_tools = get_dynamic_tools(tool_storage)
        
        # 如果定义中指定了工具列表，则筛选
        if agent_def.tools:
            tools = [t for t in all_tools if t.name in agent_def.tools]
        else:
            # 如果没有指定，但提供了专属存储，则加载存储中的所有工具
            tools = all_tools
            
    # 使用新版 create_agent 创建智能体图
    agent_graph = create_agent(
        model=llm,
        tools=tools,
        system_prompt=agent_def.system_prompt
    )
    
    # 包装 invoke 方法以适配接口
    class AgentWrapper:
        def __init__(self, graph):
            self.graph = graph
            
        def invoke(self, task: str, context: str = "") -> str:
            # 构造输入消息
            messages = [{"role": "user", "content": f"{task}\n\n上下文：{context}"}]
            
            # 调用图
            response = self.graph.invoke({"messages": messages})
            
            # 提取最后一条消息的回复
            final_messages = response.get("messages", [])
            if final_messages:
                return final_messages[-1].content
            return "（无回复）"

    return AgentWrapper(agent_graph)
