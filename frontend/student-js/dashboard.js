/* ==============================================================================
   CLARIQ — STUDENT DASHBOARD SCRIPT
   Dynamically integrates with FastAPI backend & Supabase PostgreSQL
   ============================================================================== */

const API_BASE_URL = window.location.hostname === "localhost" ? "http://localhost:8000" : "http://127.0.0.1:8000";

let currentStudentData = null;
let allStudentDoubts = [];
let currentFilter = "all";

function getAuthToken() {
    return sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
}

function authHeaders() {
    const token = getAuthToken();
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
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
    await loadDashboardData();
    await loadStudentDoubts();
    if (window.lucide) {
        lucide.createIcons();
    }
});

// ==========================================
// 1. LOAD DASHBOARD DATA
// ==========================================

async function loadDashboardData() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/student/dashboard`, {
            headers: authHeaders()
        });

        if (response.status === 401 || response.status === 403) {
            handleLogout();
            return;
        }

        const data = await response.json();
        currentStudentData = data;

        // Dynamic Greeting
        const profile = data.profile;
        const now = new Date();
        const hour = now.getHours();
        let greeting = "Good morning";
        if (hour >= 12 && hour < 17) greeting = "Good afternoon";
        else if (hour >= 17) greeting = "Good evening";

        const welcomeEl = document.getElementById("welcomeGreeting");
        if (welcomeEl) {
            welcomeEl.textContent = `${greeting}, ${profile.full_name}!`;
        }

        const subtitleEl = document.getElementById("welcomeSubtitle");
        if (subtitleEl) {
            const semLabel = profile.current_semester
                ? `Semester ${profile.current_semester}`
                : (profile.semester || "");
            subtitleEl.textContent = `${profile.department} • ${semLabel} • Section ${profile.section} • ${profile.academic_year}`;
        }

        // Top Navigation
        const navName = document.getElementById("navStudentName");
        const navAvatar = document.getElementById("navAvatar");
        if (navName) navName.textContent = profile.full_name;
        if (navAvatar) navAvatar.textContent = profile.full_name.charAt(0).toUpperCase();

        // Statistics
        const stats = data.statistics;
        document.getElementById("statTotalDoubts").textContent = stats.total_doubts;
        document.getElementById("statPendingDoubts").textContent = stats.pending_doubts;
        document.getElementById("statResolvedDoubts").textContent = stats.resolved_doubts;

        // Update "My Enrolled Subjects" section heading with semester label
        const subjectSectionHeader = document.querySelector(".subjects-section h2");
        if (subjectSectionHeader) {
            if (profile.current_semester) {
                subjectSectionHeader.textContent = `My Subjects — Semester ${profile.current_semester}`;
            } else if (data.subjects && data.subjects.length === 0 && data.semester_warning) {
                subjectSectionHeader.textContent = "My Enrolled Subjects";
            } else {
                subjectSectionHeader.textContent = "My Enrolled Subjects";
            }
        }

        // Handle unassigned semester warning
        if (data.semester_warning) {
            renderSubjects([], data.semester_warning);
        } else {
            // Render My Subjects
            renderSubjects(data.subjects);
        }
        populateSubjectDropdown(data.subjects || []);

        // Render Recent Study Materials uploaded by teachers
        renderRecentStudyMaterials(data.recent_resources || []);

    } catch (err) {
        console.error("Failed to load student dashboard:", err);
    }
}

// ==========================================
// 2. RENDER ENROLLED SUBJECTS
// ==========================================

function renderSubjects(subjects, warningMessage) {
    const grid = document.getElementById("mySubjectsGrid");
    if (!grid) return;

    // Show semester unassigned warning
    if (warningMessage) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 36px 24px; background: #FFF7ED; border: 1px solid #FED7AA; border-radius: 16px; color: #92400E;">
                <div style="font-size: 32px; margin-bottom: 10px;">📚</div>
                <h3 style="font-size: 16px; font-weight: 700; margin-bottom: 8px; color: #92400E;">Academic Semester Not Assigned</h3>
                <p style="font-size: 14px; color: #B45309;">${escapeHTML(warningMessage)}</p>
                <p style="font-size: 12px; margin-top: 8px; color: #D97706;">Please contact your administrator to have your semester assigned.</p>
            </div>
        `;
        return;
    }

    if (!subjects || subjects.length === 0) {
        grid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 30px; background: white; border-radius: 16px; color: #64748B;">
                <p>No subjects are currently assigned to your semester.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = subjects.map(s => `
        <div class="subject-card">
            <div>
                <span class="subject-code-badge">${s.code}</span>
                <h3 class="subject-title">${escapeHTML(s.name)}</h3>
                <div class="subject-faculty">
                    <i data-lucide="user" style="width:14px; height:14px;"></i>
                    <span>${escapeHTML(s.teacher_name)}</span>
                </div>
                ${s.resources_count ? `
                    <div style="margin-top: 8px;">
                        <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:600; padding:3px 10px; border-radius:12px; background:#EFF6FF; color:#2563EB; border:1px solid #DBEAFE;">
                            <i data-lucide="file-check" style="width:12px; height:12px;"></i>
                            ${s.resources_count} Study Material${s.resources_count > 1 ? 's' : ''} Uploaded
                        </span>
                    </div>
                ` : `
                    <div style="margin-top: 8px;">
                        <span style="display:inline-flex; align-items:center; gap:5px; font-size:11px; font-weight:500; padding:3px 10px; border-radius:12px; background:#F8FAFC; color:#64748B;">
                            <i data-lucide="book-open" style="width:12px; height:12px;"></i>
                            Library Available
                        </span>
                    </div>
                `}
            </div>
            <div>
                <div style="font-size: 12px; color: #64748B; margin-bottom: 12px;">
                    <strong>${s.my_doubts_count}</strong> doubts asked by you
                </div>
                <div class="subject-card-actions" style="display: flex; gap: 6px; flex-wrap: wrap;">
                    <button class="btn-sub-ask" onclick="openAskDoubtModal(${s.id})">
                        <i data-lucide="plus-circle" style="width:14px; height:14px;"></i>
                        <span>Ask Doubt</span>
                    </button>
                    <button class="btn-sub-view" onclick="filterDoubtsBySubject(${s.id})">
                        View Doubts
                    </button>
                    <a href="library.html?subject_id=${s.id}" class="btn-sub-view" style="text-decoration:none; display:inline-flex; align-items:center; gap:4px; background:#F8FAFC; border:1px solid #CBD5E1; color:#334155;" title="Open Subject Academic Library">
                        <i data-lucide="folder-open" style="width:13px; height:13px; color:#4965E8;"></i>
                        <span>Library</span>
                    </a>
                </div>
            </div>
        </div>
    `).join("");

    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 2.1 RENDER RECENT STUDY MATERIALS
// ==========================================

function renderRecentStudyMaterials(resources) {
    const container = document.getElementById("recentResourcesGrid");
    if (!container) return;

    if (!resources || resources.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1 / -1; text-align: center; padding: 28px; background: white; border-radius: 16px; border: 1px dashed #CBD5E1; color: #64748B;">
                <i data-lucide="folder-open" style="width: 28px; height: 28px; color: #94A3B8; margin-bottom: 8px;"></i>
                <p style="font-size: 14px; font-weight: 600; margin: 0 0 4px; color: #334155;">No uploaded files yet for your semester</p>
                <p style="font-size: 12px; color: #94A3B8; margin: 0 0 12px;">Subject faculties will publish syllabi, lecture notes, and video references here.</p>
                <a href="library.html" style="font-size: 13px; color: #4965E8; font-weight: 600; text-decoration: none;">Browse Full Academic Library &rarr;</a>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = resources.map(r => {
        const isYt = r.resource_type === 'youtube';
        const icon = isYt ? 'youtube' : (r.resource_type === 'pdf' ? 'file-text' : 'file');
        const iconBg = isYt ? '#FEE2E2' : (r.resource_type === 'pdf' ? '#EFF6FF' : '#F0FDF4');
        const iconColor = isYt ? '#DC2626' : (r.resource_type === 'pdf' ? '#2563EB' : '#16A34A');
        const uploadDate = r.created_at ? new Date(r.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
        const sizeStr = r.file_size ? ` • ${formatBytes(r.file_size)}` : '';

        return `
            <div class="resource-card-mini" style="background: white; border: 1px solid #E2E8F0; border-radius: 14px; padding: 16px; display: flex; flex-direction: column; justify-content: space-between; gap: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.02); transition: transform 0.15s, box-shadow 0.15s;" onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 16px rgba(0,0,0,0.06)';" onmouseout="this.style.transform='none'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.02)';">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <div style="width: 36px; height: 36px; border-radius: 10px; background: ${iconBg}; color: ${iconColor}; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                            <i data-lucide="${icon}" style="width: 18px; height: 18px;"></i>
                        </div>
                        <span style="font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 8px; background: #F1F5F9; color: #475569;">
                            ${escapeHTML(r.subject_code || r.subject_name)}
                        </span>
                    </div>
                    <h4 style="font-size: 14px; font-weight: 700; color: #1E293B; margin: 0 0 4px; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;" title="${escapeHTML(r.title)}">
                        ${escapeHTML(r.title)}
                    </h4>
                    <p style="font-size: 12px; color: #64748B; margin: 0;">
                        By ${escapeHTML(r.teacher_name)}
                    </p>
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 10px; border-top: 1px solid #F1F5F9;">
                    <span style="font-size: 11px; color: #94A3B8;">
                        ${uploadDate}${sizeStr}
                    </span>
                    <a href="library.html?subject_id=${r.subject_id}" style="display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 600; color: #4965E8; text-decoration: none; padding: 4px 10px; border-radius: 6px; background: #EEF2FF;">
                        <span>${isYt ? 'Watch' : 'Open'}</span>
                        <i data-lucide="arrow-right" style="width: 12px; height: 12px;"></i>
                    </a>
                </div>
            </div>
        `;
    }).join("");

    if (window.lucide) lucide.createIcons();
}

function formatBytes(bytes, decimals = 1) {
    if (!bytes) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function populateSubjectDropdown(subjects) {
    const select = document.getElementById("doubtSubjectSelect");
    if (!select) return;

    select.innerHTML = `<option value="">Select an enrolled subject...</option>` +
        subjects.map(s => `<option value="${s.id}">${escapeHTML(s.code)} — ${escapeHTML(s.name)}</option>`).join("");
}

// ==========================================
// 3. LOAD & RENDER MY DOUBTS
// ==========================================

async function loadStudentDoubts() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/student/doubts`, {
            headers: authHeaders()
        });
        if (response.ok) {
            const result = await response.json();
            allStudentDoubts = result.data || [];
            renderDoubtsList(allStudentDoubts);
        }
    } catch (err) {
        console.error("Failed to load doubts:", err);
    }
}

function renderDoubtsList(doubts) {
    const container = document.getElementById("myDoubtsContainer");
    if (!container) return;

    let filtered = doubts;
    if (currentFilter === "pending") {
        filtered = doubts.filter(d => d.status !== "resolved");
    } else if (currentFilter === "resolved") {
        filtered = doubts.filter(d => d.status === "resolved");
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; background: white; border-radius: 16px; border: 1px dashed #CBD5E1; color: #64748B;">
                <i data-lucide="inbox" style="width: 36px; height: 36px; margin-bottom: 8px; color: #94A3B8;"></i>
                <p style="font-size: 15px; font-weight: 600; color: #334155;">No doubts found</p>
                <p style="font-size: 13px;">${currentFilter === 'all' ? 'You have not submitted any doubts yet.' : 'No doubts match the selected filter.'}</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = filtered.map(d => {
        const isResolved = d.status === "resolved";
        const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day: 'numeric', month: 'short', year: 'numeric' }) : "";

        let verifiedAnswersHtml = "";
        if (d.verified_answers && d.verified_answers.length > 0) {
            verifiedAnswersHtml = d.verified_answers.map(ans => `
                <div class="verified-answer-box">
                    <div class="verified-badge">
                        <i data-lucide="badge-check" style="width:14px; height:14px;"></i>
                        <span>Verified Answer by ${escapeHTML(ans.teacher_name)}</span>
                    </div>
                    <p style="margin: 4px 0 0; color: #1E293B; line-height: 1.5;">${escapeHTML(ans.answer_text)}</p>
                    ${ans.resource_url ? `<a href="${escapeHTML(ans.resource_url)}" target="_blank" style="display:inline-block; margin-top:6px; color:#2563EB; font-size:12px; font-weight:600;">View Attached Resource &rarr;</a>` : ''}
                </div>
            `).join("");
        }

        return `
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 14px; padding: 18px 22px; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 8px;">
                    <div>
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                            <span class="subject-code-badge" style="margin-bottom:0;">${escapeHTML(d.subject.code || d.subject.name)}</span>
                            <span style="font-size: 12px; color: #94A3B8;">${dateStr}</span>
                            <span style="font-size: 11px; background: #F1F5F9; color: #64748B; padding: 2px 6px; border-radius: 4px;">ID: ${escapeHTML(d.doubt_code)}</span>
                        </div>
                        <h4 style="font-size: 16px; font-weight: 600; color: #1E293B; margin: 0 0 6px;">${escapeHTML(d.title)}</h4>
                        <p style="font-size: 14px; color: #475569; margin: 0; line-height: 1.5;">${escapeHTML(d.description)}</p>
                    </div>
                    <div>
                        <span style="display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; background: ${isResolved ? '#DCFCE7' : '#FEF3C7'}; color: ${isResolved ? '#166534' : '#92400E'};">
                            ${isResolved ? 'Resolved' : 'Pending Review'}
                        </span>
                    </div>
                </div>
                ${verifiedAnswersHtml}
            </div>
        `;
    }).join("");

    if (window.lucide) lucide.createIcons();
}

function filterDoubts(status) {
    currentFilter = status;
    ["filterAll", "filterPending", "filterResolved"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.background = "#F1F5F9";
    });
    const activeBtn = document.getElementById(status === 'all' ? 'filterAll' : (status === 'pending' ? 'filterPending' : 'filterResolved'));
    if (activeBtn) activeBtn.style.background = "#E2E8F0";
    renderDoubtsList(allStudentDoubts);
}

// ==========================================
// SUBJECT DOUBTS MODAL & DETAILS
// ==========================================

let activeSubjectIdForDoubts = null;

async function filterDoubtsBySubject(subjectId) {
    activeSubjectIdForDoubts = subjectId;
    const modal = document.getElementById("subjectDoubtsModal");
    const titleEl = document.getElementById("subjectDoubtsModalTitle");
    const subEl = document.getElementById("subjectDoubtsModalSub");
    const listEl = document.getElementById("subjectDoubtsList");
    const askBtn = document.getElementById("btnAskSubjectDoubt");

    if (askBtn) {
        askBtn.onclick = () => {
            closeSubjectDoubtsModal();
            openAskDoubtModal(subjectId);
        };
    }

    if (modal) modal.classList.add("active");
    if (listEl) {
        listEl.innerHTML = `<div style="text-align: center; padding: 24px; color: #64748B;">Loading subject doubts...</div>`;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/subjects/${subjectId}/doubts`, {
            headers: authHeaders()
        });
        if (!response.ok) throw new Error("Failed to load doubts for this subject.");

        const resData = await response.json();
        const subject = resData.subject;
        const doubts = resData.doubts || [];

        if (titleEl) titleEl.textContent = `${subject.name} (${subject.code})`;
        if (subEl) subEl.textContent = `${doubts.length} doubt${doubts.length === 1 ? '' : 's'} submitted by you`;

        if (doubts.length === 0) {
            listEl.innerHTML = `
                <div style="text-align: center; padding: 30px; background: #F8FAFC; border-radius: 12px; border: 1px dashed #CBD5E1; color: #64748B;">
                    <i data-lucide="inbox" style="width: 32px; height: 32px; margin-bottom: 8px; color: #94A3B8;"></i>
                    <p style="font-weight: 600; color: #334155; margin: 0 0 4px;">No doubts for this subject</p>
                    <p style="font-size: 13px; margin: 0;">You haven't asked any questions in ${escapeHTML(subject.name)} yet.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        listEl.innerHTML = doubts.map(d => {
            const isResolved = d.status === "resolved";
            const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day: 'numeric', month: 'short', year: 'numeric' }) : "";
            const teacherName = d.assigned_teacher ? d.assigned_teacher.name : "Assigned Faculty";

            let answerSnippet = "";
            if (d.verified_answers && d.verified_answers.length > 0) {
                const firstAns = d.verified_answers[0];
                answerSnippet = `
                    <div style="margin-top: 10px; background: #ECFDF5; border-left: 3px solid #10B981; padding: 8px 12px; border-radius: 0 6px 6px 0; font-size: 12px;">
                        <span style="font-weight: 700; color: #047857;">Verified Answer:</span>
                        <span style="color: #065F46;">${escapeHTML(firstAns.answer_text.substring(0, 140))}${firstAns.answer_text.length > 140 ? '...' : ''}</span>
                    </div>
                `;
            }

            return `
                <div style="background: white; border: 1px solid #E2E8F0; border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.02);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                        <span style="font-size: 11px; background: #EEF2FF; color: #4338CA; font-weight: 700; padding: 2px 8px; border-radius: 4px;">${escapeHTML(d.doubt_code)}</span>
                        <span style="font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 12px; background: ${isResolved ? '#DCFCE7' : '#FEF3C7'}; color: ${isResolved ? '#166534' : '#92400E'};">
                            ${isResolved ? 'Resolved' : 'Pending Review'}
                        </span>
                    </div>
                    <h4 style="font-size: 15px; font-weight: 600; color: #1E293B; margin: 0 0 6px;">${escapeHTML(d.title)}</h4>
                    <p style="font-size: 13px; color: #64748B; margin: 0 0 10px; line-height: 1.4;">${escapeHTML(d.description.substring(0, 180))}${d.description.length > 180 ? '...' : ''}</p>
                    ${answerSnippet}
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px; font-size: 12px; color: #94A3B8;">
                        <span>To: <strong style="color: #475569;">${escapeHTML(teacherName)}</strong> • ${dateStr}</span>
                        <button type="button" class="btn-sub-view" onclick="openDoubtDetailModal(${d.id})" style="padding: 4px 10px; font-size: 11px;">
                            View Full Detail &rarr;
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        if (window.lucide) lucide.createIcons();

    } catch (err) {
        if (listEl) {
            listEl.innerHTML = `<div style="text-align: center; color: #EF4444; padding: 20px;">${escapeHTML(err.message)}</div>`;
        }
    }
}

function closeSubjectDoubtsModal() {
    const modal = document.getElementById("subjectDoubtsModal");
    if (modal) modal.classList.remove("active");
}

async function openDoubtDetailModal(doubtId) {
    const modal = document.getElementById("doubtDetailModal");
    if (modal) modal.classList.add("active");

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
        if (descEl) descEl.textContent = d.description;

        if (facultyNameEl) {
            facultyNameEl.textContent = d.assigned_teacher ? d.assigned_teacher.name : "Assigned Faculty";
        }
        if (facultyDeptEl) {
            facultyDeptEl.textContent = d.assigned_teacher ? `${d.assigned_teacher.department} • ${d.assigned_teacher.designation || 'Faculty'}` : "Primary Faculty";
        }

        if (ansContainer) {
            if (d.verified_answers && d.verified_answers.length > 0) {
                ansContainer.innerHTML = d.verified_answers.map(ans => `
                    <div class="verified-answer-box" style="margin-top: 0; padding: 14px 16px;">
                        <div class="verified-badge" style="font-size: 13px; margin-bottom: 6px;">
                            <i data-lucide="check-circle" style="width:16px; height:16px;"></i>
                            <span>Verified Answer by ${escapeHTML(ans.teacher_name)}</span>
                        </div>
                        <p style="margin: 0 0 8px; color: #1E293B; line-height: 1.6; font-size: 14px; white-space: pre-wrap;">${escapeHTML(ans.answer_text)}</p>
                        ${ans.resource_url ? `<a href="${escapeHTML(ans.resource_url)}" target="_blank" style="display:inline-block; color:#2563EB; font-size:13px; font-weight:600;">Resource Link &rarr;</a>` : ''}
                        <div style="font-size: 11px; color: #94A3B8; margin-top: 8px;">Answered on: ${ans.created_at ? new Date(ans.created_at).toLocaleString("en-IN") : ''}</div>
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

function closeDoubtDetailModal() {
    const modal = document.getElementById("doubtDetailModal");
    if (modal) modal.classList.remove("active");
}

// ==========================================
// 4. ASK ANONYMOUS DOUBT MODAL
// ==========================================

async function handleSubjectChange(subjectId) {
    const group = document.getElementById("facultySelectGroup");
    const teacherSelect = document.getElementById("doubtTeacherSelect");
    if (!subjectId) {
        if (group) group.style.display = "none";
        return;
    }

    if (group) group.style.display = "block";
    if (teacherSelect) {
        teacherSelect.innerHTML = `<option value="">Loading faculty list...</option>`;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/subjects/${subjectId}/teachers`, {
            headers: authHeaders()
        });
        if (!response.ok) throw new Error("Could not load faculty.");

        const data = await response.json();
        const teachers = data.data || [];

        if (teachers.length === 0) {
            if (teacherSelect) teacherSelect.innerHTML = `<option value="">No faculty assigned to this subject yet</option>`;
            return;
        }

        const primaryT = teachers.find(t => t.is_primary);
        const addlTeachers = teachers.filter(t => !t.is_primary);

        let optionsHtml = "";
        if (primaryT) {
            optionsHtml += `<option value="">Default — ${escapeHTML(primaryT.full_name || primaryT.name)} (Primary Faculty)</option>`;
            optionsHtml += `<option value="${primaryT.id}">${escapeHTML(primaryT.full_name || primaryT.name)} (Primary Faculty)</option>`;
        } else {
            optionsHtml += `<option value="">Default (Assigned Primary Faculty)</option>`;
        }

        addlTeachers.forEach(t => {
            optionsHtml += `<option value="${t.id}">${escapeHTML(t.full_name || t.name)} (Additional Faculty)</option>`;
        });

        if (teacherSelect) teacherSelect.innerHTML = optionsHtml;

    } catch (err) {
        console.error("Failed to load teachers for subject:", err);
        if (teacherSelect) {
            teacherSelect.innerHTML = `<option value="">Default (Assigned Primary Faculty)</option>`;
        }
    }
}

function openAskDoubtModal(subjectId = null) {
    const modal = document.getElementById("askDoubtModal");
    if (modal) {
        modal.classList.add("active");
        if (subjectId) {
            const select = document.getElementById("doubtSubjectSelect");
            if (select) {
                select.value = subjectId;
                handleSubjectChange(subjectId);
            }
        }
    }
}

function closeAskDoubtModal() {
    const modal = document.getElementById("askDoubtModal");
    if (modal) modal.classList.remove("active");
    const form = document.getElementById("askDoubtForm");
    if (form) form.reset();
    const group = document.getElementById("facultySelectGroup");
    if (group) group.style.display = "none";
}

async function handleDoubtSubmit(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSubmitDoubt");
    btn.disabled = true;
    btn.textContent = "Submitting Anonymously...";

    try {
        const subjectId = parseInt(document.getElementById("doubtSubjectSelect").value);
        const title = document.getElementById("doubtTitle").value.trim();
        const description = document.getElementById("doubtDescription").value.trim();
        const teacherSelect = document.getElementById("doubtTeacherSelect");
        const teacherId = teacherSelect && teacherSelect.value ? parseInt(teacherSelect.value) : null;

        const response = await fetch(`${API_BASE_URL}/api/student/doubts`, {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({
                subject_id: subjectId,
                title: title,
                description: description,
                teacher_id: teacherId
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Submission failed.");
        }

        alert("Doubt submitted anonymously! Your identity is protected.");
        closeAskDoubtModal();
        await loadDashboardData();
        await loadStudentDoubts();

    } catch (err) {
        alert(err.message || "Unable to submit doubt.");
    } finally {
        btn.disabled = false;
        btn.textContent = "Submit Anonymously";
    }
}

// ==========================================
// 5. PROFILE MODAL & LOGOUT
// ==========================================

function openProfileModal() {
    const modal = document.getElementById("profileModal");
    if (!modal || !currentStudentData) return;

    const p = currentStudentData.profile;
    document.getElementById("modalName").textContent = p.full_name;
    document.getElementById("modalCollegeId").textContent = `ID: ${p.college_id}`;
    document.getElementById("modalDept").textContent = p.department;
    document.getElementById("modalSem").textContent = p.semester;
    document.getElementById("modalSec").textContent = p.section;
    document.getElementById("modalYear").textContent = p.academic_year;
    document.getElementById("modalAvatar").textContent = p.full_name.charAt(0).toUpperCase();

    document.getElementById("editFullName").value = p.full_name;
    document.getElementById("editEmail").value = p.email || "";

    modal.classList.add("active");
}

function closeProfileModal() {
    const modal = document.getElementById("profileModal");
    if (modal) modal.classList.remove("active");
}

async function handleProfileUpdate(e) {
    e.preventDefault();
    const btn = document.getElementById("btnSaveProfile");
    btn.disabled = true;
    btn.textContent = "Saving...";

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/profile`, {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify({
                full_name: document.getElementById("editFullName").value.trim(),
                email: document.getElementById("editEmail").value.trim()
            })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "Failed to update profile.");

        alert("Profile updated successfully!");
        closeProfileModal();
        await loadDashboardData();

    } catch (err) {
        alert(err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Save Changes";
    }
}

function handleLogout() {
    sessionStorage.clear();
    localStorage.removeItem("clariqToken");
    localStorage.removeItem("clariqUser");
    localStorage.removeItem("clariqStudentId");
    window.location.href = "login.html";
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
