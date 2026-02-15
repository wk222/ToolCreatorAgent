/**
 * ToolCreatorAgent — Frontend Client v3
 * SSE 流式输出 + 智能体/工具管理 + 启用/禁用 + 工具分配
 */

const API = '';

// ========== State ==========
let currentThreadId = null;
let conversations = [];
let isSending = false;
let stepsExpanded = true;

// ========== DOM ==========
const convList = document.getElementById('convList');
const chatMessages = document.getElementById('chatMessages');
const chatTitle = document.getElementById('chatTitle');
const chatThreadId = document.getElementById('chatThreadId');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const agentsList = document.getElementById('agentsList');
const toolsList = document.getElementById('toolsList');
const stepsBar = document.getElementById('stepsBar');
const stepsList = document.getElementById('stepsList');

// ========== Init ==========
document.addEventListener('DOMContentLoaded', () => {
    loadConversations();
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
    });
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
});

// ========== Conversations ==========
async function loadConversations() {
    try {
        const res = await fetch(`${API}/api/conversations`);
        const data = await res.json();
        conversations = data.conversations || [];
        renderConversations();
    } catch (e) { console.error('Failed to load conversations:', e); }
}

function renderConversations() {
    if (conversations.length === 0) {
        convList.innerHTML = `<div style="padding:24px 12px;text-align:center;color:var(--text-muted);font-size:12px;">暂无会话<br>点击上方按钮创建</div>`;
        return;
    }
    convList.innerHTML = conversations.map(c => {
        const isActive = c.thread_id === currentThreadId;
        const timeStr = formatTime(c.last_message_at);
        return `
      <div class="conv-item ${isActive ? 'active' : ''}" onclick="switchConversation('${c.thread_id}')" data-thread-id="${c.thread_id}">
        <div class="conv-icon">💬</div>
        <div class="conv-info">
          <div class="conv-title">${escapeHtml(c.title)}</div>
          <div class="conv-meta">${c.message_count || 0} 条消息 · ${timeStr}</div>
        </div>
        <button class="conv-delete" onclick="event.stopPropagation();deleteConversation('${c.thread_id}')" title="删除">✕</button>
      </div>`;
    }).join('');
}

async function createConversation() {
    try {
        const res = await fetch(`${API}/api/conversations`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({})
        });
        const data = await res.json();
        currentThreadId = data.thread_id;
        await loadConversations();
        switchConversation(data.thread_id);
    } catch (e) { console.error('Failed to create:', e); }
}

async function deleteConversation(threadId) {
    if (!confirm('确定删除这个会话？')) return;
    try {
        await fetch(`${API}/api/conversations/${threadId}`, { method: 'DELETE' });
        if (currentThreadId === threadId) {
            currentThreadId = null;
            chatTitle.textContent = '选择或创建一个会话';
            chatThreadId.textContent = '';
            chatMessages.innerHTML = emptyStateHTML();
            messageInput.disabled = true; sendBtn.disabled = true;
            resetPanel();
        }
        await loadConversations();
    } catch (e) { console.error('Failed to delete:', e); }
}

async function switchConversation(threadId) {
    currentThreadId = threadId;
    const conv = conversations.find(c => c.thread_id === threadId);
    chatTitle.textContent = conv ? conv.title : threadId;
    chatThreadId.textContent = threadId;
    messageInput.disabled = false; sendBtn.disabled = false; messageInput.focus();
    document.querySelectorAll('.conv-item').forEach(el => {
        el.classList.toggle('active', el.dataset.threadId === threadId);
    });
    await loadHistory(threadId);
    await loadStatus(threadId);
}

async function loadHistory(threadId) {
    try {
        const res = await fetch(`${API}/api/conversations/${threadId}/history`);
        const data = await res.json();
        const messages = data.messages || [];
        if (messages.length === 0) { chatMessages.innerHTML = emptyStateHTML(); return; }
        chatMessages.innerHTML = messages.map(m => renderMessage(m)).join('');
        scrollToBottom();
    } catch (e) {
        console.error('Failed to load history:', e);
        chatMessages.innerHTML = emptyStateHTML();
    }
}

// ========== SSE Streaming Chat ==========
async function sendMessage() {
    if (isSending) return;
    const text = messageInput.value.trim();
    if (!text || !currentThreadId) return;

    isSending = true; sendBtn.disabled = true;
    messageInput.value = ''; messageInput.style.height = 'auto';

    const es = chatMessages.querySelector('.empty-state');
    if (es) es.remove();

    appendMessage({ role: 'user', content: text, timestamp: Date.now() / 1000 });

    stepsBar.style.display = 'block';
    stepsBar.classList.remove('collapsed');
    stepsList.innerHTML = '';
    addStep('🚀', '发送请求...');

    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'message assistant';
    assistantDiv.innerHTML = `
    <div class="avatar">🤖</div>
    <div>
      <div class="bubble">
        <div class="thinking"><span></span><span></span><span></span></div>
      </div>
      <div class="timestamp"></div>
    </div>`;
    chatMessages.appendChild(assistantDiv);
    scrollToBottom();

    try {
        const res = await fetch(`${API}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: currentThreadId })
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;
                try {
                    const event = JSON.parse(jsonStr);
                    if (event.type === 'step') {
                        addStep(event.icon || '📋', event.content);
                    } else if (event.type === 'done') {
                        const bubble = assistantDiv.querySelector('.bubble');
                        bubble.innerHTML = formatContent(event.content);
                        assistantDiv.querySelector('.timestamp').textContent = formatTime(Date.now() / 1000);
                        scrollToBottom();
                        updatePanel(event.agents || [], event.tools || []);
                        const conv = conversations.find(c => c.thread_id === currentThreadId);
                        if (conv && conv.message_count === 0) {
                            conv.title = text.substring(0, 30) + (text.length > 30 ? '...' : '');
                            chatTitle.textContent = conv.title;
                        }
                    } else if (event.type === 'error') {
                        const bubble = assistantDiv.querySelector('.bubble');
                        bubble.innerHTML = `<span style="color:var(--error)">${escapeHtml(event.content)}</span>`;
                        addStep('❌', event.content);
                    }
                } catch (_) { }
            }
        }

        const header = stepsBar.querySelector('.steps-bar-header');
        header.innerHTML = `<span style="color:var(--success)">✅</span><span>完成</span>`;
        setTimeout(() => { stepsBar.style.display = 'none'; }, 3000);
        await loadConversations();

    } catch (e) {
        const bubble = assistantDiv.querySelector('.bubble');
        bubble.innerHTML = `<span style="color:var(--error)">❌ 网络错误: ${escapeHtml(e.message)}</span>`;
        addStep('❌', `网络错误: ${e.message}`);
    } finally {
        isSending = false; sendBtn.disabled = false; messageInput.focus();
    }
}

// ========== Steps Bar ==========
function addStep(icon, text) {
    const el = document.createElement('div');
    el.className = 'step-item';
    el.innerHTML = `<span class="step-icon">${icon}</span><span class="step-text">${escapeHtml(text)}</span>`;
    stepsList.appendChild(el);
    stepsList.scrollTop = stepsList.scrollHeight;
}

function toggleStepsExpand() {
    stepsExpanded = !stepsExpanded;
    stepsBar.classList.toggle('collapsed', !stepsExpanded);
}

// ========== Panel Tabs ==========
function switchPanelTab(tab) {
    document.querySelectorAll('.panel-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.querySelectorAll('.panel-content').forEach(c => c.style.display = 'none');
    document.getElementById(`panel-${tab}`).style.display = '';
    if (tab === 'agents') refreshAgents();
    if (tab === 'tools') refreshTools();
}

function togglePanel(tab) { switchPanelTab(tab); }

// ========== Agent Management ==========
async function refreshAgents() {
    const container = document.getElementById('agentsManageList');
    try {
        const [agentsRes, toolsRes] = await Promise.all([
            fetch(`${API}/api/agents`),
            fetch(`${API}/api/tools`)
        ]);
        const agentsData = await agentsRes.json();
        const toolsData = await toolsRes.json();
        const allAgents = agentsData.agents || [];
        const allTools = (toolsData.tools || []).map(t => t.name);

        if (allAgents.length === 0) {
            container.innerHTML = '<span class="panel-empty">暂无子智能体。<br>可以在对话中说"创建一个XXX智能体"来创建。</span>';
            return;
        }

        container.innerHTML = allAgents.map(a => {
            const enabled = a.enabled !== false;
            const assignedTools = a.tools || [];
            const unassignedTools = allTools.filter(t => !assignedTools.includes(t));

            return `
        <div class="manage-card ${!enabled ? 'disabled-card' : ''}">
          <div class="manage-card-title">
            <span>🤖 ${escapeHtml(a.name)}</span>
            <div style="display:flex;gap:4px;align-items:center;">
              <label class="toggle-switch" title="${enabled ? '点击禁用' : '点击启用'}">
                <input type="checkbox" ${enabled ? 'checked' : ''} 
                       onchange="toggleAgent('${escapeHtml(a.name)}', this.checked)">
                <span class="toggle-slider"></span>
              </label>
              <button class="delete-btn" onclick="deleteAgent('${escapeHtml(a.name)}')" title="删除">✕</button>
            </div>
          </div>
          <div class="manage-card-desc">${escapeHtml(a.description || a.role || '')}</div>
          <div class="manage-card-meta">
            <span>模型: ${escapeHtml(a.model || 'default')}</span>
            <span>使用: ${a.usage_count || 0} 次</span>
            <span style="color:${enabled ? 'var(--success)' : 'var(--error)'}">${enabled ? '已启用' : '已禁用'}</span>
          </div>

          <!-- 已分配工具 -->
          <div class="agent-tools-section">
            <div class="agent-tools-title">🔧 已分配工具</div>
            <div class="agent-tools-list">
              ${assignedTools.length > 0
                    ? assignedTools.map(t => `
                    <span class="tool-chip">
                      ${escapeHtml(t)}
                      <button class="chip-remove" onclick="removeToolFromAgent('${escapeHtml(a.name)}','${escapeHtml(t)}')" title="移除">✕</button>
                    </span>`).join('')
                    : '<span class="panel-empty" style="font-size:11px;">无</span>'
                }
            </div>
            <!-- 追加工具选择器 -->
            ${unassignedTools.length > 0 ? `
              <div class="tool-assign-row">
                <select class="tool-assign-select" id="sel-${a.name}">
                  <option value="">选择工具...</option>
                  ${unassignedTools.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('')}
                </select>
                <button class="mini-btn" onclick="assignToolToAgent('${escapeHtml(a.name)}')">追加</button>
              </div>
            ` : ''}
          </div>
        </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = `<span class="panel-empty">加载失败: ${e.message}</span>`;
    }
}

async function toggleAgent(name, enabled) {
    try {
        await fetch(`${API}/api/agents/${encodeURIComponent(name)}/toggle`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        refreshAgents();
    } catch (e) { alert('操作失败: ' + e.message); }
}

async function deleteAgent(name) {
    if (!confirm(`确定删除智能体 "${name}"？此操作不可恢复。`)) return;
    try {
        await fetch(`${API}/api/agents/${encodeURIComponent(name)}`, { method: 'DELETE' });
        refreshAgents();
    } catch (e) { alert('删除失败: ' + e.message); }
}

async function assignToolToAgent(agentName) {
    const select = document.getElementById(`sel-${agentName}`);
    const toolName = select ? select.value : '';
    if (!toolName) { alert('请先选择一个工具'); return; }
    try {
        await fetch(`${API}/api/agents/${encodeURIComponent(agentName)}/tools`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tool_name: toolName })
        });
        refreshAgents();
    } catch (e) { alert('分配失败: ' + e.message); }
}

async function removeToolFromAgent(agentName, toolName) {
    try {
        await fetch(`${API}/api/agents/${encodeURIComponent(agentName)}/tools/${encodeURIComponent(toolName)}`, { method: 'DELETE' });
        refreshAgents();
    } catch (e) { alert('移除失败: ' + e.message); }
}

// ========== Tool Management ==========
async function refreshTools() {
    const container = document.getElementById('toolsManageList');
    try {
        const res = await fetch(`${API}/api/tools`);
        const data = await res.json();
        const tools = data.tools || [];

        if (tools.length === 0) {
            container.innerHTML = '<span class="panel-empty">暂无自定义工具。<br>可以在对话中说"创建一个XXX工具"来创建。</span>';
            return;
        }

        container.innerHTML = tools.map(t => `
      <div class="manage-card">
        <div class="manage-card-title">
          <span>🔧 ${escapeHtml(t.name)}</span>
          <button class="delete-btn" onclick="deleteTool('${escapeHtml(t.name)}')" title="删除">✕</button>
        </div>
        <div class="manage-card-desc">${escapeHtml(t.description || '')}</div>
        <div class="manage-card-meta"><span>使用: ${t.usage_count || 0} 次</span></div>
      </div>
    `).join('');
    } catch (e) {
        container.innerHTML = `<span class="panel-empty">加载失败: ${e.message}</span>`;
    }
}

async function deleteTool(name) {
    if (!confirm(`确定删除工具 "${name}"？此操作不可恢复。`)) return;
    try {
        await fetch(`${API}/api/tools/${encodeURIComponent(name)}`, { method: 'DELETE' });
        refreshTools();
    } catch (e) { alert('删除失败: ' + e.message); }
}

// ========== Status Panel ==========
async function loadStatus(threadId) {
    try {
        const res = await fetch(`${API}/api/status/${threadId}`);
        const data = await res.json();
        updatePanel(Object.keys(data.agents || {}), Object.keys(data.tools || {}));
    } catch (e) { resetPanel(); }
}

function updatePanel(agents, tools) {
    if (agents.length > 0) {
        agentsList.innerHTML = agents.map(a => `<span class="panel-tag"><span class="dot"></span>${escapeHtml(a)}</span>`).join('');
    } else { agentsList.innerHTML = '<span class="panel-empty">暂无智能体</span>'; }
    if (tools.length > 0) {
        toolsList.innerHTML = tools.map(t => `<span class="panel-tag"><span class="dot"></span>${escapeHtml(t)}</span>`).join('');
    } else { toolsList.innerHTML = '<span class="panel-empty">暂无工具</span>'; }
}

function resetPanel() {
    agentsList.innerHTML = '<span class="panel-empty">暂无智能体</span>';
    toolsList.innerHTML = '<span class="panel-empty">暂无工具</span>';
}

// ========== Rendering ==========
function renderMessage(msg) {
    const isUser = msg.role === 'user';
    const avatar = isUser ? '👤' : '🤖';
    const timeStr = formatTime(msg.timestamp);
    const content = formatContent(msg.content);
    return `
    <div class="message ${msg.role}">
      <div class="avatar">${avatar}</div>
      <div>
        <div class="bubble">${content}</div>
        <div class="timestamp">${timeStr}</div>
      </div>
    </div>`;
}

function appendMessage(msg) {
    chatMessages.insertAdjacentHTML('beforeend', renderMessage(msg));
    scrollToBottom();
}

function formatContent(text) {
    if (!text) return '';
    let s = escapeHtml(text);
    s = s.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
    s = s.replace(/\n/g, '<br>');
    return s;
}

function emptyStateHTML() {
    return `
    <div class="empty-state">
      <div class="logo">🛠️</div>
      <h2>欢迎使用 ToolCreatorAgent</h2>
      <p>我是一个能够<strong>自主创建工具和智能体</strong>的超级助手。<br>
      试试对我说："创建一个计算圆面积的工具" 或 "创建一个数据分析师智能体"。</p>
    </div>`;
}

// ========== Utils ==========
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatTime(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    if (isToday) return `${hh}:${mm}`;
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${hh}:${mm}`;
}

function scrollToBottom() {
    requestAnimationFrame(() => { chatMessages.scrollTop = chatMessages.scrollHeight; });
}
