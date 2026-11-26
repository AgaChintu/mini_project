/* ==============================================================================
   CLARIQ — TEACHER / FACULTY DASHBOARD SCRIPT
   Dynamically integrates with FastAPI backend & Supabase PostgreSQL
   Features:
   - Subject-wise dynamic doubt management
   - AI semantic clustering & summaries
   - Human-in-the-loop answer verification
   - Strict student identity protection
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

let currentTeacherData = null;
let currentActiveSubjectId = null;
let currentDoubtToAnswer = null;

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

function checkTeacherAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = "../student-pages/login.html";
        return false;
    }
    return true;
}

// ==========================================
// INITIAL LOAD
// ==========================================

document.addEventListener("DOMContentLoaded", async () => {
    if (!checkTeacherAuth()) return;
    await loadTeacherDashboard();
    if (window.lucide) lucide.createIcons();
});

// ==========================================
// 1. LOAD DASHBOARD DATA
// ==========================================

async function loadTeacherDashboard() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/teacher/dashboard`, {
            headers: authHeaders()
        });

        if (response.status === 401 || response.status === 403) {
            handleLogout();
            return;
        }

        const data = await response.json();
        currentTeacherData = data;

        // Welcome Header & Profile
        const p = data.profile;
        const welcomeEl = document.getElementById("teacherGreeting");
        if (welcomeEl) {
            welcomeEl.textContent = `Welcome back, ${p.full_name}!`;
        }

        const subtitleEl = document.getElementById("teacherSubtitle");
        if (subtitleEl) {
            subtitleEl.textContent = `${p.designation} • ${p.department} • Faculty ID: ${p.college_id}`;
        }

        // Navigation profile
        const navName = document.getElementById("tNavName");
        const navAvatar = document.getElementById("tNavAvatar");
        if (navName) navName.textContent = p.full_name;
        if (navAvatar) navAvatar.textContent = p.full_name.charAt(0).toUpperCase();

        // Statistics
        const s = data.statistics;
        document.getElementById("statAssignedSubjects").textContent = s.assigned_subjects_count;
        document.getElementById("statTotalDoubts").textContent = s.total_doubts;
        document.getElementById("statPendingDoubts").textContent = s.pending_doubts;
        document.getElementById("statResolvedDoubts").textContent = s.resolved_doubts;

        // Render Assigned Subjects
        renderTeacherSubjects(data.assigned_subjects);

        // Auto-select first subject if available
        if (data.assigned_subjects && data.assigned_subjects.length > 0 && !currentActiveSubjectId) {
            selectSubjectForManagement(data.assigned_subjects[0].id);
        }

    } catch (err) {
        console.error("Failed to load teacher dashboard:", err);
    }
}

// ==========================================
// 2. RENDER ASSIGNED SUBJECTS
// ==========================================

function renderTeacherSubjects(subjects) {
    const container = document.getElementById("teacherSubjectsContainer");
    if (!container) return;

    if (!subjects || subjects.length === 0) {
        container.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 40px; background: white; border-radius: 16px; color: #64748B;">
                <i data-lucide="book-open" style="width: 36px; height: 36px; margin-bottom: 8px; color: #94A3B8;"></i>
                <p style="font-size: 15px; font-weight: 600; color: #334155;">No subjects currently assigned</p>
                <p style="font-size: 13px;">Contact the academic administrator to assign course sections to your faculty profile.</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = subjects.map(s => {
        const isActive = currentActiveSubjectId === s.id;
        const sectionsStr = s.sections && s.sections.length > 0 ? s.sections.join(", ") : "All Sections";

        return `
            <div class="t-subject-card ${isActive ? 'active' : ''}" onclick="selectSubjectForManagement(${s.id})">
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="font-size: 11px; font-weight: 700; background: #EEF2FF; color: #4965E8; padding: 3px 8px; border-radius: 6px;">
                            ${escapeHTML(s.code)}
                        </span>
                        ${s.pending_doubts > 0 ? `
                            <span style="font-size: 11px; font-weight: 700; background: #FEF3C7; color: #D97706; padding: 2px 8px; border-radius: 12px;">
                                ${s.pending_doubts} pending
                            </span>
                        ` : `
                            <span style="font-size: 11px; font-weight: 700; background: #DCFCE7; color: #166534; padding: 2px 8px; border-radius: 12px;">
                                all verified
                            </span>
                        `}
                    </div>
                    <h3 style="font-size: 17px; font-weight: 700; color: #1E293B; margin: 0 0 6px;">
                        ${escapeHTML(s.name)}
                    </h3>
                    <p style="font-size: 12px; color: #64748B; margin: 0 0 16px;">
                        Sections: <strong>${escapeHTML(sectionsStr)}</strong>
                    </p>
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #F1F5F9; padding-top: 12px; font-size: 12px; color: #475569;">
                    <span>Total Doubts: <strong>${s.total_doubts}</strong></span>
                    <span style="color: #4965E8; font-weight: 600; display: flex; align-items: center; gap: 4px;">
                        Manage <i data-lucide="chevron-right" style="width: 14px; height: 14px;"></i>
                    </span>
                </div>
            </div>
        `;
    }).join("");

    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 3. SELECT SUBJECT & LOAD CLUSTERED DOUBTS
// ==========================================

async function selectSubjectForManagement(subjectId) {
    currentActiveSubjectId = subjectId;

    // Highlight card
    if (currentTeacherData && currentTeacherData.assigned_subjects) {
        renderTeacherSubjects(currentTeacherData.assigned_subjects);
    }

    const sectionEl = document.getElementById("subjectDetailsSection");
    if (sectionEl) sectionEl.style.display = "block";

    const clustersBox = document.getElementById("clustersContainer");
    if (clustersBox) {
        clustersBox.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #64748B;">
                Loading subject doubts and computing AI clusters...
            </div>
        `;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/teacher/subjects/${subjectId}/doubts`, {
            headers: authHeaders()
        });

        if (!response.ok) throw new Error("Failed to load subject doubts.");

        const result = await response.json();

        // Update active banner
        document.getElementById("activeSubjectTitle").textContent = `${result.subject.name} — Doubt Management`;
        document.getElementById("activeSubjectCode").textContent = result.subject.code;
        document.getElementById("aiSubjectOverview").textContent = result.ai_overview;

        renderClusters(result.clusters, result.subject);

    } catch (err) {
        console.error("Error loading subject doubts:", err);
        if (clustersBox) {
            clustersBox.innerHTML = `<div style="color: #DC2626; padding: 20px;">${escapeHTML(err.message)}</div>`;
        }
    }
}

// ==========================================
// 4. RENDER CLUSTERED DOUBTS
// ==========================================

function renderClusters(clusters, subject) {
    const container = document.getElementById("clustersContainer");
    if (!container) return;

    if (!clusters || clusters.length === 0) {
        container.innerHTML = `
            <div style="background: white; border-radius: 16px; border: 1px dashed #CBD5E1; padding: 40px; text-align: center; color: #64748B;">
                <i data-lucide="check-circle" style="width: 40px; height: 40px; color: #10B981; margin-bottom: 8px;"></i>
                <h4 style="font-size: 16px; font-weight: 700; color: #1E293B; margin: 0 0 4px;">No Pending Questions</h4>
                <p style="font-size: 13px; margin: 0;">Students in your classes have not submitted any doubts for this subject yet.</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = clusters.map(c => {
        const doubtsHtml = c.doubts.map(d => {
            const isResolved = d.is_resolved;
            return `
                <div class="doubt-item">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 6px;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                                <span style="font-size: 11px; background: #E2E8F0; color: #334155; padding: 2px 6px; border-radius: 4px; font-weight: 600;">
                                    ID: ${escapeHTML(d.doubt_code)}
                                </span>
                                <span style="font-size: 11px; color: #059669; font-weight: 600;">
                                    🛡️ Anonymous Student
                                </span>
                            </div>
                            <h5 style="font-size: 15px; font-weight: 600; color: #1E293B; margin: 0 0 4px;">
                                ${escapeHTML(d.title)}
                            </h5>
                            <p style="font-size: 13px; color: #475569; margin: 0; line-height: 1.5;">
                                ${escapeHTML(d.description)}
                            </p>
                            ${d.attachments && d.attachments.length > 0 ? `
                                <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
                                    <span style="font-size: 11px; font-weight: 600; color: #64748B;">Student Attachments:</span>
                                    ${d.attachments.map(att => {
                                        const icon = att.mime_type && att.mime_type.startsWith("image/") ? "🖼️" : "📄";
                                        const sizeKB = att.file_size ? ` (${Math.max(1, Math.round(att.file_size / 1024))} KB)` : "";
                                        return `<button type="button" onclick='openProtectedAttachment("${API_BASE_URL}/api/teacher/doubts/${d.id}/attachments/${att.id}", ${JSON.stringify(att.original_filename)})' style="display:inline-flex; align-items:center; gap:5px; background:#EEF2FF; color:#3730A3; border:1px solid #C7D2FE; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer;">${icon} ${escapeHTML(att.original_filename)}${sizeKB}</button>`;
                                    }).join("")}
                                </div>
                            ` : ''}
                        </div>

                        <div>
                            ${isResolved ? `
                                <button class="btn-answer resolved">
                                    <i data-lucide="check-circle-2" style="width: 14px; height: 14px;"></i>
                                    <span>Verified</span>
                                </button>
                            ` : `
                                <button class="btn-answer" onclick='openAnswerModal(${JSON.stringify(d).replace(/'/g, "&#39;")}, ${JSON.stringify(subject).replace(/'/g, "&#39;")})'>
                                    <i data-lucide="edit-3" style="width: 14px; height: 14px;"></i>
                                    <span>Verify & Answer</span>
                                </button>
                            `}
                        </div>
                    </div>

                    ${d.answers && d.answers.length > 0 ? `
                        <div style="background: white; border-left: 3px solid #10B981; border-radius: 0 8px 8px 0; padding: 10px 14px; margin-top: 10px; font-size: 13px;">
                            <strong style="color: #059669;">Verified Answer:</strong>
                            <p style="margin: 2px 0 0; color: #1E293B;">${escapeHTML(d.answers[0].answer_text)}</p>
                            ${d.answers[0].answer_attachment_name ? `
                                <div style="margin-top: 8px;">
                                    <button type="button" onclick='openProtectedAttachment("${API_BASE_URL}/api/teacher/answers/${d.answers[0].id}/solution", ${JSON.stringify(d.answers[0].answer_attachment_name)})' style="display:inline-flex; align-items:center; gap:5px; background:#ECFDF5; color:#047857; border:1px solid #A7F3D0; padding:4px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer;">📎 Solution: ${escapeHTML(d.answers[0].answer_attachment_name)}</button>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join("");

        return `
            <div class="cluster-card">
                <div class="cluster-header">
                    <div>
                        <h4 class="cluster-title">${escapeHTML(c.cluster_title)}</h4>
                        <p style="font-size: 13px; color: #64748B; margin: 0 0 6px;">
                            ${escapeHTML(c.description)}
                        </p>
                        <div>
                            ${c.keywords.map(k => `<span class="keyword-chip">${escapeHTML(k)}</span>`).join("")}
                        </div>
                    </div>
                    <div class="cluster-student-badge">
                        <i data-lucide="users" style="width: 14px; height: 14px;"></i>
                        <span>${c.student_count} student${c.student_count !== 1 ? 's' : ''} asked similar doubts</span>
                    </div>
                </div>

                <div style="margin-top: 14px;">
                    ${doubtsHtml}
                </div>
            </div>
        `;
    }).join("");

    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 5. HUMAN-IN-THE-LOOP ANSWER VERIFICATION
// ==========================================

function openAnswerModal(doubt, subject) {
    currentDoubtToAnswer = doubt;
    const modal = document.getElementById("answerModal");
    if (!modal) return;

    document.getElementById("modalDoubtSubject").textContent = subject.name || "Subject";
    document.getElementById("modalDoubtTitle").textContent = doubt.title;
    document.getElementById("modalDoubtQuestion").textContent = doubt.description || doubt.question;
    document.getElementById("modalAiSummary").textContent = doubt.ai_summary || doubt.title;

    document.getElementById("answerText").value = "";
    document.getElementById("resourceLink").value = "";
    document.getElementById("resolveClusterCheck").checked = true;

    // Reset file input and preview
    const fileInput = document.getElementById("solutionFileInput");
    if (fileInput) fileInput.value = "";
    const preview = document.getElementById("solutionFilePreview");
    if (preview) preview.textContent = "";

    // Show student attachments if present
    renderModalStudentAttachments(doubt);

    modal.classList.add("active");
}

function renderModalStudentAttachments(doubt) {
    // Try to find or create an attachment preview area inside the modal
    let attBox = document.getElementById("modalStudentAttachments");
    if (!attBox) return;

    if (!doubt.attachments || doubt.attachments.length === 0) {
        attBox.innerHTML = '<span style="font-size:12px; color:#94A3B8;">No files attached by student.</span>';
        return;
    }

    attBox.innerHTML = `<div style="font-size:12px; font-weight:600; color:#475569; margin-bottom:4px;">Student Attached Files:</div>` +
        doubt.attachments.map(att => {
            const icon = att.mime_type && att.mime_type.startsWith("image/") ? "🖼️" : "📄";
            return `<button type="button"
                onclick='openProtectedAttachment("${API_BASE_URL}/api/teacher/doubts/${doubt.id}/attachments/${att.id}", ${JSON.stringify(att.original_filename)})'
                style="display:inline-flex; align-items:center; gap:5px; background:#EEF2FF; color:#3730A3; border:1px solid #C7D2FE; padding:5px 10px; border-radius:6px; font-size:12px; font-weight:600; cursor:pointer; margin:3px 6px 3px 0;">
                ${icon} ${escapeHTML(att.original_filename)}
            </button>`;
        }).join("");
}

async function openProtectedAttachment(url, filename) {
    try {
        const res = await fetch(url, {
            headers: { "Authorization": `Bearer ${getAuthToken()}` }
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || "Could not load attachment.");
        }
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const win = window.open(blobUrl, "_blank");
        if (!win) {
            const a = document.createElement("a");
            a.href = blobUrl;
            a.download = filename || "attachment";
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (err) {
        alert(err.message || "Failed to open attachment.");
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const solInput = document.getElementById("solutionFileInput");
    const solPreview = document.getElementById("solutionFilePreview");
    if (solInput && solPreview) {
        solInput.addEventListener("change", () => {
            const file = solInput.files && solInput.files[0];
            if (!file) {
                solPreview.textContent = "";
                return;
            }
            const allowed = ["image/png", "image/jpeg", "application/pdf"];
            if (!allowed.includes(file.type)) {
                alert(`"${file.name}" is not supported. Please attach a PNG, JPG, or PDF file.`);
                solInput.value = "";
                solPreview.textContent = "";
                return;
            }
            if (file.size > 10 * 1024 * 1024) {
                alert(`"${file.name}" exceeds the 10 MB limit.`);
                solInput.value = "";
                solPreview.textContent = "";
                return;
            }
            const sizeKB = Math.max(1, Math.round(file.size / 1024));
            solPreview.innerHTML = `Selected: <strong>${escapeHTML(file.name)}</strong> (${sizeKB} KB)`;
        });
    }
});

function closeAnswerModal() {
    const modal = document.getElementById("answerModal");
    if (modal) modal.classList.remove("active");
    currentDoubtToAnswer = null;
}

async function handlePublishAnswer(e) {
    e.preventDefault();
    if (!currentDoubtToAnswer) return;

    const btn = document.getElementById("btnPublishAnswer");
    btn.disabled = true;
    btn.textContent = "Publishing Verified Answer...";

    try {
        const answerText = document.getElementById("answerText").value.trim();
        const resourceUrl = document.getElementById("resourceLink").value.trim();
        const resolveCluster = document.getElementById("resolveClusterCheck").checked;
        const solutionFileEl = document.getElementById("solutionFileInput");
        const solutionFile = solutionFileEl && solutionFileEl.files && solutionFileEl.files[0] ? solutionFileEl.files[0] : null;

        // Build FormData so we can optionally attach a solution file
        const fd = new FormData();
        fd.append("answer_text", answerText);
        if (resourceUrl) fd.append("resource_url", resourceUrl);
        fd.append("resolve_cluster", resolveCluster ? "true" : "false");
        if (solutionFile) fd.append("solution_file", solutionFile);

        const token = getAuthToken();
        const response = await fetch(`${API_BASE_URL}/api/teacher/doubts/${currentDoubtToAnswer.id}/answer`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`
                // No Content-Type header: browser sets multipart boundary
            },
            body: fd
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Failed to publish answer.");
        }

        const fileMsg = solutionFile ? ` Solution file "${solutionFile.name}" attached.` : "";
        alert(`Verified answer published!${fileMsg} ${data.message || ''}`);
        closeAnswerModal();

        // Refresh live subject doubts and dashboard counts
        await loadTeacherDashboard();
        if (currentActiveSubjectId) {
            await selectSubjectForManagement(currentActiveSubjectId);
        }

    } catch (err) {
        alert(err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="check-circle" style="width: 16px; height: 16px;"></i> <span>Publish Verified Answer</span>`;
        if (window.lucide) lucide.createIcons();
    }
}

// ==========================================
// 6. PROFILE MODAL & LOGOUT
// ==========================================

function openTeacherProfileModal() {
    const modal = document.getElementById("teacherProfileModal");
    if (!modal || !currentTeacherData) return;

    const p = currentTeacherData.profile;
    document.getElementById("tProfileName").textContent = p.full_name;
    document.getElementById("tProfileId").textContent = `ID: ${p.college_id}`;
    document.getElementById("tProfileDept").textContent = p.department;
    document.getElementById("tProfileDesig").textContent = p.designation;
    document.getElementById("tProfileAvatar").textContent = p.full_name.charAt(0).toUpperCase();

    document.getElementById("tEditName").value = p.full_name;
    document.getElementById("tEditEmail").value = p.email || "";
    document.getElementById("tEditDesig").value = p.designation || "";

    modal.classList.add("active");
}

function closeTeacherProfileModal() {
    const modal = document.getElementById("teacherProfileModal");
    if (modal) modal.classList.remove("active");
}

async function handleTeacherProfileUpdate(e) {
    e.preventDefault();
    try {
        const res = await fetch(`${API_BASE_URL}/api/teacher/profile`, {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify({
                full_name: document.getElementById("tEditName").value.trim(),
                email: document.getElementById("tEditEmail").value.trim(),
                designation: document.getElementById("tEditDesig").value.trim()
            })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Update failed.");

        alert("Profile updated successfully!");
        closeTeacherProfileModal();
        await loadTeacherDashboard();
    } catch (err) {
        alert(err.message);
    }
}

function handleLogout() {
    sessionStorage.clear();
    localStorage.removeItem("clariqToken");
    localStorage.removeItem("clariqUser");
    localStorage.removeItem("clariqTeacherId");
    window.location.href = "../student-pages/login.html";
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
