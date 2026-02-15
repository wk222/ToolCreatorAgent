"""
工具状态存储模块

实现工具定义的存储、序列化和反序列化
支持文件夹形式存储
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
import time
import os
import shutil


class ToolStorage:
    """
    工具存储类
    
    用于管理动态创建的工具定义
    支持添加、获取、删除、序列化和反序列化
    """
    
    def __init__(self, base_dir: str = None):
        """
        初始化工具存储
        
        Args:
            base_dir: 基础存储目录（可选）。如果提供，将持久化保存到磁盘。
        """
        self.base_dir = base_dir
        self.tools: Dict[str, Dict[str, Any]] = {}
        
        if self.base_dir:
            self._ensure_base_dir()
            self._load_tools()
            
    def _ensure_base_dir(self):
        """确保基础目录存在"""
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            
    def _load_tools(self):
        """从磁盘加载所有工具"""
        if not self.base_dir or not os.path.exists(self.base_dir):
            return

        # 遍历基础目录下的 .json 文件
        self.tools = {}
        for entry in os.scandir(self.base_dir):
            if entry.is_file() and entry.name.endswith('.json'):
                try:
                    with open(entry.path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'name' in data:
                            self.tools[data['name']] = data
                except Exception as e:
                    print(f"Error loading tool from {entry.path}: {e}")

    def _save_tool(self, name: str, definition: Dict[str, Any]):
        """保存单个工具到磁盘"""
        if not self.base_dir:
            return
            
        file_path = os.path.join(self.base_dir, f"{name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(definition, f, ensure_ascii=False, indent=2)
    
    def add_tool(self, name: str, definition: Dict[str, Any]) -> bool:
        """
        添加工具定义
        
        Args:
            name: 工具名称
            definition: 工具定义字典
            
        Returns:
            bool: 是否添加成功（False表示已存在）
        """
        if name in self.tools:
            return False
        
        self.tools[name] = definition
        self._save_tool(name, definition)
        return True
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具定义"""
        return self.tools.get(name)
    
    def remove_tool(self, name: str) -> bool:
        """删除工具"""
        if name in self.tools:
            del self.tools[name]
            
            if self.base_dir:
                file_path = os.path.join(self.base_dir, f"{name}.json")
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Error removing tool file {file_path}: {e}")
            return True
        return False
    
    def list_tools(self) -> Dict[str, str]:
        """列出所有工具（仅返回名称和描述）"""
        return {
            name: def_dict.get('description', '')
            for name, def_dict in self.tools.items()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'tools': self.tools,
            'count': len(self.tools),
            'timestamp': time.time()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolStorage':
        """从字典反序列化 (内存模式)"""
        storage = cls()
        storage.tools = data.get('tools', {})
        return storage
    
    def export_to_json(self, filepath: str):
        """导出到JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def import_from_json(cls, filepath: str) -> 'ToolStorage':
        """从JSON文件导入"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


@dataclass
class ToolContext:
    """
    工具上下文数据结构
    
    存储在 LangGraph Runtime.context 中
    用于持久化工具定义、使用统计和用户偏好
    """
    # 工具定义字典 {tool_name: tool_definition}
    tool_definitions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # 工具使用统计 {tool_name: usage_count}
    tool_usage: Dict[str, int] = field(default_factory=dict)
    
    # 用户偏好设置
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'tool_definitions': self.tool_definitions,
            'tool_usage': self.tool_usage,
            'user_preferences': self.user_preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ToolContext':
        """从字典反序列化"""
        if not isinstance(data, dict):
            return cls()
        
        return cls(
            tool_definitions=data.get('tool_definitions', {}),
            tool_usage=data.get('tool_usage', {}),
            user_preferences=data.get('user_preferences', {})
        )
    
    def increment_usage(self, tool_name: str):
        """增加工具使用计数"""
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1
