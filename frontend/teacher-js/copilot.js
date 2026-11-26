/* ==============================================================================
   CLARIQ — TEACHER AI COPILOT CHATBOT SCRIPT
   Communicates with Groq-powered /api/chatbot/teacher/message
   ============================================================================== */

const API_BASE_URL = window.location.hostname === "localhost" ? "http://localhost:8000" : "http://127.0.0.1:8000";

let currentConversationId = null;
let conversationHistory = []; // [{role: "user" | "assistant", content: "..."}]
let isLoading = false;

function getAuthToken() {
    return sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
}

function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = "login.html";
        return false;
    }
    return true;
}

// ==========================================
// INITIAL LOAD
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
    if (!checkAuth()) return;
    setupEventListeners();
    if (window.lucide) lucide.createIcons();
});

// ==========================================
// EVENT LISTENERS
// ==========================================
function setupEventListeners() {
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const btnSend = document.getElementById("btnSend");
    const btnNewChat = document.getElementById("btnNewChat");
    const btnClearChat = document.getElementById("btnClearChat");

    // Auto-resize textarea on input & toggle send button
    if (chatInput) {
        chatInput.addEventListener("input", () => {
            chatInput.style.height = "auto";
            chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
            if (btnSend) {
                btnSend.disabled = !chatInput.value.trim() || isLoading;
            }
        });

        // Enter key sends, Shift+Enter creates new line
        chatInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isLoading && chatInput.value.trim()) {
                    sendMessage();
                }
            }
        });
    }

    if (chatForm) {
        chatForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (!isLoading && chatInput.value.trim()) {
                sendMessage();
            }
        });
    }

    if (btnNewChat) {
        btnNewChat.addEventListener("click", startNewChat);
    }

    if (btnClearChat) {
        btnClearChat.addEventListener("click", clearCurrentChat);
    }
}

// Quick prompt pill click
window.sendQuickPrompt = function(promptText) {
    const chatInput = document.getElementById("chatInput");
    if (!chatInput || isLoading) return;
    chatInput.value = promptText;
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
    sendMessage();
};

// ==========================================
// SEND MESSAGE FLOW
// ==========================================
async function sendMessage() {
    const chatInput = document.getElementById("chatInput");
    const btnSend = document.getElementById("btnSend");
    const userText = chatInput.value.trim();
    if (!userText || isLoading) return;

    // Reset input field
    chatInput.value = "";
    chatInput.style.height = "auto";
    if (btnSend) btnSend.disabled = true;

    // Append User Message to UI
    appendMessage("user", userText);

    // Add to in-memory context
    conversationHistory.push({ role: "user", content: userText });

    // Show Typing Indicator
    showTypingIndicator();
    isLoading = true;

    try {
        const payload = {
            message: userText,
            conversation_id: currentConversationId,
            conversation_history: conversationHistory.slice(0, -1) // past turns
        };

        const res = await fetch(`${API_BASE_URL}/api/chatbot/teacher/message`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        removeTypingIndicator();

        if (!res.ok) {
            throw new Error(data.detail || "Unable to get a response from AI.");
        }

        const aiResponse = data.response || "";
        currentConversationId = data.conversation_id || currentConversationId;

        // Append Assistant Message to UI
        appendMessage("assistant", aiResponse);

        // Add to in-memory context
        conversationHistory.push({ role: "assistant", content: aiResponse });

    } catch (err) {
        removeTypingIndicator();
        console.error("Teacher Copilot error:", err);
        showErrorBanner(err.message, userText);
    } finally {
        isLoading = false;
        if (btnSend) {
            btnSend.disabled = !chatInput.value.trim();
        }
        chatInput.focus();
    }
}

// ==========================================
// UI RENDERING
// ==========================================
function appendMessage(role, text) {
    const container = document.getElementById("chatMessagesContainer");
    if (!container) return;

    // Hide welcome banner after first message
    const welcomeBanner = document.getElementById("chatWelcomeBanner");
    if (welcomeBanner && conversationHistory.length === 0) {
        welcomeBanner.style.display = "none";
    }

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const isUser = role === "user";

    const msgRow = document.createElement("div");
    msgRow.className = `message-row ${role}`;

    const avatarHtml = isUser
        ? `<div class="msg-avatar">${getTeacherInitial()}</div>`
        : `<div class="msg-avatar"><i data-lucide="sparkles" style="width: 18px; height: 18px;"></i></div>`;

    msgRow.innerHTML = `
        ${avatarHtml}
        <div class="msg-body">
            <div class="msg-bubble">${formatMessageContent(text)}</div>
            <div class="msg-time">${timeStr}</div>
        </div>
    `;

    container.appendChild(msgRow);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
}

function showTypingIndicator() {
    const container = document.getElementById("chatMessagesContainer");
    if (!container) return;

    const row = document.createElement("div");
    row.className = "typing-indicator-row";
    row.id = "typingIndicator";
    row.innerHTML = `
        <div class="msg-avatar" style="background: linear-gradient(135deg, #F97316 0%, #EA580C 100%); color: white;">
            <i data-lucide="sparkles" style="width: 18px; height: 18px;"></i>
        </div>
        <div class="typing-bubble">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
    `;

    container.appendChild(row);
    if (window.lucide) lucide.createIcons();
    scrollToBottom();
}

function removeTypingIndicator() {
    const el = document.getElementById("typingIndicator");
    if (el) el.remove();
}

function showErrorBanner(errorMessage, failedQuery) {
    const container = document.getElementById("chatMessagesContainer");
    if (!container) return;

    const banner = document.createElement("div");
    banner.className = "chat-error-banner";
    banner.innerHTML = `
        <div>
            <strong>Error:</strong> ${escapeHTML(errorMessage)}
        </div>
        <button type="button" class="btn-retry-msg" onclick="retryMessage('${escapeHTML(failedQuery).replace(/'/g, "\\'")}')">
            Retry
        </button>
    `;

    container.appendChild(banner);
    scrollToBottom();
}

window.retryMessage = function(query) {
    const banners = document.querySelectorAll(".chat-error-banner");
    banners.forEach(b => b.remove());

    const chatInput = document.getElementById("chatInput");
    if (chatInput) {
        chatInput.value = query;
        sendMessage();
    }
};

function scrollToBottom() {
    const container = document.getElementById("chatMessagesContainer");
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// ==========================================
// SESSION MANAGEMENT (NEW CHAT & CLEAR)
// ==========================================
function startNewChat() {
    currentConversationId = null;
    conversationHistory = [];

    const container = document.getElementById("chatMessagesContainer");
    if (!container) return;

    container.innerHTML = `
        <div class="chat-welcome-banner" id="chatWelcomeBanner">
            <div class="welcome-icon-box">
                <i data-lucide="sparkles" style="width: 22px; height: 22px;"></i>
            </div>
            <div class="welcome-text">
                <h3>Hello Professor! I'm your ClariQ AI Copilot.</h3>
                <p>
                    I'm here to assist you with preparing lecture explanations, creating assignment questions, generating MCQs with answers, formulating lesson plans, and developing revision notes.<br>
                    <strong>How can I assist your teaching today?</strong>
                </p>
                <div class="welcome-capabilities">
                    <span class="capability-pill" onclick="sendQuickPrompt('Generate 10 MCQs on DBMS Normalization (1NF, 2NF, 3NF, BCNF) with answer key and brief explanations')">
                        📝 10 MCQs on DBMS Normalization
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Prepare a structured 45-minute lecture plan for introducing Binary Search Trees to undergraduate students')">
                        📋 Lecture Plan: Binary Search Trees
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Create 5 conceptual assignment questions on Graph Traversal (BFS and DFS) with practical applications')">
                        📚 Graph Algorithms Assignment
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Explain Red-Black Tree balancing rules in simple classroom-friendly language with example cases')">
                        💡 Explain Red-Black Trees Simply
                    </span>
                </div>
            </div>
        </div>
    `;

    const chatInput = document.getElementById("chatInput");
    if (chatInput) {
        chatInput.value = "";
        chatInput.style.height = "auto";
        chatInput.focus();
    }

    if (window.lucide) lucide.createIcons();
}

async function clearCurrentChat() {
    if (conversationHistory.length === 0) return;
    if (!confirm("Are you sure you want to clear this conversation?")) return;

    if (currentConversationId) {
        try {
            await fetch(`${API_BASE_URL}/api/chatbot/conversations/${currentConversationId}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${getAuthToken()}` }
            });
        } catch (e) {
            console.error("Error clearing conversation on server:", e);
        }
    }

    startNewChat();
}

// ==========================================
// UTILITIES
// ==========================================
function getTeacherInitial() {
    try {
        const rawUser = sessionStorage.getItem("clariqUser") || localStorage.getItem("clariqUser");
        if (rawUser) {
            const user = JSON.parse(rawUser);
            const name = user.full_name || user.name || "T";
            return name.charAt(0).toUpperCase();
        }
    } catch (_) {}
    return "T";
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}

function formatMessageContent(raw) {
    if (!raw) return "";

    let text = escapeHTML(raw);

    // Format code blocks
    text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Format inline code
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Format bold
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Format numbered lists (e.g. 1. 2.)
    text = text.replace(/^(\d+)\.\s+(.+)$/gm, "<div style='margin-left: 12px; margin-top: 4px;'><strong>$1.</strong> $2</div>");

    // Format bullet points
    text = text.replace(/^\s*[-*]\s+(.+)$/gm, "<div style='margin-left: 12px; margin-top: 2px;'>• $1</div>");

    return text;
}
