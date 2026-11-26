/* ==============================================================================
   CLARIQ — STUDENT MY DOUBTS SCRIPT
   Live integration with FastAPI backend & Supabase PostgreSQL
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

let currentSearchTerm = "";
let currentSubjectFilter = "all";
let currentStatusFilter = "all";
let currentSortBy = "latest";
let searchDebounceTimer = null;

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
// INITIALIZATION
// ==========================================

document.addEventListener("DOMContentLoaded", async () => {
    if (!checkAuth()) return;

    setupEventListeners();
    await loadStudentProfile();
    await loadSubjectsDropdown();
    await fetchAndRenderDoubts();

    if (window.lucide) lucide.createIcons();
});

// ==========================================
// 1. SETUP EVENT LISTENERS
// ==========================================

function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById("searchInput");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            clearTimeout(searchDebounceTimer);
            currentSearchTerm = e.target.value.trim();
            searchDebounceTimer = setTimeout(() => {
                fetchAndRenderDoubts();
            }, 300);
        });
    }

    // Subject filter
    const subjectSelect = document.getElementById("subjectSelect");
    if (subjectSelect) {
        subjectSelect.addEventListener("change", (e) => {
            currentSubjectFilter = e.target.value;
            fetchAndRenderDoubts();
        });
    }

    // Sort control
    const sortSelect = document.getElementById("sort-doubts");
    if (sortSelect) {
        sortSelect.addEventListener("change", (e) => {
            currentSortBy = e.target.value;
            fetchAndRenderDoubts();
        });
    }

    // Status tabs
    const statusTabs = document.querySelectorAll(".status-tabs button");
    statusTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            statusTabs.forEach(t => {
                t.className = "status-tab";
            });
            tab.className = "status-tab-active";
            currentStatusFilter = tab.dataset.status || "all";
            fetchAndRenderDoubts();
        });
    });
}

// ==========================================
// 2. LOAD PROFILE & SUBJECTS
// ==========================================

async function loadStudentProfile() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/student/dashboard`, {
            headers: authHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            const p = data.profile;
            const nameEl = document.getElementById("topStudentName");
            const avatarEl = document.getElementById("topAvatar");
            if (nameEl) nameEl.textContent = p.full_name;
            if (avatarEl) avatarEl.textContent = p.full_name.charAt(0).toUpperCase();
        }
    } catch (err) {
        console.error("Failed to load profile:", err);
    }
}

async function loadSubjectsDropdown() {
    const select = document.getElementById("subjectSelect");
    if (!select) return;

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/subjects`, {
            headers: authHeaders()
        });
        if (!response.ok) return;

        const resData = await response.json();
        const subjects = resData.data || [];

        let html = `<option value="all">All Subjects</option>`;
        subjects.forEach(s => {
            html += `<option value="${s.id}">${escapeHTML(s.code)} — ${escapeHTML(s.name)}</option>`;
        });
        select.innerHTML = html;
    } catch (err) {
        console.error("Failed to load subjects:", err);
    }
}

// ==========================================
// 3. FETCH AND RENDER DOUBTS
// ==========================================

async function fetchAndRenderDoubts() {
    const container = document.getElementById("doubtContainer");
    if (!container) return;

    container.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #64748B;">
            <p>Loading your doubts...</p>
        </div>
    `;

    try {
        const params = new URLSearchParams();
        if (currentSearchTerm) params.append("search", currentSearchTerm);
        if (currentSubjectFilter && currentSubjectFilter !== "all") params.append("subject_id", currentSubjectFilter);
        if (currentStatusFilter && currentStatusFilter !== "all") params.append("status_filter", currentStatusFilter);
        if (currentSortBy) params.append("sort_by", currentSortBy);

        const url = `${API_BASE_URL}/api/student/doubts?${params.toString()}`;
        const response = await fetch(url, { headers: authHeaders() });

        if (!response.ok) {
            throw new Error("Failed to fetch doubts.");
        }

        const res = await response.json();
        const doubts = res.data || [];

        if (doubts.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 50px 20px; background: white; border-radius: 16px; border: 1px dashed #CBD5E1; color: #64748B; margin-top: 16px;">
                    <i data-lucide="inbox" style="width: 44px; height: 44px; margin-bottom: 12px; color: #94A3B8;"></i>
                    <h3 style="font-size: 16px; font-weight: 600; color: #1E293B; margin: 0 0 6px;">No Doubts Found</h3>
                    <p style="font-size: 13px; margin: 0 0 16px; color: #64748B;">Try adjusting your search or filters, or ask a new doubt.</p>
                    <button class="ask-doubt-btn" onclick="window.location.href='ask-doubt.html'" style="display: inline-flex; align-items: center; gap: 6px; padding: 10px 18px;">
                        <i data-lucide="plus"></i>
                        <span>Ask a Doubt</span>
                    </button>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        container.innerHTML = doubts.map(d => {
            const isResolved = d.status === "resolved";
            const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day: 'numeric', month: 'short', year: 'numeric' }) : "";
            const teacherName = d.assigned_teacher ? d.assigned_teacher.name : "Assigned Faculty";

            let verifiedAnswerHtml = "";
            if (d.verified_answers && d.verified_answers.length > 0) {
                const ans = d.verified_answers[0];
                verifiedAnswerHtml = `
                    <div style="margin-top: 14px; background: #ECFDF5; border-left: 3px solid #10B981; padding: 10px 14px; border-radius: 0 8px 8px 0; font-size: 13px;">
                        <div style="display: flex; align-items: center; gap: 6px; color: #047857; font-weight: 700; margin-bottom: 4px; font-size: 12px;">
                            <i data-lucide="badge-check" style="width: 14px; height: 14px;"></i>
                            <span>Verified Answer by ${escapeHTML(ans.teacher_name)}</span>
                        </div>
                        <p style="margin: 0; color: #065F46; line-height: 1.5;">${escapeHTML(ans.answer_text)}</p>
                        <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; align-items:center;">
                            ${ans.resource_url ? `<a href="${escapeHTML(ans.resource_url)}" target="_blank" style="display:inline-block; color:#2563EB; font-size:12px; font-weight:600;">Resource Link &rarr;</a>` : ''}
                            ${ans.answer_attachment_name ? `<button type="button" onclick='openProtectedFile("${API_BASE_URL}/api/student/doubts/${d.id}/answer-file/${ans.id}", ${JSON.stringify(ans.answer_attachment_name)})' style="display:inline-flex; align-items:center; gap:5px; background:white; color:#047857; border:1px solid #A7F3D0; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer;">📎 Solution File: ${escapeHTML(ans.answer_attachment_name)}</button>` : ''}
                        </div>
                    </div>
                `;
            }

            const studentAttHtml = (d.attachments && d.attachments.length > 0) ? `
                <div style="margin: 8px 0 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
                    <span style="font-size: 11px; font-weight: 600; color: #64748B;">Attached:</span>
                    ${d.attachments.map(att => {
                        const icon = att.mime_type && att.mime_type.startsWith("image/") ? "🖼️" : "📄";
                        return `<button type="button" onclick='openProtectedFile("${API_BASE_URL}/api/student/doubts/attachments/${att.id}", ${JSON.stringify(att.original_filename)})' style="display:inline-flex; align-items:center; gap:4px; background:#F1F5F9; color:#334155; border:1px solid #CBD5E1; padding:3px 9px; border-radius:6px; font-size:12px; font-weight:500; cursor:pointer;">${icon} ${escapeHTML(att.original_filename)}</button>`;
                    }).join("")}
                </div>
            ` : "";

            return `
                <div style="background: white; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px 24px; margin-top: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); transition: transform 0.15s, box-shadow 0.15s;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 10px;">
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <span style="display: inline-block; background: #EEF2FF; color: #4F46E5; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 6px;">
                                ${escapeHTML(d.subject.code || d.subject.name)}
                            </span>
                            <span style="font-size: 12px; color: #94A3B8;">${dateStr}</span>
                            <span style="font-size: 11px; background: #F1F5F9; color: #64748B; padding: 2px 8px; border-radius: 4px; font-weight: 600;">
                                ID: ${escapeHTML(d.doubt_code)}
                            </span>
                        </div>
                        <span style="display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${isResolved ? '#DCFCE7' : '#FEF3C7'}; color: ${isResolved ? '#166534' : '#92400E'};">
                            ${isResolved ? 'Resolved' : 'Pending Review'}
                        </span>
                    </div>

                    <h3 style="font-size: 16px; font-weight: 600; color: #1E293B; margin: 0 0 8px;">
                        ${escapeHTML(d.title)}
                    </h3>

                    <p style="font-size: 14px; color: #475569; margin: 0 0 12px; line-height: 1.5;">
                        ${escapeHTML(d.description)}
                    </p>

                    ${studentAttHtml}
                    ${verifiedAnswerHtml}

                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 12px; border-top: 1px solid #F1F5F9; font-size: 13px; color: #64748B;">
                        <span>Routed To: <strong style="color: #334155;">${escapeHTML(teacherName)}</strong></span>
                        <button type="button" onclick="openDoubtDetailModal(${d.id})" style="padding: 6px 14px; background: #F1F5F9; color: #475569; border: none; border-radius: 8px; font-weight: 600; font-size: 12px; cursor: pointer;">
                            View Full Detail &rarr;
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons();

    } catch (err) {
        container.innerHTML = `
            <div style="text-align: center; padding: 30px; color: #EF4444; background: white; border-radius: 14px;">
                <p>Failed to load doubts: ${escapeHTML(err.message)}</p>
            </div>
        `;
    }
}

// ==========================================
// 4. DETAIL MODAL
// ==========================================

async function openDoubtDetailModal(doubtId) {
    const modal = document.getElementById("doubtDetailModal");
    if (modal) modal.style.display = "flex";

    const codeEl = document.getElementById("detailDoubtCode");
    const statusEl = document.getElementById("detailDoubtStatus");
    const titleEl = document.getElementById("detailDoubtTitle");
    const subjectEl = document.getElementById("detailDoubtSubject");
    const dateEl = document.getElementById("detailDoubtDate");
    const descEl = document.getElementById("detailDoubtDesc");
    const facultyNameEl = document.getElementById("detailFacultyName");
    const facultyDeptEl = document.getElementById("detailFacultyDept");
    const ansContainer = document.getElementById("detailAnswerContainer");

    if (descEl) descEl.textContent = "Loading details...";

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/doubts/${doubtId}`, {
            headers: authHeaders()
        });
        if (!response.ok) throw new Error("Failed to load doubt details.");

        const res = await response.json();
        const d = res.data;

        if (codeEl) codeEl.textContent = d.doubt_code || `DOUBT-${d.id}`;
        if (statusEl) {
            const isResolved = d.status === "resolved";
            statusEl.textContent = isResolved ? "Resolved" : "Pending Review";
            statusEl.style.background = isResolved ? "#DCFCE7" : "#FEF3C7";
            statusEl.style.color = isResolved ? "#166534" : "#92400E";
        }
        if (titleEl) titleEl.textContent = d.title;
        if (subjectEl) subjectEl.textContent = `${d.subject.name} (${d.subject.code})`;
        if (dateEl) dateEl.textContent = d.created_at ? new Date(d.created_at).toLocaleString("en-IN") : "-";
        if (descEl) {
            descEl.innerHTML = `<div style="white-space: pre-wrap;">${escapeHTML(d.description)}</div>` +
                ((d.attachments && d.attachments.length > 0) ? `
                    <div style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed #CBD5E1; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
                        <span style="font-size: 12px; font-weight: 600; color: #64748B;">Your Attachments:</span>
                        ${d.attachments.map(att => {
                            const icon = att.mime_type && att.mime_type.startsWith("image/") ? "🖼️" : "📄";
                            return `<button type="button" onclick='openProtectedFile("${API_BASE_URL}/api/student/doubts/attachments/${att.id}", ${JSON.stringify(att.original_filename)})' style="display:inline-flex; align-items:center; gap:5px; background:white; color:#334155; border:1px solid #CBD5E1; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer;">${icon} ${escapeHTML(att.original_filename)}</button>`;
                        }).join("")}
                    </div>
                ` : "");
        }

        if (facultyNameEl) {
            facultyNameEl.textContent = d.assigned_teacher ? d.assigned_teacher.name : "Assigned Faculty";
        }
        if (facultyDeptEl) {
            facultyDeptEl.textContent = d.assigned_teacher ? `${d.assigned_teacher.department} • ${d.assigned_teacher.designation || 'Faculty'}` : "Primary Faculty";
        }

        if (ansContainer) {
            if (d.verified_answers && d.verified_answers.length > 0) {
                ansContainer.innerHTML = d.verified_answers.map(ans => `
                    <div style="background: #ECFDF5; border-left: 3px solid #10B981; padding: 14px 16px; border-radius: 0 8px 8px 0; margin-top: 10px;">
                        <div style="display: flex; align-items: center; gap: 6px; color: #047857; font-weight: 700; margin-bottom: 6px; font-size: 13px;">
                            <i data-lucide="check-circle" style="width: 16px; height: 16px;"></i>
                            <span>Verified Answer by ${escapeHTML(ans.teacher_name)}</span>
                        </div>
                        <p style="margin: 0 0 8px; color: #065F46; line-height: 1.6; font-size: 14px; white-space: pre-wrap;">${escapeHTML(ans.answer_text)}</p>
                        <div style="display:flex; flex-wrap:wrap; gap:10px; align-items:center;">
                            ${ans.resource_url ? `<a href="${escapeHTML(ans.resource_url)}" target="_blank" style="display:inline-block; color:#2563EB; font-size:13px; font-weight:600;">Resource Link &rarr;</a>` : ''}
                            ${ans.answer_attachment_name ? `<button type="button" onclick='openProtectedFile("${API_BASE_URL}/api/student/doubts/${d.id}/answer-file/${ans.id}", ${JSON.stringify(ans.answer_attachment_name)})' style="display:inline-flex; align-items:center; gap:6px; background:white; color:#047857; border:1px solid #A7F3D0; padding:6px 12px; border-radius:8px; font-size:13px; font-weight:600; cursor:pointer;">📎 Download Solution: ${escapeHTML(ans.answer_attachment_name)}</button>` : ''}
                        </div>
                        <div style="font-size: 11px; color: #059669; margin-top: 8px;">Answered on: ${ans.created_at ? new Date(ans.created_at).toLocaleString("en-IN") : ''}</div>
                    </div>
                `).join("");
            } else {
                ansContainer.innerHTML = `
                    <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 10px; padding: 16px; text-align: center; color: #64748B; font-size: 13px;">
                        <i data-lucide="clock" style="width: 20px; height: 20px; color: #D97706; margin-bottom: 4px;"></i>
                        <p style="margin: 0; font-weight: 500;">Your doubt has been delivered to your faculty and is awaiting human verification.</p>
                    </div>
                `;
            }
        }

        if (window.lucide) lucide.createIcons();

    } catch (err) {
        if (descEl) descEl.textContent = `Error: ${err.message}`;
    }
}

async function openProtectedFile(url, filename) {
    try {
        const res = await fetch(url, {
            headers: { "Authorization": `Bearer ${getAuthToken()}` }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Could not load file.");
        }
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const win = window.open(blobUrl, "_blank");
        if (!win) {
            const a = document.createElement("a");
            a.href = blobUrl;
            a.download = filename || "file";
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
        alert(err.message || "Failed to open file.");
    }
}

function closeDoubtDetailModal() {
    const modal = document.getElementById("doubtDetailModal");
    if (modal) modal.style.display = "none";
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
