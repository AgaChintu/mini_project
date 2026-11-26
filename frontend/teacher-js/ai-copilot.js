/* ==============================================================================
   CLARIQ — AI ACADEMIC COPILOT SCRIPT
   Integrates directly with FastAPI /api/copilot endpoints (Groq LLM + RAG)
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

let currentClusters = [];
let activeClusterId = null;
let activeClusterData = null;

function getAuthToken() {
    return sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
}

function authHeaders() {
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${getAuthToken()}`
    };
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
document.addEventListener("DOMContentLoaded", async () => {
    if (!checkAuth()) return;
    setupEventListeners();
    await loadSubjectsFilter();
    await loadDashboardOverview();
    await loadClusters();
    await loadTopicHeatmap();
});

function setupEventListeners() {
    const searchInput = document.getElementById("clusterSearchInput");
    const subjFilter = document.getElementById("clusterSubjectFilter");
    const prioFilter = document.getElementById("clusterPriorityFilter");
    const statFilter = document.getElementById("clusterStatusFilter");

    if (searchInput) searchInput.addEventListener("input", debounce(loadClusters, 300));
    if (subjFilter) subjFilter.addEventListener("change", loadClusters);
    if (prioFilter) prioFilter.addEventListener("change", loadClusters);
    if (statFilter) statFilter.addEventListener("change", loadClusters);
}

// ==========================================
// LOAD SUBJECTS FILTER
// ==========================================
async function loadSubjectsFilter() {
    const select = document.getElementById("clusterSubjectFilter");
    try {
        const res = await fetch(`${API_BASE_URL}/api/library/teacher/subjects`, {
            headers: authHeaders()
        });
        if (!res.ok) return;
        const data = await res.json();
        const subjects = data.data || [];

        let html = `<option value="">All Subjects</option>`;
        subjects.forEach(s => {
            html += `<option value="${s.id}">${escapeHTML(s.code || "")} — ${escapeHTML(s.name)}</option>`;
        });
        if (select) select.innerHTML = html;
    } catch (e) {
        console.error("Error loading subjects filter", e);
    }
}

// ==========================================
// LOAD DASHBOARD OVERVIEW STATS
// ==========================================
async function loadDashboardOverview() {
    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/dashboard`, {
            headers: authHeaders()
        });
        if (!res.ok) return;
        const data = await res.json();
        const d = data.data || {};

        document.getElementById("statTotalDoubts").textContent = d.total_doubts ?? 0;
        document.getElementById("statTotalClusters").textContent = d.total_clusters ?? 0;
        document.getElementById("statHighPriority").textContent = d.high_priority_clusters ?? 0;
        document.getElementById("statAiDrafts").textContent = d.ai_drafts_pending_review ?? 0;
        document.getElementById("statResolvedDoubts").textContent = d.resolved_doubts ?? 0;
    } catch (e) {
        console.error("Error loading copilot stats", e);
    }
}

// ==========================================
// LOAD MASTER DOUBT CARDS
// ==========================================
async function loadClusters() {
    const grid = document.getElementById("clustersGrid");
    const emptyBox = document.getElementById("clustersEmpty");
    const countSpan = document.getElementById("filteredClusterCount");

    const search = document.getElementById("clusterSearchInput")?.value.trim() || "";
    const subjectId = document.getElementById("clusterSubjectFilter")?.value || "";
    const priority = document.getElementById("clusterPriorityFilter")?.value || "";
    const status = document.getElementById("clusterStatusFilter")?.value || "";

    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (subjectId) params.append("subject_id", subjectId);
    if (priority) params.append("priority", priority);
    if (status) params.append("status", status);

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters?${params.toString()}`, {
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Failed to load doubt clusters.");
        const data = await res.json();
        currentClusters = data.data || [];

        if (countSpan) countSpan.textContent = currentClusters.length;

        if (currentClusters.length === 0) {
            grid.innerHTML = "";
            emptyBox.style.display = "block";
            return;
        }

        emptyBox.style.display = "none";
        grid.innerHTML = currentClusters.map(c => renderClusterCard(c)).join("");
        if (window.lucide) lucide.createIcons();

    } catch (e) {
        console.error("Error loading clusters", e);
        grid.innerHTML = `<p style="color: #DC2626; grid-column: 1 / -1; text-align: center;">Error loading doubt clusters.</p>`;
    }
}

function renderClusterCard(c) {
    const priority = (c.priority || "medium").toLowerCase();
    const pClass = priority === "high" ? "p-high" : (priority === "medium" ? "p-medium" : "p-low");

    let statusPill = `<span class="status-pill st-pending">Pending</span>`;
    if (c.status === "resolved") statusPill = `<span class="status-pill st-resolved">Resolved</span>`;
    else if (c.has_ai_draft) statusPill = `<span class="status-pill st-drafted">AI Draft Ready</span>`;

    const keywords = (c.keywords || "").split(",").map(k => k.trim()).filter(k => k);
    const kwChips = keywords.slice(0, 4).map(k => `<span class="kw-chip">#${escapeHTML(k)}</span>`).join("");

    return `
        <div class="cluster-card" onclick="openClusterDetailModal(${c.id})">
            <div>
                <div class="cluster-card-head">
                    <span class="cluster-sub-badge">${escapeHTML(c.subject_name || "General")}</span>
                    <span class="priority-badge ${pClass}">${escapeHTML(priority)} Priority</span>
                </div>

                <h4 class="cluster-title">${escapeHTML(c.cluster_title)}</h4>
                <p class="cluster-summary">${escapeHTML(c.ai_summary || "No summary available.")}</p>

                ${kwChips ? `<div class="keywords-wrap">${kwChips}</div>` : ''}
            </div>

            <div class="cluster-footer">
                <span class="student-count-pill">
                    <i data-lucide="users" style="width: 15px; height: 15px;"></i>
                    ${c.doubt_count} student${c.doubt_count === 1 ? '' : 's'} asked
                </span>
                ${statusPill}
            </div>
        </div>
    `;
}

// ==========================================
// RUN AI CLUSTERING SYNC
// ==========================================
async function handleClusterSync() {
    const btn = document.getElementById("btnSyncClusters");
    const originalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> Processing & Clustering with AI...`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/process-doubts`, {
            method: "POST",
            headers: authHeaders()
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Clustering failed.");

        alert(data.message || "Doubts clustered successfully!");
        await loadDashboardOverview();
        await loadClusters();
        await loadTopicHeatmap();

    } catch (err) {
        alert("Clustering error: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
        if (window.lucide) lucide.createIcons();
    }
}

// ==========================================
// DETAIL MODAL HANDLERS
// ==========================================
async function openClusterDetailModal(clusterId) {
    activeClusterId = clusterId;
    const modal = document.getElementById("clusterDetailModal");

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters/${clusterId}`, {
            headers: authHeaders()
        });
        if (!res.ok) throw new Error("Could not fetch cluster details.");
        const data = await res.json();
        activeClusterData = data.data;

        document.getElementById("modalSubjBadge").textContent = activeClusterData.subject_name || "Course Subject";
        document.getElementById("modalClusterTitle").textContent = activeClusterData.cluster_title;
        document.getElementById("modalAiSummary").textContent = activeClusterData.ai_summary || "No summary generated.";

        // Priority select
        const prioSelect = document.getElementById("modalPrioritySelect");
        if (prioSelect) prioSelect.value = (activeClusterData.priority || "medium").toLowerCase();

        // Keywords
        const kwWrap = document.getElementById("modalKeywords");
        const kws = (activeClusterData.keywords || "").split(",").map(k => k.trim()).filter(Boolean);
        kwWrap.innerHTML = kws.map(k => `<span class="kw-chip">#${escapeHTML(k)}</span>`).join("");

        // Anonymous doubts list
        const doubtsList = document.getElementById("modalDoubtsList");
        const countSpan = document.getElementById("modalDoubtCount");
        const memberDoubts = activeClusterData.member_doubts || [];

        if (countSpan) countSpan.textContent = memberDoubts.length;

        if (memberDoubts.length > 0) {
            doubtsList.innerHTML = memberDoubts.map((d, idx) => `
                <div class="doubt-bubble">
                    <div class="doubt-bubble-head">
                        <span>Anonymous Student #${idx + 1}</span>
                        <span>${d.created_at ? new Date(d.created_at).toLocaleString() : ''}</span>
                    </div>
                    <div style="font-weight: 600; font-size: 13px; color: #1E293B; margin-bottom: 2px;">${escapeHTML(d.title || "")}</div>
                    <div style="font-size: 13px; color: #475569;">${escapeHTML(d.description || d.question || "")}</div>
                </div>
            `).join("");
        } else {
            doubtsList.innerHTML = `<p style="font-size: 12px; color: #94A3B8;">No individual doubts attached.</p>`;
        }

        // Answer Editor
        const answerText = activeClusterData.published_answer || activeClusterData.teacher_edited_answer || activeClusterData.ai_draft_answer || "";
        document.getElementById("modalAnswerText").value = answerText;

        modal.classList.add("active");
        if (window.lucide) lucide.createIcons();

    } catch (err) {
        alert("Failed to load details: " + err.message);
    }
}

function closeClusterModal() {
    const modal = document.getElementById("clusterDetailModal");
    if (modal) modal.classList.remove("active");
    activeClusterId = null;
    activeClusterData = null;
}

// ==========================================
// AI ANSWER GENERATION (GROQ LLM)
// ==========================================
async function handleGenerateAiDraft() {
    if (!activeClusterId) return;

    const btn = document.getElementById("btnGenerateAiDraft");
    const originalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> Querying Groq LLM...`;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters/${activeClusterId}/generate-answer`, {
            method: "POST",
            headers: authHeaders()
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "AI answer generation failed.");

        const d = data.data || {};
        document.getElementById("modalAnswerText").value = d.draft || "";

        alert("AI Answer Draft generated! Please review, edit as needed, and approve before publishing to students.");
        if (window.lucide) lucide.createIcons();

    } catch (err) {
        alert("AI generation error: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
        if (window.lucide) lucide.createIcons();
    }
}

// ==========================================
// SAVE DRAFT
// ==========================================
async function handleSaveDraft() {
    if (!activeClusterId) return;
    const text = document.getElementById("modalAnswerText").value.trim();
    if (!text) {
        alert("Please write or generate an answer first.");
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters/${activeClusterId}/save-draft`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ answer_text: text })
        });
        if (!res.ok) throw new Error("Failed to save draft.");
        alert("Answer draft saved successfully.");
        await loadClusters();
    } catch (err) {
        alert("Error saving draft: " + err.message);
    }
}

// ==========================================
// PUBLISH ANSWER (HUMAN-IN-THE-LOOP)
// ==========================================
async function handlePublishAnswer() {
    if (!activeClusterId) return;
    const text = document.getElementById("modalAnswerText").value.trim();
    if (!text || text.length < 10) {
        alert("Please provide a comprehensive answer before publishing to students.");
        return;
    }

    if (!confirm("Are you sure you want to approve and publish this verified answer to all students who asked this question?")) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters/${activeClusterId}/publish`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ answer_text: text })
        });

        if (!res.ok) throw new Error("Failed to publish answer.");
        alert("Answer verified and published to students successfully!");
        closeClusterModal();
        await loadDashboardOverview();
        await loadClusters();
        await loadTopicHeatmap();

    } catch (err) {
        alert("Publish error: " + err.message);
    }
}

// ==========================================
// PRIORITY OVERRIDE
// ==========================================
async function handlePriorityOverride() {
    if (!activeClusterId) return;
    const priority = document.getElementById("modalPrioritySelect").value;

    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/clusters/${activeClusterId}/priority`, {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify({ priority: priority })
        });
        if (!res.ok) throw new Error("Failed to update priority.");
        await loadClusters();
    } catch (err) {
        console.error("Priority update error:", err);
    }
}

// ==========================================
// TOPIC DIFFICULTY HEATMAP
// ==========================================
async function loadTopicHeatmap() {
    const grid = document.getElementById("topicHeatmapGrid");
    try {
        const res = await fetch(`${API_BASE_URL}/api/copilot/analytics?days=60`, {
            headers: authHeaders()
        });
        if (!res.ok) return;
        const data = await res.json();
        const heatmap = data.data?.topic_heatmap || [];

        if (heatmap.length === 0) {
            grid.innerHTML = `<p style="color: #94A3B8; font-size: 13px; grid-column: 1 / -1;">No topic clusters identified yet.</p>`;
            return;
        }

        grid.innerHTML = heatmap.slice(0, 8).map(item => {
            const count = item.count;
            const countClass = count >= 10 ? "count-hot" : (count >= 4 ? "count-warm" : "count-cool");
            return `
                <div class="heatmap-item">
                    <span style="font-weight: 600; font-size: 13px; color: #1E293B;">${escapeHTML(item.topic)}</span>
                    <span class="heatmap-count ${countClass}">${count} doubts</span>
                </div>
            `;
        }).join("");

    } catch (e) {
        console.error("Error loading heatmap", e);
    }
}

// ==========================================
// UTILITIES
// ==========================================
function debounce(fn, delay) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
