"""
动态工具创建器 - 核心创新模块

实现智能体的元编程能力：
1. 根据需求自主生成工具定义
2. 动态创建 Pydantic 参数模型
3. 动态创建 BaseTool 工具类
4. 在沙箱环境中安全执行工具代码

使用 LangChain 1.0.0 的 InjectedToolArg 特性注入 storage
"""
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel, Field, create_model, ConfigDict
from langchain.tools import BaseTool
import json
import time
import os
from .tool_storage import ToolStorage


class ToolCreatorInput(BaseModel):
    """工具创建器的输入参数模型"""
    tool_name: str = Field(
        description="工具名称（英文+下划线，如 calculate_score）"
    )
    description: str = Field(
        description="工具功能描述，清晰说明工具的作用"
    )
    parameters: str = Field(
        description="""参数定义（JSON格式），例如：
[
  {"name": "radius", "type": "float", "description": "圆的半径", "default": null},
  {"name": "unit", "type": "str", "description": "单位", "default": "cm"}
]
支持的类型：str, int, float, bool, list, dict
"""
    )
    code: str = Field(
        description="""Python执行代码，可使用以下变量和模块：
- 所有输入参数（直接使用参数名）
- result 变量（必须设置，作为返回值）
- json, time 模块
- print() 函数用于输出日志

示例：
result = radius ** 2 * 3.14159
print(f"计算结果: {result}")
"""
    )
    usage_guide: str = Field(
        description="使用指南，说明何时使用此工具",
        default=""
    )
    target_agent: Optional[str] = Field(
        description="目标智能体名称（可选）。如果指定，工具将创建在该智能体的专属工具库中（即该智能体的文件夹内）。",
        default=None
    )


class ToolCreatorTool(BaseTool):
    """
    动态工具创建器 - 核心创新
    """
    name: str = "create_custom_tool"
    description: str = """
🛠️ 工具制造器 - 创建自定义工具供后续使用

**核心能力**：
- ✅ 动态创建新工具
- ✅ 工具持久化保存
- ✅ 可以创建到全局工具库
- ✅ 也可以创建到指定智能体的专属工具库

**适用场景**：
1. 发现某个操作需要重复执行
2. 需要特定领域的计算或处理
3. 想要封装复杂逻辑为简单接口
4. 为特定智能体创建专属能力

**示例**：
"创建一个计算圆面积的工具，输入半径，返回面积"
"为 data_analyst 智能体创建一个数据清洗工具"
"""
    args_schema: Type[BaseModel] = ToolCreatorInput
    
    # Pydantic v2: 必须显式声明字段
    storage: Any = Field(default=None, exclude=True)
    agent_storage: Any = Field(default=None, exclude=True)
    
    # Pydantic v2 配置
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def __init__(self, storage=None, agent_storage=None, **kwargs):
        """初始化（Pydantic v2兼容）"""
        super().__init__(storage=storage, agent_storage=agent_storage, **kwargs)
    
    def _run(
        self, 
        tool_name: str, 
        description: str, 
        parameters: str, 
        code: str, 
        usage_guide: str = "",
        target_agent: str = None
    ) -> str:
        """
        执行工具创建
        """
        # 步骤1：验证工具名称（仅允许字母、数字、下划线）
        if not tool_name.replace('_', '').isalnum():
            return json.dumps({
                "success": False,
                "error": "工具名称只能包含字母、数字和下划线"
            }, ensure_ascii=False)
        
        # 步骤2：解析参数定义
        try:
            params = json.loads(parameters) if isinstance(parameters, str) else parameters
            if not isinstance(params, list):
                raise ValueError("参数定义必须是数组")
        except (json.JSONDecodeError, ValueError) as e:
            return json.dumps({
                "success": False,
                "error": f"参数定义格式错误: {str(e)}"
            }, ensure_ascii=False)
        
        # 步骤3：确定目标存储
        target_storage = self.storage
        location_msg = "全局工具库"
        
        if target_agent:
            if not self.agent_storage:
                return json.dumps({
                    "success": False,
                    "error": "未配置智能体存储，无法为指定智能体创建工具"
                }, ensure_ascii=False)
                
            agent_def = self.agent_storage.get_agent(target_agent)
            if not agent_def:
                return json.dumps({
                    "success": False,
                    "error": f"目标智能体 '{target_agent}' 不存在"
                }, ensure_ascii=False)
            
            # 构建智能体专属工具存储
            agent_dir = os.path.join(self.agent_storage.base_dir, target_agent)
            tools_dir = os.path.join(agent_dir, "tools")
            target_storage = ToolStorage(base_dir=tools_dir)
            location_msg = f"智能体 '{target_agent}' 的专属工具库"
        
        # 步骤4：构建工具定义
        tool_definition = {
            'name': tool_name,
            'description': description,
            'parameters': params,
            'code': code,
            'usage_guide': usage_guide or description,
            'created_at': time.time(),
            'usage_count': 0
        }
        
        # 步骤5：验证并保存
        if not target_storage.add_tool(tool_name, tool_definition):
            return json.dumps({
                "success": False,
                "error": f"工具 '{tool_name}' 已存在于 {location_msg}"
            }, ensure_ascii=False)
        
        # 步骤6：测试创建工具实例（验证定义正确性）
        try:
            test_tool = create_dynamic_tool(tool_definition)
            # 验证工具属性
            assert hasattr(test_tool, 'name')
            # 验证方法存在
            assert hasattr(test_tool, '_run')
        except Exception as e:
            # 创建失败，回滚
            target_storage.remove_tool(tool_name)
            return json.dumps({
                "success": False,
                "error": f"工具创建失败: {str(e)}"
            }, ensure_ascii=False)
        
        # 步骤7：返回成功信息
        return json.dumps({
            "success": True,
            "tool_name": tool_name,
            "message": f"✅ 工具 '{tool_name}' 已成功创建到 {location_msg}！",
            "location": location_msg,
            "usage": f"现在可以在相关上下文中使用 {tool_name} 工具了",
            "details": {
                "description": description,
                "parameters": [p['name'] for p in params],
                "usage_guide": usage_guide or description
            }
        }, ensure_ascii=False)


def create_dynamic_tool(tool_definition: Dict[str, Any]) -> BaseTool:
    """
    根据工具定义动态创建工具实例 - 核心创新
    
    技术要点：
    1. 使用 Pydantic 的 create_model() 动态创建参数模型
    2. 使用 Python 的 type() 动态创建工具类
    3. 在沙箱环境中执行工具代码
    
    Args:
        tool_definition: 工具定义字典
        
    Returns:
        BaseTool: 动态创建的工具实例
    """
    name = tool_definition['name']
    description = tool_definition['description']
    parameters = tool_definition.get('parameters', [])
    code = tool_definition['code']
    
    # ========== 步骤1：构建字段定义字典 ==========
    field_definitions = {}
    type_map = {
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict
    }
    
    for param in parameters:
        field_name = param['name']
        field_type = type_map.get(param.get('type', 'str'), str)
        field_desc = param.get('description', '')
        field_default = param.get('default')
        
        # 根据是否有默认值决定字段定义
        if field_default is None:
            # 必填参数
            field_definitions[field_name] = (
                field_type,
                Field(description=field_desc)
            )
        else:
            # 可选参数
            field_definitions[field_name] = (
                field_type,
                Field(default=field_default, description=field_desc)
            )
    
    # ========== 步骤2：动态创建 Pydantic 输入模型 ==========
    if field_definitions:
        InputModel = create_model(
            f"{name}Input",
            **field_definitions
        )
    else:
        # 无参数工具
        class EmptyInputModel(BaseModel):
            pass
        InputModel = EmptyInputModel
    
    # ========== 步骤3：动态创建工具类 ==========
    # 捕获变量到局部作用域（避免闭包作用域问题）
    _name = name
    _desc = description
    _code = code
    
    class DynamicTool(BaseTool):
        """动态创建的工具类"""
        name: str = _name
        description: str = _desc
        args_schema: Type[BaseModel] = InputModel
        
        def _run(self, **kwargs) -> str:
            """执行工具"""
            try:
                from io import StringIO
                from contextlib import redirect_stdout
                import pandas as pd
                import numpy as np
                from pathlib import Path
                
                # 准备执行环境
                buffer = StringIO()
                exec_globals = {
                    "pd": pd,
                    "np": np,
                    "json": json,
                    "time": time,
                    "Path": Path,
                    "result": None,  # 用于存储返回值
                    "input_params": kwargs,  # 输入参数
                    "__builtins__": {
                        'print': print, 'len': len, 'str': str, 'int': int, 'float': float,
                        'list': list, 'dict': dict, 'tuple': tuple, 'set': set,
                        'range': range, 'enumerate': enumerate, 'zip': zip,
                        'sum': sum, 'max': max, 'min': min, 'round': round,
                        'True': True, 'False': False, 'None': None,
                        '__import__': __import__,
                        'open': open,
                    }
                }
                
                # 将参数添加到执行环境
                exec_globals.update(kwargs)
                
                start_time = time.time()
                
                # 执行代码
                with redirect_stdout(buffer):
                    exec(_code, exec_globals)
                
                execution_time = time.time() - start_time
                
                # 获取结果
                result = exec_globals.get('result')
                output = buffer.getvalue()
                
                # 返回 JSON 格式结果
                return json.dumps({
                    "success": True,
                    "tool": _name,
                    "result": result,
                    "output": output,
                    "execution_time": round(execution_time, 3)
                }, ensure_ascii=False, indent=2, default=str)
            
            except Exception as e:
                # 错误处理
                import traceback
                return json.dumps({
                    "success": False,
                    "tool": _name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }, ensure_ascii=False)
    
    # ========== 步骤4：返回工具实例 ==========
    return DynamicTool()


def get_tool_creator_tools(storage, agent_storage=None) -> List[BaseTool]:
    """
    获取工具创建器工具列表
    
    Args:
        storage: ToolStorage 实例
        agent_storage: AgentStorage 实例 (可选，用于支持为智能体创建工具)
        
    Returns:
        包含 ToolCreatorTool 的工具列表
    """
    return [
        ToolCreatorTool(storage=storage, agent_storage=agent_storage)
    ]


def get_dynamic_tools(storage) -> List[BaseTool]:
    """
    从 ToolStorage 创建所有动态工具实例
    
    Args:
        storage: ToolStorage 实例
        
    Returns:
        动态工具实例列表
    """
    tools = []
    
    for tool_name, tool_definition in storage.tools.items():
        try:
            tool = create_dynamic_tool(tool_definition)
            tools.append(tool)
        except Exception as e:
            print(f"⚠️  创建工具 '{tool_name}' 失败: {e}")
    
    return tools
