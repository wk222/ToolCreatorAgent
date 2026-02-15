"""
智能体状态存储模块

实现子智能体定义的存储、序列化和反序列化
支持智能体的持久化和跨会话复用以文件夹形式存储
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import json
import time
import os
import shutil
from pathlib import Path


@dataclass
class AgentDefinition:
    """
    智能体定义数据结构
    
    包含创建一个子智能体所需的所有信息
    """
    name: str                           # 智能体名称（唯一标识）
    role: str                           # 角色描述
    description: str                    # 功能描述
    system_prompt: str                  # 系统提示词
    tools: List[str] = field(default_factory=list)  # 可用工具名称列表
    model: str = "gemini-3-flash-preview"               # 使用的模型
    temperature: float = 0.7           # 温度参数
    capabilities: List[str] = field(default_factory=list)  # 能力标签
    created_at: float = field(default_factory=time.time)
    usage_count: int = 0
    enabled: bool = True               # 是否启用（可临时禁用）
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'name': self.name,
            'role': self.role,
            'description': self.description,
            'system_prompt': self.system_prompt,
            'tools': self.tools,
            'model': self.model,
            'temperature': self.temperature,
            'capabilities': self.capabilities,
            'created_at': self.created_at,
            'usage_count': self.usage_count,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentDefinition':
        """从字典反序列化"""
        return cls(
            name=data.get('name', ''),
            role=data.get('role', ''),
            description=data.get('description', ''),
            system_prompt=data.get('system_prompt', ''),
            tools=data.get('tools', []),
            model=data.get('model', 'gemini-3-flash-preview'),
            temperature=data.get('temperature', 0.7),
            capabilities=data.get('capabilities', []),
            created_at=data.get('created_at', time.time()),
            usage_count=data.get('usage_count', 0),
            enabled=data.get('enabled', True)
        )


class AgentStorage:
    """
    智能体存储类
    
    管理动态创建的子智能体定义
    基于文件系统存储，每个智能体一个独立文件夹
    """
    
    def __init__(self, base_dir: str = "agents_workspace"):
        """
        初始化智能体存储
        
        Args:
            base_dir: 基础存储目录
        """
        self.base_dir = base_dir
        self.agents: Dict[str, AgentDefinition] = {}
        self._ensure_base_dir()
        self._load_agents()
    
    def _ensure_base_dir(self):
        """确保基础目录存在"""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
    def _load_agents(self):
        """从磁盘加载所有智能体"""
        self.agents = {}
        if not os.path.exists(self.base_dir):
            return

        # 遍历基础目录下的子目录
        for entry in os.scandir(self.base_dir):
            if entry.is_dir():
                config_path = os.path.join(entry.path, "agent_config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            agent = AgentDefinition.from_dict(data)
                            self.agents[agent.name] = agent
                    except Exception as e:
                        print(f"Error loading agent from {config_path}: {e}")

    def _save_agent(self, agent: AgentDefinition):
        """保存单个智能体到磁盘"""
        agent_dir = os.path.join(self.base_dir, agent.name)
        if not os.path.exists(agent_dir):
            os.makedirs(agent_dir)
            
        # 同时也确保 tools 目录存在
        tools_dir = os.path.join(agent_dir, "tools")
        if not os.path.exists(tools_dir):
            os.makedirs(tools_dir)
            
        config_path = os.path.join(agent_dir, "agent_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(agent.to_dict(), f, ensure_ascii=False, indent=2)

    def add_agent(self, definition: AgentDefinition) -> bool:
        """
        添加智能体定义并保存到磁盘
        
        Args:
            definition: 智能体定义
            
        Returns:
            bool: 是否添加成功（False表示已存在）
        """
        if definition.name in self.agents:
            return False
        
        self.agents[definition.name] = definition
        self._save_agent(definition)
        return True
    
    def get_agent(self, name: str) -> Optional[AgentDefinition]:
        """获取智能体定义"""
        return self.agents.get(name)
    
    def remove_agent(self, name: str) -> bool:
        """删除智能体及其目录"""
        if name in self.agents:
            del self.agents[name]
            
            # 删除磁盘文件
            agent_dir = os.path.join(self.base_dir, name)
            if os.path.exists(agent_dir):
                try:
                    shutil.rmtree(agent_dir)
                except Exception as e:
                    print(f"Error removing agent directory {agent_dir}: {e}")
            
            return True
        return False
    
    def update_agent(self, name: str, updates: Dict[str, Any]) -> bool:
        """更新智能体定义并保存"""
        if name not in self.agents:
            return False
        
        agent = self.agents[name]
        for key, value in updates.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self._save_agent(agent)
        return True
    
    def increment_usage(self, name: str):
        """增加智能体使用计数并保存"""
        if name in self.agents:
            self.agents[name].usage_count += 1
            self._save_agent(self.agents[name])
    
    def toggle_agent(self, name: str, enabled: bool) -> bool:
        """启用或禁用智能体"""
        if name not in self.agents:
            return False
        self.agents[name].enabled = enabled
        self._save_agent(self.agents[name])
        return True
    
    def add_tool_to_agent(self, agent_name: str, tool_name: str) -> bool:
        """给智能体追加工具"""
        if agent_name not in self.agents:
            return False
        if tool_name not in self.agents[agent_name].tools:
            self.agents[agent_name].tools.append(tool_name)
            self._save_agent(self.agents[agent_name])
        return True
    
    def remove_tool_from_agent(self, agent_name: str, tool_name: str) -> bool:
        """从智能体移除工具"""
        if agent_name not in self.agents:
            return False
        if tool_name in self.agents[agent_name].tools:
            self.agents[agent_name].tools.remove(tool_name)
            self._save_agent(self.agents[agent_name])
            return True
        return False
    
    def list_agents(self) -> Dict[str, str]:
        """列出所有智能体（仅返回名称和描述）"""
        return {
            name: agent.description
            for name, agent in self.agents.items()
        }
    
    def get_agents_by_capability(self, capability: str) -> List[AgentDefinition]:
        """根据能力标签查找智能体"""
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'agents': {
                name: agent.to_dict()
                for name, agent in self.agents.items()
            },
            'count': len(self.agents),
            'timestamp': time.time(),
            'base_dir': self.base_dir
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentStorage':
        """
        从字典反序列化
        注意：这通常用于恢复状态，但为了保持与磁盘同步，
        我们优先使用磁盘上的数据，除非指定了新的 base_dir
        """
        base_dir = data.get('base_dir', 'agents_workspace')
        storage = cls(base_dir=base_dir)
        
        # 内存中的数据可能比磁盘新（如果仅做了内存更新而未保存），
        # 但在这个设计中我们假定写操作也是同步到磁盘的。
        # 这里我们可以合并数据
        agents_data = data.get('agents', {})
        for name, agent_dict in agents_data.items():
            if name not in storage.agents:
                 storage.agents[name] = AgentDefinition.from_dict(agent_dict)
        
        return storage
    
    def export_to_json(self, filepath: str):
        """导出到JSON文件（仅导出当前状态的快照）"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def import_from_json(cls, filepath: str) -> 'AgentStorage':
        """从JSON文件导入"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class AgentContext:
    """
    智能体上下文数据结构
    
    存储在 LangGraph Runtime.context 中
    用于持久化智能体定义和执行状态
    """
    # 智能体定义字典 {agent_name: agent_definition}
    agent_definitions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 智能体使用统计 {agent_name: usage_count}
    agent_usage: Dict[str, int] = field(default_factory=dict)
    
    # 当前活跃的子智能体
    active_agents: List[str] = field(default_factory=list)
    
    # 智能体间通信历史
    communication_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'agent_definitions': self.agent_definitions,
            'agent_usage': self.agent_usage,
            'active_agents': self.active_agents,
            'communication_history': self.communication_history[-100:]  # 只保留最近100条
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentContext':
        """从字典反序列化"""
        if not isinstance(data, dict):
            return cls()
        
        return cls(
            agent_definitions=data.get('agent_definitions', {}),
            agent_usage=data.get('agent_usage', {}),
            active_agents=data.get('active_agents', []),
            communication_history=data.get('communication_history', [])
        )
    
    def record_communication(self, from_agent: str, to_agent: str, message: str, response: str):
        """记录智能体间通信"""
        self.communication_history.append({
            'from': from_agent,
            'to': to_agent,
            'message': message,
            'response': response,
            'timestamp': time.time()
        })
