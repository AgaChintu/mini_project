/* ==============================================================================
   CLARIQ — STUDENT AI CHATBOT SCRIPT
   Communicates with Groq-powered /api/chatbot/student/message
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

    initUserProfile();
    setupEventListeners();
    if (window.lucide) lucide.createIcons();
});

// Profile avatar and name in topbar
async function initUserProfile() {
    try {
        const rawUser = localStorage.getItem("clariqUser") || sessionStorage.getItem("clariqUser");
        if (rawUser) {
            const user = JSON.parse(rawUser);
            const displayName = user.name || user.full_name || "Student";
            const nameEl = document.getElementById("studentName");
            const avatarEl = document.getElementById("studentAvatar");
            if (nameEl) nameEl.textContent = displayName;
            if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();
        }
    } catch (e) {
        console.error("Error reading cached profile", e);
    }

    // Refresh dynamically from student dashboard
    const token = getAuthToken();
    if (!token) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/student/dashboard`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            const profile = data.profile || (data.data && data.data.profile);
            if (profile && profile.full_name) {
                const nameEl = document.getElementById("studentName");
                const avatarEl = document.getElementById("studentAvatar");
                if (nameEl) nameEl.textContent = profile.full_name;
                if (avatarEl) avatarEl.textContent = profile.full_name.charAt(0).toUpperCase();
            }
        }
    } catch (e) {
        // Ignore background refresh failure
    }
}

// ==========================================
// EVENT LISTENERS
// ==========================================
function setupEventListeners() {
    const chatForm = document.getElementById("chatForm");
    const chatInput = document.getElementById("chatInput");
    const btnSend = document.getElementById("btnSend");
    const btnNewChat = document.getElementById("btnNewChat");
    const btnClearChat = document.getElementById("btnClearChat");

    // Auto-resize input & toggle send button
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
            conversation_history: conversationHistory.slice(0, -1) // past turns excluding current
        };

        const res = await fetch(`${API_BASE_URL}/api/chatbot/student/message`, {
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
        console.error("Chat error:", err);
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
        ? `<div class="msg-avatar">${getUserInitial()}</div>`
        : `<div class="msg-avatar"><i data-lucide="bot" style="width: 18px; height: 18px;"></i></div>`;

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
        <div class="msg-avatar" style="background: linear-gradient(135deg, #4965E8 0%, #6366F1 100%); color: white;">
            <i data-lucide="bot" style="width: 18px; height: 18px;"></i>
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
    // Remove error banner
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
                <h3>Hello! I'm your ClariQ AI Assistant.</h3>
                <p>
                    I'm here to help you understand academic concepts, solve programming questions, explain difficult topics and assist with your studies.<br>
                    <strong>What would you like to learn today?</strong>
                </p>
                <div class="welcome-capabilities">
                    <span class="capability-pill" onclick="sendQuickPrompt('What is a neural network and how does it work?')">
                        💡 What is a neural network?
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Explain Binary Search Tree with time complexity')">
                        🌲 Explain Binary Search Tree
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Give me a Python example of recursion vs iteration')">
                        🐍 Python recursion example
                    </span>
                    <span class="capability-pill" onclick="sendQuickPrompt('Explain normalization forms 1NF, 2NF, 3NF in DBMS')">
                        📊 DBMS Normalization
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
function getUserInitial() {
    try {
        const rawUser = localStorage.getItem("clariqUser") || sessionStorage.getItem("clariqUser");
        if (rawUser) {
            const user = JSON.parse(rawUser);
            const name = user.name || user.full_name || "S";
            return name.charAt(0).toUpperCase();
        }
    } catch (_) {}
    return "S";
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}

function formatMessageContent(raw) {
    if (!raw) return "";

    // Escape HTML first to prevent injection
    let text = escapeHTML(raw);

    // Format code blocks ```code```
    text = text.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Format inline code `code`
    text = text.replace(/`([^`]+)`/g, "<code>$1</code>");

    // Format bold **text**
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

    // Format bullet points
    text = text.replace(/^\s*[-*]\s+(.+)$/gm, "• $1");

    return text;
}
