"""
7x24 后台服务模式 - 包装器
提供 API 接口并支持长时间自主运行
支持多会话管理、SSE流式输出、智能体管理
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
import os
import json
import time
import uuid
from agent import create_tool_creator_agent

app = FastAPI(title="ToolCreatorAgent 7x24 Service")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 预加载 Agent 配置
try:
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
            llm_config = config.get('llm_config', {})
    else:
        llm_config = {}
except Exception:
    llm_config = {}

# ========== 会话管理 ==========
CONVERSATIONS_FILE = "conversations.json"

def load_conversations() -> Dict:
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_conversations(convs: Dict):
    with open(CONVERSATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(convs, f, ensure_ascii=False, indent=2)

conversations = load_conversations()

# 消息历史
HISTORY_DIR = "chat_history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def load_history(thread_id: str) -> List[Dict]:
    filepath = os.path.join(HISTORY_DIR, f"{thread_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_history(thread_id: str, history: List[Dict]):
    filepath = os.path.join(HISTORY_DIR, f"{thread_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# 全局 Agent 实例
agents = {}

def get_or_create_agent(thread_id: str):
    """懒实例化 Agent"""
    if thread_id not in agents:
        agents[thread_id] = create_tool_creator_agent(
            model=llm_config.get('model', 'gpt-4'),
            thread_id=thread_id,
            api_key=llm_config.get('api_key'),
            base_url=llm_config.get('api_base')
        )
    return agents[thread_id]

# ========== 请求模型 ==========
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default-7x24"

class CreateConversationRequest(BaseModel):
    title: Optional[str] = None

class AgentToggleRequest(BaseModel):
    enabled: bool

# ========== API 路由 ==========

@app.get("/api/health")
async def health():
    return {"status": "running", "timestamp": time.time()}

# ---------- 会话管理 ----------

@app.get("/api/conversations")
async def list_conversations():
    conv_list = []
    for tid, meta in conversations.items():
        conv_list.append({"thread_id": tid, **meta})
    conv_list.sort(key=lambda x: x.get("last_message_at", 0), reverse=True)
    return {"conversations": conv_list}

@app.post("/api/conversations")
async def create_conversation(req: Optional[CreateConversationRequest] = None):
    thread_id = f"session-{uuid.uuid4().hex[:8]}"
    title = (req.title if req and req.title else None) or f"新会话 {len(conversations) + 1}"
    now = time.time()
    conversations[thread_id] = {
        "title": title,
        "created_at": now,
        "last_message_at": now,
        "message_count": 0
    }
    save_conversations(conversations)
    return {"thread_id": thread_id, "title": title}

@app.delete("/api/conversations/{thread_id}")
async def delete_conversation(thread_id: str):
    if thread_id in conversations:
        del conversations[thread_id]
        save_conversations(conversations)
    filepath = os.path.join(HISTORY_DIR, f"{thread_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
    if thread_id in agents:
        del agents[thread_id]
    return {"success": True}

@app.get("/api/conversations/{thread_id}/history")
async def get_history(thread_id: str):
    history = load_history(thread_id)
    return {"thread_id": thread_id, "messages": history}

# ---------- SSE 流式聊天 ----------

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式聊天 — 返回中间步骤和最终结果"""
    thread_id = request.thread_id

    # 确保会话存在
    if thread_id not in conversations:
        conversations[thread_id] = {
            "title": request.message[:30] + ("..." if len(request.message) > 30 else ""),
            "created_at": time.time(),
            "last_message_at": time.time(),
            "message_count": 0
        }

    agent = get_or_create_agent(thread_id)
    history = load_history(thread_id)

    # 保存用户消息
    history.append({
        "role": "user",
        "content": request.message,
        "timestamp": time.time()
    })

    def event_generator():
        final_content = None
        final_agents = []
        final_tools = []

        for event in agent.chat_stream(request.message):
            evt_type = event.get("type")

            if evt_type == "step":
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif evt_type == "heartbeat":
                yield f"data: {json.dumps({'type': 'heartbeat'}, ensure_ascii=False)}\n\n"
            elif evt_type == "done":
                final_content = event.get("content", "")
                final_agents = event.get("agents", [])
                final_tools = event.get("tools", [])
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            elif evt_type == "error":
                final_content = event.get("content", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 保存结果
        if final_content:
            history.append({
                "role": "assistant",
                "content": final_content,
                "timestamp": time.time()
            })
            save_history(thread_id, history)
            conversations[thread_id]["last_message_at"] = time.time()
            conversations[thread_id]["message_count"] = len(history)
            save_conversations(conversations)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# 非流式聊天保留兼容
@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        thread_id = request.thread_id
        if thread_id not in conversations:
            conversations[thread_id] = {
                "title": request.message[:30] + ("..." if len(request.message) > 30 else ""),
                "created_at": time.time(),
                "last_message_at": time.time(),
                "message_count": 0
            }

        agent = get_or_create_agent(thread_id)
        history = load_history(thread_id)
        history.append({"role": "user", "content": request.message, "timestamp": time.time()})

        response = agent.chat(request.message)
        history.append({"role": "assistant", "content": response, "timestamp": time.time()})
        save_history(thread_id, history)
        conversations[thread_id]["last_message_at"] = time.time()
        conversations[thread_id]["message_count"] = len(history)
        save_conversations(conversations)

        return {
            "thread_id": thread_id,
            "response": response,
            "agents_active": list(agent.list_agents().keys()),
            "tools_active": list(agent.list_tools().keys())
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ---------- 智能体管理 ----------

@app.get("/api/agents")
async def list_all_agents():
    """列出所有已创建的子智能体（跨会话全局）"""
    agent = get_or_create_agent("__system__")
    details = agent.get_agent_details()
    return {"agents": details}

@app.get("/api/agents/{agent_name}")
async def get_agent_detail(agent_name: str):
    """获取单个智能体详情"""
    agent = get_or_create_agent("__system__")
    agent_def = agent.agent_storage.get_agent(agent_name)
    if not agent_def:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent_def.to_dict()

@app.patch("/api/agents/{agent_name}/toggle")
async def toggle_agent(agent_name: str, req: AgentToggleRequest):
    """启用或禁用智能体"""
    agent = get_or_create_agent("__system__")
    ok = agent.agent_storage.toggle_agent(agent_name, req.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True, "agent_name": agent_name, "enabled": req.enabled}

@app.delete("/api/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """删除一个子智能体"""
    agent = get_or_create_agent("__system__")
    ok = agent.agent_storage.remove_agent(agent_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True, "deleted": agent_name}

# ---------- 子智能体工具管理 ----------

@app.get("/api/agents/{agent_name}/tools")
async def list_agent_tools(agent_name: str):
    """列出子智能体的已分配工具"""
    agent = get_or_create_agent("__system__")
    agent_def = agent.agent_storage.get_agent(agent_name)
    if not agent_def:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "agent_name": agent_name,
        "tools": agent_def.tools,
        "enabled": agent_def.enabled
    }

class AssignToolRequest(BaseModel):
    tool_name: str

@app.post("/api/agents/{agent_name}/tools")
async def assign_tool_to_agent(agent_name: str, req: AssignToolRequest):
    """给子智能体分配一个全局工具"""
    agent = get_or_create_agent("__system__")
    # 验证工具存在
    global_tools = agent.storage.list_tools()
    if req.tool_name not in global_tools:
        raise HTTPException(status_code=404, detail=f"Global tool '{req.tool_name}' not found")
    ok = agent.agent_storage.add_tool_to_agent(agent_name, req.tool_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"success": True, "agent_name": agent_name, "tool_assigned": req.tool_name}

@app.delete("/api/agents/{agent_name}/tools/{tool_name}")
async def remove_tool_from_agent(agent_name: str, tool_name: str):
    """从子智能体移除一个工具"""
    agent = get_or_create_agent("__system__")
    ok = agent.agent_storage.remove_tool_from_agent(agent_name, tool_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Agent or tool not found")
    return {"success": True, "agent_name": agent_name, "tool_removed": tool_name}

# ---------- 全局工具管理 ----------

@app.get("/api/tools")
async def list_all_tools():
    """列出所有已创建的工具"""
    agent = get_or_create_agent("__system__")
    tools = agent.storage.list_tools()
    usage = agent.get_tool_usage_stats()
    tool_list = []
    for name, desc in tools.items():
        tool_list.append({
            "name": name,
            "description": desc,
            "usage_count": usage.get(name, 0)
        })
    return {"tools": tool_list}


@app.delete("/api/tools/{tool_name}")
async def delete_tool(tool_name: str):
    """删除一个工具"""
    agent = get_or_create_agent("__system__")
    ok = agent.storage.remove_tool(tool_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Tool not found")
    return {"success": True, "deleted": tool_name}

@app.get("/api/status/{thread_id}")
async def get_status(thread_id: str):
    if thread_id not in agents:
        return {"thread_id": thread_id, "agents": {}, "tools": {}, "usage_stats": {}}
    agent = agents[thread_id]
    return {
        "thread_id": thread_id,
        "agents": agent.list_agents(),
        "tools": agent.list_tools(),
        "usage_stats": agent.get_tool_usage_stats()
    }

# ========== 静态文件 ==========
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

@app.get("/")
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "static/index.html not found"}

app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    print("🚀 ToolCreatorAgent 7x24 服务启动中...")
    print(f"   前端地址: http://localhost:8000")
    print(f"   API 文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
