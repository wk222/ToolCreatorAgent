"""
具有自主工具创建能力的智能体系统 - 核心模块

专利申请：一种具有自主工具创建和智能体创建能力的智能体系统

核心能力：
1. 工具创建（元编程）：智能体自主创建工具
2. 智能体创建（元元编程）：智能体自主创建子智能体
"""

from .tool_storage import ToolStorage, ToolContext
from .tool_creator import (
    ToolCreatorTool,
    create_dynamic_tool,
    get_tool_creator_tools,
    get_dynamic_tools
)
from .tool_middleware import DynamicToolMiddleware

# 新增：智能体创建模块
from .agent_storage import AgentStorage, AgentDefinition, AgentContext
from .agent_creator import (
    AgentCreatorTool,
    DelegateToAgentTool,
    ListAgentsTool,
    RemoveAgentTool,
    get_agent_creator_tools,
    create_sub_agent_instance
)

__all__ = [
    # 工具创建相关
    'ToolStorage',
    'ToolContext',
    'ToolCreatorTool',
    'create_dynamic_tool',
    'get_tool_creator_tools',
    'get_dynamic_tools',
    'DynamicToolMiddleware',
    # 智能体创建相关（新增）
    'AgentStorage',
    'AgentDefinition',
    'AgentContext',
    'AgentCreatorTool',
    'DelegateToAgentTool',
    'ListAgentsTool',
    'RemoveAgentTool',
    'get_agent_creator_tools',
    'create_sub_agent_instance',
]

__version__ = '2.0.0'
__author__ = 'Patent Applicant'
__patent__ = '一种具有自主工具创建和智能体创建能力的智能体系统'

