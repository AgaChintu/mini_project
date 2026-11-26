/* ==============================================================================
   CLARIQ — ADMIN DASHBOARD v4
   Full faculty & subject management with live database sync
   ============================================================================== */

const API = "http://127.0.0.1:8000";

// ─── STATE ────────────────────────────────────────────────────────────────────
let currentTab = "overview";
let allTeachers = [];
let allSubjects = [];
let allStudents = [];
let filteredTeachers = [];
let filteredSubjects = [];
let filteredStudents = [];
let activeSubjectsView = "cards";
let activeFacultyView = "list";
let mgmtActiveSubjectId = null;
let editingSubjectId = null;
let pendingStudentSemesterChange = null;

// ─── AUTH ─────────────────────────────────────────────────────────────────────
function getToken() {
    return sessionStorage.getItem("clariqAdminToken") || localStorage.getItem("clariqAdminToken");
}

function authHeaders() {
    return { "Content-Type": "application/json", "Authorization": `Bearer ${getToken()}` };
}

function checkAuth() {
    if (!getToken()) { window.location.href = "login.html"; return false; }
    return true;
}

function handleLogout() {
    ["clariqAdminToken", "clariqAdminUser"].forEach(k => {
        sessionStorage.removeItem(k); localStorage.removeItem(k);
    });
    window.location.href = "login.html";
}

// ─── NAVIGATION & ROUTE DETECTION ─────────────────────────────────────────────
function getActiveTabFromUrl() {
    // 1. Check URL hash (#overview, #faculty, #subjects, #students, #routing)
    const hash = (window.location.hash || "").replace("#", "").toLowerCase().trim();
    if (["overview", "faculty", "subjects", "students", "routing"].includes(hash)) {
        return hash;
    }
    // 2. Check query parameter (?tab=faculty)
    const params = new URLSearchParams(window.location.search);
    const tabParam = (params.get("tab") || "").toLowerCase().trim();
    if (["overview", "faculty", "subjects", "students", "routing"].includes(tabParam)) {
        return tabParam;
    }
    // 3. Check pathname (e.g. /faculty, /subjects, /students, /routing, /overview, faculty.html)
    const path = window.location.pathname.toLowerCase();
    if (path.includes("faculty")) return "faculty";
    if (path.includes("students") || path.includes("student")) return "students";
    if (path.includes("subjects") || path.includes("subject")) return "subjects";
    if (path.includes("routing")) return "routing";
    if (path.includes("overview")) return "overview";

    return "overview";
}

// ─── INIT ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    if (!checkAuth()) return;

    // Detect active tab from URL / history and activate immediately
    const initialTab = getActiveTabFromUrl();
    switchTab(initialTab, false);

    await Promise.all([loadAdminProfile(), loadOverviewStats()]);
    if (window.lucide) lucide.createIcons();
});

// History back/forward navigation support
window.addEventListener("popstate", () => {
    const tab = getActiveTabFromUrl();
    switchTab(tab, false);
});

// URL hash change navigation support
window.addEventListener("hashchange", () => {
    const tab = getActiveTabFromUrl();
    switchTab(tab, false);
});

async function loadAdminProfile() {
    try {
        const res = await fetch(`${API}/api/admin/me`, { headers: authHeaders() });
        if (res.status === 401) { handleLogout(); return; }
        const { admin } = await res.json();
        const el = id => document.getElementById(id);
        if (el("sidebarAdminName")) el("sidebarAdminName").textContent = admin.full_name || admin.username;
        if (el("adminBadgeEmail")) el("adminBadgeEmail").textContent = admin.email || "Super Admin";
    } catch (e) { console.warn("Profile load failed:", e); }
}

async function loadOverviewStats() {
    try {
        const res = await fetch(`${API}/api/admin/dashboard`, { headers: authHeaders() });
        if (!res.ok) return;
        const { metrics, recent_doubts } = await res.json();
        const set = (elId, val) => { const el = document.getElementById(elId); if (el) el.textContent = val ?? "—"; };
        set("statStudents", metrics.total_students);
        set("statFaculty", metrics.total_teachers);
        set("statSubjects", metrics.total_subjects);
        set("statAssignments", metrics.active_faculty_assignments);
        set("statDoubts", metrics.total_doubts);
        set("statPending", metrics.pending_doubts);
        set("statResolved", metrics.resolved_doubts);

        // Render recent doubts
        const listEl = document.getElementById("recentDoubtsList");
        if (listEl && recent_doubts) {
            if (recent_doubts.length === 0) {
                listEl.innerHTML = `<div class="empty-state" style="padding:16px 0;"><p>No recent doubts.</p></div>`;
            } else {
                listEl.innerHTML = recent_doubts.slice(0, 8).map(d => `
                    <div class="recent-doubt-row">
                        <div class="rd-dot ${d.status === 'resolved' ? 'resolved' : 'pending'}"></div>
                        <div>
                            <div class="rd-title">${esc(d.title)}</div>
                            <div class="rd-meta">${esc(d.subject_name)} · ${esc(d.assigned_teacher || 'Unassigned')} · <span class="badge ${d.status === 'resolved' ? 'badge-green' : 'badge-amber'}">${d.status}</span></div>
                        </div>
                    </div>
                `).join("");
            }
        }
    } catch (e) { console.warn("Stats load failed:", e); }
}

// ─── NAVIGATION ───────────────────────────────────────────────────────────────
function switchTab(tab, updateHistory = true) {
    if (!["overview", "faculty", "subjects", "students", "routing"].includes(tab)) {
        tab = "overview";
    }
    currentTab = tab;

    // Reset active class on all panels and navigation links
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".nav-item a").forEach(a => a.classList.remove("active"));

    // Activate selected panel and navigation link
    const panelEl = document.getElementById(`panel-${tab}`);
    if (panelEl) panelEl.classList.add("active");
    const navEl = document.getElementById(`nav-${tab}`);
    if (navEl) navEl.classList.add("active");

    // Update topbar headers & document title
    const titles = {
        overview: ["Institutional Console", "Administrative control for ClariQ platform", "Dashboard | ClariQ Admin"],
        faculty: ["Faculty Management", "Manage teacher accounts and subject assignments", "Faculty Management | ClariQ Admin"],
        subjects: ["Subjects & Faculty Management", "Manage curriculum, faculty assignments and academic responsibilities", "Subjects & Faculty | ClariQ Admin"],
        students: ["Student Academic Management", "Assign and manage student semesters and academic progression", "Student Academic | ClariQ Admin"],
        routing: ["Doubt Routing", "Review and reassign pending student doubts", "Doubt Routing | ClariQ Admin"],
    };
    const t = titles[tab] || ["Admin Console", "", "Admin Console | ClariQ"];
    const h1 = document.getElementById("pageTitle");
    const sub = document.getElementById("pageSubtitle");
    if (h1) h1.textContent = t[0];
    if (sub) sub.textContent = t[1];
    document.title = t[2];

    // Synchronize browser history / URL hash
    if (updateHistory) {
        const targetHash = `#${tab}`;
        if (window.location.hash !== targetHash) {
            history.pushState({ tab }, "", targetHash);
        }
    }

    refreshCurrentTab();
    if (window.lucide) lucide.createIcons();
}

function refreshCurrentTab() {
    loadOverviewStats();
    if (currentTab === "faculty") loadFaculty();
    else if (currentTab === "subjects") loadSubjects();
    else if (currentTab === "students") loadAdminStudents();
    else if (currentTab === "routing") loadRoutingDoubts();
}

// ─── FACULTY MANAGEMENT ───────────────────────────────────────────────────────
async function loadFaculty() {
    try {
        const [dirRes, ovRes] = await Promise.all([
            fetch(`${API}/api/admin/teachers`, { headers: authHeaders() }),
            fetch(`${API}/api/admin/faculty-overview`, { headers: authHeaders() }),
        ]);
        const dirData = await dirRes.json();
        allTeachers = dirData.data || [];
        filteredTeachers = [...allTeachers];
        renderFacultyTable(filteredTeachers);

        if (ovRes.ok) {
            const ovData = await ovRes.json();
            renderFacultyOverview(ovData.data || []);
        }
    } catch (e) {
        console.error("Faculty load error:", e);
        document.getElementById("facultyTableBody").innerHTML = errRow(8, e.message);
    }
    if (window.lucide) lucide.createIcons();
}

function setFacultyView(view) {
    activeFacultyView = view;
    document.getElementById("facultyDirectoryView").style.display = view === "list" ? "" : "none";
    document.getElementById("facultyOverviewView").style.display = view === "overview" ? "" : "none";
    document.getElementById("btnFaculty-list").classList.toggle("active", view === "list");
    document.getElementById("btnFaculty-overview").classList.toggle("active", view === "overview");
    if (view === "overview" && allTeachers.length === 0) loadFaculty();
}

function renderFacultyTable(teachers) {
    const tbody = document.getElementById("facultyTableBody");
    if (!tbody) return;
    if (teachers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8">${emptyState("No faculty records found", "Try a different search or filter.")}</td></tr>`;
        return;
    }
    tbody.innerHTML = teachers.map(t => {
        const subs = t.assigned_subjects || [];
        let subjectsHtml = "";
        if (subs.length === 0) {
            subjectsHtml = `<span class="badge badge-gray" style="color:#64748B;">Not Assigned</span>`;
        } else {
            subjectsHtml = `<div style="display:flex; flex-wrap:wrap; gap:4px; max-width:320px;">` +
                subs.map(s => {
                    const sName = esc(s.name || s.full_name || s.code);
                    const isPrim = !!s.is_primary;
                    return `<span class="badge ${isPrim ? 'badge-blue' : 'badge-gray'}" style="font-size:11px;" title="${isPrim ? 'Primary Faculty' : 'Additional Faculty'}: ${sName}">${sName}</span>`;
                }).join("") +
            `</div>`;
        }

        return `
            <tr>
                <td><span class="badge badge-blue">${esc(t.teacher_code)}</span></td>
                <td><strong style="color:var(--text);">${esc(t.full_name)}</strong></td>
                <td style="color:var(--text-muted); font-size:12px;">${esc(t.email || "—")}</td>
                <td style="font-size:12px;">${esc(t.department || "—")}</td>
                <td style="font-size:12px;">${esc(t.designation || "—")}</td>
                <td>${subjectsHtml}</td>
                <td>
                    <span class="badge ${t.is_active ? 'badge-green' : 'badge-red'}">${t.is_active ? 'Active' : 'Inactive'}</span>
                </td>
                <td>
                    <div style="display:flex; gap:6px;">
                        <button class="btn btn-sm btn-secondary" onclick="openFacultyProfile(${t.id})" title="View Profile">
                            <i data-lucide="eye"></i>
                        </button>
                        <button class="btn btn-sm ${t.is_active ? 'btn-danger' : 'btn-success'}"
                            onclick="toggleFacultyStatus(${t.id}, ${t.is_active})"
                            title="${t.is_active ? 'Deactivate' : 'Activate'}">
                            ${t.is_active ? '<i data-lucide="user-x"></i>' : '<i data-lucide="user-check"></i>'}
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
    if (window.lucide) lucide.createIcons();
}

function renderFacultyOverview(teachers) {
    const tbody = document.getElementById("facultyOverviewBody");
    if (!tbody) return;
    if (teachers.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7">${emptyState("No faculty data", "No faculty assignments found.")}</td></tr>`;
        return;
    }
    tbody.innerHTML = teachers.map(t => {
        const primaryChips = (t.primary_subjects || []).map(s =>
            `<span class="faculty-subject-chip" title="${esc(s.name || s.full_name)}">${esc(s.name || s.full_name)}</span>`
        ).join("");
        const addlChips = (t.additional_subjects || []).map(s =>
            `<span class="faculty-subject-chip chip-additional" title="${esc(s.name || s.full_name)}">${esc(s.name || s.full_name)}</span>`
        ).join("");

        const totalUnique = t.total_subjects ?? t.total_assigned ?? (
            new Set([
                ...(t.primary_subjects || []).map(s => s.id || s.name),
                ...(t.additional_subjects || []).map(s => s.id || s.name),
            ]).size
        );

        return `
            <tr>
                <td>
                    <div style="font-weight:600;">${esc(t.full_name)}</div>
                    <div style="font-size:11px; color:var(--text-muted);">${esc(t.teacher_code)}</div>
                </td>
                <td style="font-size:12px;">${esc(t.department || "—")}</td>
                <td style="font-size:12px;">${esc(t.designation || "—")}</td>
                <td><div class="faculty-subjects-chips">${primaryChips || '<span style="font-size:12px;color:var(--text-muted); font-style:italic;">None</span>'}</div></td>
                <td><div class="faculty-subjects-chips">${addlChips || '<span style="font-size:12px;color:var(--text-muted); font-style:italic;">None</span>'}</div></td>
                <td><span class="badge badge-blue">${totalUnique}</span></td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="openFacultyProfile(${t.id})">
                        <i data-lucide="eye"></i> Profile
                    </button>
                </td>
            </tr>
        `;
    }).join("");
    if (window.lucide) lucide.createIcons();
}

function filterFaculty() {
    const q = (document.getElementById("facultySearch")?.value || "").toLowerCase().trim();
    const dept = document.getElementById("facultyDeptFilter")?.value || "";
    const statusVal = document.getElementById("facultyStatusFilter")?.value || "";

    filteredTeachers = allTeachers.filter(t => {
        const matchQ = !q ||
            t.full_name?.toLowerCase().includes(q) ||
            t.teacher_code?.toLowerCase().includes(q) ||
            t.email?.toLowerCase().includes(q);
        const matchDept = !dept || (t.department || "").includes(dept);
        const matchStatus = statusVal === "" || String(t.is_active) === statusVal;
        return matchQ && matchDept && matchStatus;
    });
    renderFacultyTable(filteredTeachers);
}

async function toggleFacultyStatus(teacherId, currentStatus) {
    const action = currentStatus ? "deactivate" : "activate";
    if (!confirm(`Are you sure you want to ${action} this faculty account?`)) return;
    try {
        const res = await fetch(`${API}/api/admin/teachers/${teacherId}/status`, {
            method: "PATCH", headers: authHeaders(),
            body: JSON.stringify({ is_active: !currentStatus }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update status.");
        showToast(`Faculty ${action}d successfully.`, "success");
        await loadFaculty();
        await loadOverviewStats();
    } catch (e) { showToast(e.message, "error"); }
}

async function openFacultyProfile(teacherId) {
    openModal("modalFacultyProfile");
    document.getElementById("fpModalBody").innerHTML = `<div class="empty-state"><p>Loading...</p></div>`;

    try {
        const res = await fetch(`${API}/api/admin/teachers/${teacherId}`, { headers: authHeaders() });
        const { teacher } = await res.json();

        document.getElementById("fpModalName").textContent = teacher.full_name;
        document.getElementById("fpModalCode").textContent = teacher.teacher_code;

        const primarySubs = teacher.assigned_subjects?.filter(s => s.is_primary) || [];
        const addlSubs = teacher.assigned_subjects?.filter(s => !s.is_primary) || [];

        document.getElementById("fpModalBody").innerHTML = `
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:16px;">
                <div>
                    <div class="form-label">Email</div>
                    <div style="font-size:13px;">${esc(teacher.email || "—")}</div>
                </div>
                <div>
                    <div class="form-label">Department</div>
                    <div style="font-size:13px;">${esc(teacher.department || "—")}</div>
                </div>
                <div>
                    <div class="form-label">Designation</div>
                    <div style="font-size:13px;">${esc(teacher.designation || "—")}</div>
                </div>
                <div>
                    <div class="form-label">Status</div>
                    <div><span class="badge ${teacher.is_active ? 'badge-green' : 'badge-red'}">${teacher.is_active ? 'Active' : 'Inactive'}</span></div>
                </div>
            </div>
            ${teacher.profile_info ? `<div style="background:#F8FAFC; border-radius:8px; padding:12px; font-size:12px; color:#475569; margin-bottom:16px;">${esc(teacher.profile_info)}</div>` : ""}
            <div class="section-divider">Primary Subject Assignments (${primarySubs.length})</div>
            ${primarySubs.length === 0
                ? `<div style="font-size:12px; color:var(--text-muted); padding:8px 0;">No primary assignments yet.</div>`
                : primarySubs.map(s => `
                    <div class="assigned-item primary-item" style="margin-bottom:6px;">
                        <div class="assigned-item-info">
                            <div class="assigned-item-name">${esc(s.name)}</div>
                            <div class="assigned-item-meta">${esc(s.code || "")} · Primary Faculty</div>
                        </div>
                        <span class="badge badge-blue">Primary</span>
                    </div>`).join("")}
            <div class="section-divider" style="margin-top:14px;">Additional Subject Assignments (${addlSubs.length})</div>
            ${addlSubs.length === 0
                ? `<div style="font-size:12px; color:var(--text-muted); padding:8px 0;">No additional assignments yet.</div>`
                : addlSubs.map(s => `
                    <div class="assigned-item" style="margin-bottom:6px;">
                        <div class="assigned-item-info">
                            <div class="assigned-item-name">${esc(s.name)}</div>
                            <div class="assigned-item-meta">${esc(s.code || "")} · Additional Faculty</div>
                        </div>
                        <span class="badge badge-gray">Additional</span>
                    </div>`).join("")}
        `;
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        document.getElementById("fpModalBody").innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
}

// ─── SUBJECT MANAGEMENT ───────────────────────────────────────────────────────
async function loadSubjects() {
    try {
        const [subRes, summRes] = await Promise.all([
            fetch(`${API}/api/admin/subjects`, { headers: authHeaders() }),
            fetch(`${API}/api/admin/subjects/semester-summary`, { headers: authHeaders() })
        ]);
        if (!subRes.ok) throw new Error("Could not load subjects.");
        const { data } = await subRes.json();
        allSubjects = data || [];
        filteredSubjects = [...allSubjects];

        let summaryData = null;
        if (summRes.ok) {
            summaryData = await summRes.json();
        }
        updateSubjectSummary(allSubjects, summaryData);
        renderSubjectsView();
    } catch (e) {
        console.error("Subject load error:", e);
        document.getElementById("subjectsGrid").innerHTML = `<div style="grid-column:1/-1;">${emptyState("Error loading subjects", e.message)}</div>`;
    }
    if (window.lucide) lucide.createIcons();
}

function updateSubjectSummary(subjects, summaryData) {
    const total = subjects.length;
    const assigned = subjects.filter(s => s.faculty_count > 0).length;
    const unassignedFaculty = total - assigned;
    const unassignedSem = subjects.filter(s => !s.semester_number).length;
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };

    set("subSummTotal", total);
    set("subSummAssigned", assigned);
    set("subSummUnassigned", unassignedFaculty);
    set("subSummUnassignedSem", unassignedSem);

    if (summaryData) {
        set("subSummSemestersCount", summaryData.total_semesters || "0");
        const chipsEl = document.getElementById("semesterBreakdownChips");
        if (chipsEl && summaryData.breakdown) {
            if (summaryData.breakdown.length === 0) {
                chipsEl.innerHTML = `<span style="color:var(--text-muted);">No active semester breakdown.</span>`;
            } else {
                chipsEl.innerHTML = summaryData.breakdown.map(b => `
                    <span class="badge badge-purple" style="font-weight:600; cursor:pointer;" onclick="filterBySpecificSemester(${b.semester_number})" title="Filter by Semester ${b.semester_number}">
                        Sem ${b.semester_number}: <strong>${b.subject_count}</strong>
                    </span>
                `).join("") + (summaryData.unassigned_subjects_count > 0 ? `
                    <span class="badge badge-amber" style="font-weight:600; cursor:pointer;" onclick="filterBySpecificSemester('unassigned')" title="Filter Unassigned">
                        Unassigned: <strong>${summaryData.unassigned_subjects_count}</strong>
                    </span>` : "");
            }
        }
    }
}

function filterBySpecificSemester(sem) {
    const semSelect = document.getElementById("subjectSemesterFilter");
    if (semSelect) {
        semSelect.value = String(sem);
        filterSubjects();
    }
}

function setSubjectsView(view) {
    activeSubjectsView = view;
    document.getElementById("subjectsCardsView").style.display = view === "cards" ? "" : "none";
    document.getElementById("subjectsTableView").style.display = view === "table" ? "" : "none";
    document.getElementById("btnSubj-cards").classList.toggle("active", view === "cards");
    document.getElementById("btnSubj-table").classList.toggle("active", view === "table");
    renderSubjectsView();
}

function filterSubjects() {
    const q = (document.getElementById("subjectSearch")?.value || "").toLowerCase().trim();
    const dept = document.getElementById("subjectDeptFilter")?.value || "";
    const sem = document.getElementById("subjectSemesterFilter")?.value || "";
    const assign = document.getElementById("subjectAssignFilter")?.value || "";

    filteredSubjects = allSubjects.filter(s => {
        const facultyNames = (s.assigned_faculty || []).map(f => f.full_name || f.name || "").join(" ").toLowerCase();
        const matchQ = !q ||
            s.name?.toLowerCase().includes(q) ||
            s.code?.toLowerCase().includes(q) ||
            facultyNames.includes(q);
        const matchDept = !dept || (s.department || "").includes(dept);
        const matchSem = !sem ||
            (sem === "unassigned" && !s.semester_number) ||
            (s.semester_number === parseInt(sem, 10));
        const matchAssign = !assign ||
            (assign === "assigned" && s.faculty_count > 0) ||
            (assign === "unassigned" && s.faculty_count === 0);
        return matchQ && matchDept && matchSem && matchAssign;
    });
    renderSubjectsView();
}

function renderSubjectsView() {
    if (activeSubjectsView === "cards") renderSubjectsCards(filteredSubjects);
    else renderSubjectsTable(filteredSubjects);
    if (window.lucide) lucide.createIcons();
}

function renderSubjectsCards(subjects) {
    const grid = document.getElementById("subjectsGrid");
    if (!grid) return;
    if (subjects.length === 0) {
        grid.innerHTML = `<div style="grid-column:1/-1;">${emptyState("No subjects found", "Try a different filter or add a new subject.")}</div>`;
        return;
    }
    grid.innerHTML = subjects.map(s => {
        const primaryT = s.primary_teacher;
        const addlFaculty = (s.assigned_faculty || []).filter(f => !f.is_primary);
        const isActive = s.is_active !== false;

        let facultySection = "";
        if (primaryT) {
            facultySection += `
                <div class="faculty-chip primary-chip">
                    <div>
                        <div class="faculty-chip-name">${esc(primaryT.full_name || primaryT.name)}</div>
                        <div class="faculty-chip-dept">${esc(primaryT.designation || primaryT.teacher_code || "")}</div>
                    </div>
                    <span class="badge badge-blue">Primary</span>
                </div>`;
        }
        if (addlFaculty.length > 0) {
            facultySection += addlFaculty.map(f => `
                <div class="faculty-chip">
                    <div>
                        <div class="faculty-chip-name">${esc(f.full_name || f.name)}</div>
                        <div class="faculty-chip-dept">${esc(f.designation || f.teacher_code || "")}</div>
                    </div>
                    <span class="badge badge-gray">Additional</span>
                </div>`).join("");
        }
        if (!primaryT && addlFaculty.length === 0) {
            facultySection = `<div style="font-size:12px; color:var(--text-muted); font-style:italic; padding:8px 0;">Faculty Not Assigned</div>`;
        }

        const semBadge = s.semester_number
            ? `<span class="badge badge-purple">Semester ${s.semester_number}</span>`
            : `<span class="badge badge-amber">Unassigned Sem</span>`;

        return `
            <div class="subject-card">
                <div class="subject-card-header">
                    <div>
                        <span class="badge badge-blue">${esc(s.code)}</span>
                        ${semBadge}
                        ${!isActive ? '<span class="badge badge-red" style="margin-left:4px;">Archived</span>' : ''}
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:11px; font-weight:700; color:var(--primary);">${s.semester_number ? `Semester ${s.semester_number}` : (s.semester_label || s.semester || "Unassigned")}</div>
                        <div style="font-size:11px; color:var(--text-muted);">${esc(s.department || "")}</div>
                    </div>
                </div>
                <div class="subject-card-name">${esc(s.name)}</div>
                <div>
                    <div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:6px;">
                        Assigned Faculty (${s.faculty_count || 0})
                    </div>
                    <div style="display:flex; flex-direction:column; gap:5px;">${facultySection}</div>
                </div>
                <div class="subject-actions">
                    <button class="btn btn-sm btn-secondary" onclick="openManageFacultyModal(${s.id})" title="Manage Faculty">
                        <i data-lucide="user-cog"></i> Faculty
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="openEditSubjectSemesterModal(${s.id})" title="Change Semester">
                        <i data-lucide="calendar"></i> Sem
                    </button>
                    <button class="btn btn-sm btn-secondary" onclick="openEditSubjectModal(${s.id})" title="Edit Subject">
                        <i data-lucide="pencil"></i> Edit
                    </button>
                    ${isActive ? `
                    <button class="btn btn-sm btn-danger" onclick="confirmArchiveSubject(${s.id}, '${esc(s.name).replace(/'/g,"\\'")}')">
                        <i data-lucide="archive"></i>
                    </button>` : `
                    <button class="btn btn-sm btn-success" onclick="restoreSubject(${s.id})">
                        <i data-lucide="archive-restore"></i>
                    </button>`}
                </div>
            </div>
        `;
    }).join("");
    if (window.lucide) lucide.createIcons();
}

function renderSubjectsTable(subjects) {
    const tbody = document.getElementById("subjectsTableBody");
    if (!tbody) return;
    if (subjects.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9">${emptyState("No subjects found", "")}</td></tr>`;
        return;
    }
    tbody.innerHTML = subjects.map(s => {
        const primaryT = s.primary_teacher;
        const addlFaculty = (s.assigned_faculty || []).filter(f => !f.is_primary);
        const totalFaculty = (primaryT ? 1 : 0) + addlFaculty.length;
        const isActive = s.is_active !== false;
        const semYear = [s.semester_number ? `Semester ${s.semester_number}` : (s.semester_label || s.semester), s.academic_year_label].filter(Boolean).join(" · ") || "—";

        const addlFacultyHtml = addlFaculty.length > 0
            ? `<div style="display:flex; flex-direction:column; gap:2px;">` +
              addlFaculty.map(f =>
                  `<span style="font-size:11px; color:var(--text);">${esc(f.full_name || f.name)} <span style="color:var(--text-muted); font-size:10px;">(${esc(f.teacher_code || f.designation || "Faculty")})</span></span>`
              ).join("") + `</div>`
            : `<span style="color:var(--text-muted); font-size:11px; font-style:italic;">None</span>`;

        return `
            <tr>
                <td><span class="badge badge-blue">${esc(s.code)}</span></td>
                <td><strong style="color:var(--text); font-size:13px;">${esc(s.name)}</strong></td>
                <td style="font-size:12px;">${esc(s.department || "—")}</td>
                <td style="font-size:12px;">
                    <span class="badge ${s.semester_number ? 'badge-purple' : 'badge-amber'}">${s.semester_number ? `Sem ${s.semester_number}` : 'Unassigned'}</span>
                </td>
                <td>
                    ${primaryT
                        ? `<div>
                             <div style="font-weight:600;font-size:12px; color:var(--primary);">${esc(primaryT.full_name || primaryT.name)}</div>
                             <div style="font-size:11px;color:var(--text-muted);">${esc(primaryT.teacher_code || "")}${primaryT.designation ? ' · ' + esc(primaryT.designation) : ''}</div>
                           </div>`
                        : `<span style="color:var(--text-muted);font-size:12px; font-style:italic;">Not Assigned</span>`}
                </td>
                <td>${addlFacultyHtml}</td>
                <td><span class="badge ${totalFaculty > 0 ? 'badge-blue' : 'badge-gray'}">${totalFaculty}</span></td>
                <td>
                    <span class="badge ${isActive ? 'badge-green' : 'badge-red'}">${isActive ? 'Active' : 'Archived'}</span>
                    ${totalFaculty === 0 ? '<div style="margin-top:2px;"><span class="badge badge-amber" style="font-size:10px;">Unassigned Faculty</span></div>' : ''}
                </td>
                <td>
                    <div style="display:flex;gap:4px;">
                        <button class="btn btn-xs btn-secondary" onclick="openManageFacultyModal(${s.id})" title="Manage Faculty">Faculty</button>
                        <button class="btn btn-xs btn-secondary" onclick="openEditSubjectSemesterModal(${s.id})" title="Change Semester">Sem</button>
                        <button class="btn btn-xs btn-secondary" onclick="openEditSubjectModal(${s.id})" title="Edit Subject">Edit</button>
                        ${isActive
                            ? `<button class="btn btn-xs btn-danger" onclick="confirmArchiveSubject(${s.id}, '${esc(s.name).replace(/'/g,"\\'")}')" title="Archive Subject">Archive</button>`
                            : `<button class="btn btn-xs btn-success" onclick="restoreSubject(${s.id})" title="Restore Subject">Restore</button>`}
                    </div>
                </td>
            </tr>
        `;
    }).join("");
    if (window.lucide) lucide.createIcons();
}

// ─── ADD / EDIT SUBJECT MODAL ─────────────────────────────────────────────────
async function openAddSubjectModal() {
    editingSubjectId = null;
    document.getElementById("addSubjectModalTitle").textContent = "Add New Subject";
    document.getElementById("addSubjectModalSub").textContent = "Create a new curriculum subject and optionally assign faculty";
    document.getElementById("subjFormSubmitLabel").textContent = "Create Subject";
    document.getElementById("editSubjectId").value = "";
    document.getElementById("addSubjectForm").reset();

    // Load teachers for dropdowns
    if (allTeachers.length === 0) {
        const res = await fetch(`${API}/api/admin/teachers`, { headers: authHeaders() });
        const { data } = await res.json();
        allTeachers = data || [];
    }
    populateSubjectFacultyDropdowns(allTeachers, null, []);
    openModal("modalAddSubject");
}

async function openEditSubjectModal(subjectId) {
    editingSubjectId = subjectId;
    document.getElementById("addSubjectModalTitle").textContent = "Edit Subject";
    document.getElementById("addSubjectModalSub").textContent = "Update subject details and faculty assignments";
    document.getElementById("subjFormSubmitLabel").textContent = "Save Changes";
    document.getElementById("editSubjectId").value = subjectId;

    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}`, { headers: authHeaders() });
        const { subject: s } = await res.json();

        document.getElementById("subjName").value = s.name || "";
        document.getElementById("subjCode").value = s.code || "";
        document.getElementById("subjDept").value = s.department || "Computer Science & Engineering";
        document.getElementById("subjType").value = s.subject_type || "theory";
        document.getElementById("subjSemester").value = s.semester_number ? String(s.semester_number) : "";
        document.getElementById("subjYear").value = s.academic_year_label || "";
        document.getElementById("subjDesc").value = s.description || "";

        if (allTeachers.length === 0) {
            const tRes = await fetch(`${API}/api/admin/teachers`, { headers: authHeaders() });
            const { data } = await tRes.json();
            allTeachers = data || [];
        }

        const primaryId = s.primary_teacher?.teacher_id || s.primary_teacher?.id || null;
        const addlIds = (s.assigned_faculty || []).filter(f => !f.is_primary).map(f => f.teacher_id || f.id);
        populateSubjectFacultyDropdowns(allTeachers, primaryId, addlIds);
        openModal("modalAddSubject");
    } catch (e) { showToast("Failed to load subject details: " + e.message, "error"); }
}

function populateSubjectFacultyDropdowns(teachers, selectedPrimaryId, selectedAddlIds) {
    const activeFaculty = teachers.filter(t => t.is_active);

    // Primary dropdown
    const primarySelect = document.getElementById("subjPrimaryFaculty");
    primarySelect.innerHTML = `<option value="">None — Assign later</option>` +
        activeFaculty.map(t => `
            <option value="${t.id}" ${t.id === selectedPrimaryId ? 'selected' : ''}>
                ${esc(t.full_name)} (${esc(t.teacher_code)}) — ${esc(t.department || "")}
            </option>`).join("");

    // Additional (checkboxes)
    const addlList = document.getElementById("additionalFacultyList");
    addlList.innerHTML = activeFaculty.map(t => `
        <div class="multi-select-item">
            <input type="checkbox" id="addl_${t.id}" value="${t.id}"
                ${selectedAddlIds.includes(t.id) ? 'checked' : ''}
                ${t.id === selectedPrimaryId ? 'disabled' : ''}>
            <label for="addl_${t.id}">
                <strong>${esc(t.full_name)}</strong>
                <span style="color:var(--text-muted); font-size:11px; margin-left:6px;">${esc(t.teacher_code)} — ${esc(t.department || "")}</span>
            </label>
        </div>
    `).join("");

    // Disable primary in additional when primary changes
    primarySelect.onchange = () => {
        const selId = parseInt(primarySelect.value) || null;
        addlList.querySelectorAll("input[type=checkbox]").forEach(cb => {
            cb.disabled = parseInt(cb.value) === selId;
            if (parseInt(cb.value) === selId) cb.checked = false;
        });
    };
}

async function handleSubjectFormSubmit(e) {
    e.preventDefault();
    const isEdit = !!editingSubjectId;
    const btn = document.getElementById("subjFormSubmitBtn");
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2"></i> ${isEdit ? 'Saving...' : 'Creating...'}`;
    if (window.lucide) lucide.createIcons();

    const primaryId = parseInt(document.getElementById("subjPrimaryFaculty").value) || null;
    const addlIds = [...document.querySelectorAll("#additionalFacultyList input[type=checkbox]:checked")]
        .map(cb => parseInt(cb.value)).filter(id => id !== primaryId);

    const semVal = document.getElementById("subjSemester").value;
    const semNum = semVal ? parseInt(semVal, 10) : null;

    const payload = {
        name: document.getElementById("subjName").value.trim(),
        code: document.getElementById("subjCode").value.trim(),
        department: document.getElementById("subjDept").value,
        subject_type: document.getElementById("subjType").value,
        semester_number: isNaN(semNum) ? null : semNum,
        semester_label: semNum ? `Semester ${semNum}` : null,
        academic_year_label: document.getElementById("subjYear").value,
        description: document.getElementById("subjDesc").value.trim() || null,
    };

    if (!isEdit) {
        payload.primary_teacher_id = primaryId;
        payload.additional_teacher_ids = addlIds;
    }

    try {
        const url = isEdit ? `${API}/api/admin/subjects/${editingSubjectId}` : `${API}/api/admin/subjects`;
        const method = isEdit ? "PUT" : "POST";
        const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(payload) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to save subject.");
        showToast(`Subject '${data.subject?.name || payload.name}' ${isEdit ? 'updated' : 'created'} successfully!`, "success");
        closeModal("modalAddSubject");
        await loadSubjects();
        await loadOverviewStats();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="${isEdit ? 'save' : 'plus'}"></i> <span id="subjFormSubmitLabel">${isEdit ? 'Save Changes' : 'Create Subject'}</span>`;
        if (window.lucide) lucide.createIcons();
    }
}

function confirmArchiveSubject(subjectId, subjectName) {
    document.getElementById("confirmTitle").textContent = "Archive Subject";
    document.getElementById("confirmSubtitle").textContent = "Subject will be deactivated. Historical records preserved.";
    document.getElementById("confirmMessage").textContent =
        `Are you sure you want to archive "${subjectName}"? All doubts and answers for this subject will remain in the database. Faculty assignments will be deactivated. This subject will no longer appear in student or teacher dashboards.`;
    document.getElementById("confirmActionBtn").onclick = () => archiveSubject(subjectId);
    openModal("modalConfirm");
}

async function archiveSubject(subjectId) {
    closeModal("modalConfirm");
    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}`, {
            method: "DELETE", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to archive subject.");
        showToast("Subject archived successfully. Historical records preserved.", "success");
        await loadSubjects();
        await loadOverviewStats();
    } catch (e) { showToast(e.message, "error"); }
}

async function restoreSubject(subjectId) {
    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}/restore`, {
            method: "PATCH", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to restore subject.");
        showToast("Subject restored successfully.", "success");
        await loadSubjects();
    } catch (e) { showToast(e.message, "error"); }
}


// ─── EDIT SUBJECT SEMESTER ───────────────────────────────────────────────────
function openEditSubjectSemesterModal(subjectId) {
    const s = allSubjects.find(sub => sub.id === subjectId);
    if (!s) return;
    document.getElementById("editSubjectSemId").value = s.id;
    document.getElementById("editSubjSemName").textContent = s.name;
    document.getElementById("editSubjSemMeta").textContent = s.code + " · " + (s.department || "");
    const badgeEl = document.getElementById("editSubjCurrentSemBadge");
    if (badgeEl) {
        badgeEl.textContent = s.semester_number ? "Semester " + s.semester_number : "Unassigned";
        badgeEl.className = s.semester_number ? "badge badge-blue" : "badge badge-amber";
    }
    const selectEl = document.getElementById("editSubjNewSemester");
    if (selectEl) selectEl.value = s.semester_number ? String(s.semester_number) : "";
    openModal("modalEditSubjectSemester");
}

async function handleSubjectSemesterSubmit(e) {
    e.preventDefault();
    const subjectId = parseInt(document.getElementById("editSubjectSemId").value, 10);
    const newSem = parseInt(document.getElementById("editSubjNewSemester").value, 10);
    if (!subjectId || isNaN(newSem)) return;
    const btn = document.getElementById("btnSaveSubjectSem");
    btn.disabled = true; btn.textContent = "Saving...";
    try {
        const res = await fetch(API + "/api/admin/subjects/" + subjectId + "/semester", {
            method: "PATCH", headers: authHeaders(),
            body: JSON.stringify({ semester_number: newSem })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update subject semester.");
        showToast("Subject semester changed to Semester " + newSem + " successfully!", "success");
        closeModal("modalEditSubjectSemester");
        await loadSubjects();
        await loadOverviewStats();
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        btn.disabled = false; btn.textContent = "Save Semester";
    }
}

// ─── STUDENT ACADEMIC MANAGEMENT ─────────────────────────────────────────
async function loadAdminStudents() {
    try {
        const res = await fetch(API + "/api/admin/students", { headers: authHeaders() });
        if (!res.ok) throw new Error("Could not load student list.");
        const json = await res.json();
        allStudents = json.data || [];
        filteredStudents = [...allStudents];
        const total = allStudents.length;
        const assigned = allStudents.filter(s => s.current_semester).length;
        const unassigned = total - assigned;
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
        set("stuSummTotal", total);
        set("stuSummAssigned", assigned);
        set("stuSummUnassigned", unassigned);
        renderStudentsTable(filteredStudents);
    } catch (e) {
        console.error("Student load error:", e);
        const tbody = document.getElementById("studentsTableBody");
        if (tbody) tbody.innerHTML = errRow(7, e.message);
    }
    if (window.lucide) lucide.createIcons();
}

function renderStudentsTable(students) {
    const tbody = document.getElementById("studentsTableBody");
    if (!tbody) return;
    if (students.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7'>" + emptyState("No students found", "Try another filter or search keyword.") + "</td></tr>";
        return;
    }
    tbody.innerHTML = students.map(s => {
        const semBadge = s.current_semester
            ? "<span class='badge badge-blue'>Semester " + s.current_semester + "</span>"
            : "<span class='badge badge-amber'>Not Assigned</span>";
        return "<tr>" +
            "<td><strong style='color:var(--text); font-size:12px;'>" + esc(s.college_id || s.id) + "</strong></td>" +
            "<td><div style='font-weight:600; color:var(--text); font-size:13px;'>" + esc(s.full_name) + "</div></td>" +
            "<td style='font-size:12px; color:var(--text-muted);'>" + esc(s.email) + "</td>" +
            "<td style='font-size:12px;'>" + esc(s.department || "—") + "</td>" +
            "<td>" + semBadge + "</td>" +
            "<td style='font-size:12px;'>" + esc(s.section || "—") + "</td>" +
            "<td><button class='btn btn-xs btn-primary' onclick='openEditStudentSemesterModal(" + s.id + ")' title='Change Semester'>" +
            "<i data-lucide='edit-3'></i> Change Semester</button></td>" +
            "</tr>";
    }).join("");
    if (window.lucide) lucide.createIcons();
}

function filterStudents() {
    const q = (document.getElementById("studentSearch") ? document.getElementById("studentSearch").value : "").toLowerCase().trim();
    const dept = document.getElementById("studentDeptFilter") ? document.getElementById("studentDeptFilter").value : "";
    const sem = document.getElementById("studentSemFilter") ? document.getElementById("studentSemFilter").value : "";
    filteredStudents = allStudents.filter(s => {
        const matchQ = !q || (s.full_name||"").toLowerCase().includes(q) || (s.college_id||"").toLowerCase().includes(q) || (s.email||"").toLowerCase().includes(q);
        const matchDept = !dept || (s.department||"").includes(dept);
        const matchSem = !sem || (sem === "unassigned" && !s.current_semester) || (s.current_semester === parseInt(sem, 10));
        return matchQ && matchDept && matchSem;
    });
    renderStudentsTable(filteredStudents);
}

function openEditStudentSemesterModal(studentId) {
    const s = allStudents.find(stu => stu.id === studentId);
    if (!s) return;
    document.getElementById("editStudentId").value = s.id;
    document.getElementById("editStudentName").textContent = s.full_name;
    document.getElementById("editStudentMeta").textContent = (s.college_id || "ID: " + s.id) + " · " + (s.department || "Department");
    const badgeEl = document.getElementById("editStudentCurrentSemBadge");
    if (badgeEl) {
        badgeEl.textContent = s.current_semester ? "Semester " + s.current_semester : "Not Assigned";
        badgeEl.className = s.current_semester ? "badge badge-blue" : "badge badge-amber";
    }
    const selectEl = document.getElementById("editStudentNewSemester");
    if (selectEl) selectEl.value = s.current_semester ? String(s.current_semester) : "";
    openModal("modalEditStudentSemester");
}

function promptStudentSemesterConfirm(e) {
    e.preventDefault();
    const studentId = parseInt(document.getElementById("editStudentId").value, 10);
    const newSem = parseInt(document.getElementById("editStudentNewSemester").value, 10);
    if (!studentId || isNaN(newSem)) return;
    const student = allStudents.find(s => s.id === studentId);
    if (!student) return;
    const currLabel = student.current_semester ? "Semester " + student.current_semester : "Not Assigned";
    const newLabel = "Semester " + newSem;
    pendingStudentSemesterChange = { studentId: student.id, studentName: student.full_name, newSemester: newSem };
    closeModal("modalEditStudentSemester");
    document.getElementById("confirmTitle").textContent = "Confirm Semester Change";
    document.getElementById("confirmSubtitle").textContent = "Academic Progression & Subject Visibility";
    document.getElementById("confirmMessage").textContent = "Are you sure you want to change this student's semester from " + currLabel + " to " + newLabel + "? Their available subjects will be updated accordingly.";
    document.getElementById("confirmActionBtn").textContent = "Confirm Change";
    document.getElementById("confirmActionBtn").className = "btn btn-primary";
    document.getElementById("confirmActionBtn").onclick = () => executeStudentSemesterChange();
    openModal("modalConfirm");
}

async function executeStudentSemesterChange() {
    closeModal("modalConfirm");
    if (!pendingStudentSemesterChange) return;
    const { studentId, studentName, newSemester } = pendingStudentSemesterChange;
    pendingStudentSemesterChange = null;
    try {
        const res = await fetch(API + "/api/admin/students/" + studentId + "/semester", {
            method: "PATCH", headers: authHeaders(),
            body: JSON.stringify({ current_semester: newSemester, semester_number: newSemester })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update student semester.");
        showToast("Semester for " + studentName + " updated to Semester " + newSemester + "! Available subjects updated.", "success");
        await loadAdminStudents();
        await loadOverviewStats();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ─── MANAGE FACULTY MODAL ─────────────────────────────────────────────────────
async function openManageFacultyModal(subjectId) {
    mgmtActiveSubjectId = subjectId;
    document.getElementById("mgmtSubjectId").value = subjectId;
    openModal("modalManageFaculty");

    document.getElementById("mgmtAssignedList").innerHTML = `<div class="empty-state" style="padding:12px;"><p>Loading...</p></div>`;

    try {
        const [subjRes, teachRes] = await Promise.all([
            fetch(`${API}/api/admin/subjects/${subjectId}/teachers`, { headers: authHeaders() }),
            allTeachers.length > 0
                ? Promise.resolve({ ok: true, json: async () => ({ data: allTeachers }) })
                : fetch(`${API}/api/admin/teachers`, { headers: authHeaders() }),
        ]);

        const rawSubj = await subjRes.json();
        const assignments = Array.isArray(rawSubj)
            ? rawSubj
            : (rawSubj.assignments || rawSubj.data || rawSubj.faculty || []);
        const rawTeach = await teachRes.json();
        const teachers = Array.isArray(rawTeach)
            ? rawTeach
            : (rawTeach.data || rawTeach.teachers || rawTeach.faculty || []);
        if (allTeachers.length === 0) allTeachers = teachers;

        // Update modal title
        const subject = allSubjects.find(s => s.id === subjectId);
        if (subject) {
            document.getElementById("mgmtModalSubjectName").textContent = subject.name;
            document.getElementById("mgmtModalSubjectMeta").textContent =
                `${subject.code} • ${subject.department || ""} ${subject.semester_label ? '• Sem ' + subject.semester_label : ''}`;
        }

        // Render assigned
        if (assignments.length === 0) {
            document.getElementById("mgmtAssignedList").innerHTML =
                `<div style="text-align:center; padding:16px; color:var(--text-muted); font-size:13px; background:#F8FAFC; border-radius:8px;">No faculty currently assigned to this subject.</div>`;
        } else {
            document.getElementById("mgmtAssignedList").innerHTML = assignments.map(a => `
                <div class="assigned-item ${a.is_primary ? 'primary-item' : ''}">
                    <div class="assigned-item-info">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div class="assigned-item-name">${esc(a.full_name)}</div>
                            <span class="badge ${a.is_primary ? 'badge-blue' : 'badge-gray'}">${a.is_primary ? 'Primary Faculty' : 'Additional Faculty'}</span>
                        </div>
                        <div class="assigned-item-meta">${esc(a.department || "")} • ${esc(a.teacher_code)}</div>
                    </div>
                    <div class="assigned-item-actions">
                        ${!a.is_primary ? `
                            <button class="btn btn-xs" style="background:#EEF2FF; color:var(--primary);"
                                onclick="makeFacultyPrimary(${subjectId}, ${a.teacher_id})">
                                <i data-lucide="star"></i> Make Primary
                            </button>` : ''}
                        <button class="btn btn-xs btn-danger"
                            onclick="removeFacultyAssignment(${subjectId}, ${a.teacher_id}, '${esc(a.full_name).replace(/'/g,"\\'")}')">
                            <i data-lucide="user-minus"></i>
                        </button>
                    </div>
                </div>
            `).join("");
        }

        // Populate assign dropdown (only unassigned active teachers)
        const assignedIds = new Set(assignments.map(a => a.teacher_id));
        const unassigned = teachers.filter(t => t.is_active && !assignedIds.has(t.id));
        const sel = document.getElementById("mgmtTeacherSelect");
        sel.innerHTML = `<option value="">Select teacher to assign...</option>` +
            unassigned.map(t => `<option value="${t.id}">${esc(t.full_name)} (${esc(t.teacher_code)}) — ${esc(t.department || "")}</option>`).join("");

        if (window.lucide) lucide.createIcons();
    } catch (e) {
        document.getElementById("mgmtAssignedList").innerHTML = `<div class="empty-state"><p>${esc(e.message)}</p></div>`;
    }
}

async function handleAssignFacultySubmit(e) {
    e.preventDefault();
    const subjectId = mgmtActiveSubjectId;
    const teacherId = parseInt(document.getElementById("mgmtTeacherSelect").value);
    const isPrimary = document.getElementById("mgmtIsPrimary").checked;

    if (!teacherId) { showToast("Please select a teacher.", "error"); return; }

    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}/teachers`, {
            method: "POST", headers: authHeaders(),
            body: JSON.stringify({ teacher_id: teacherId, is_primary: isPrimary }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to assign teacher.");
        showToast(`Faculty assigned successfully${isPrimary ? ' as Primary Faculty' : ''}.`, "success");
        document.getElementById("mgmtIsPrimary").checked = false;
        await openManageFacultyModal(subjectId);
        await loadSubjects();
        await loadOverviewStats();
    } catch (e) { showToast(e.message, "error"); }
}

async function makeFacultyPrimary(subjectId, teacherId) {
    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}/teachers/${teacherId}/primary`, {
            method: "PATCH", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update primary faculty.");
        showToast("Primary faculty updated successfully.", "success");
        await openManageFacultyModal(subjectId);
        await loadSubjects();
    } catch (e) { showToast(e.message, "error"); }
}

async function removeFacultyAssignment(subjectId, teacherId, teacherName) {
    if (!confirm(`Remove ${teacherName} from this subject? Historical doubts and answers will be preserved.`)) return;
    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}/teachers/${teacherId}`, {
            method: "DELETE", headers: authHeaders()
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to remove assignment.");
        showToast("Faculty assignment removed. Historical records preserved.", "success");
        await openManageFacultyModal(subjectId);
        await loadSubjects();
        await loadOverviewStats();
    } catch (e) { showToast(e.message, "error"); }
}

// ─── DOUBT ROUTING ────────────────────────────────────────────────────────────
async function loadRoutingDoubts() {
    const statusFilter = document.getElementById("routingStatusFilter")?.value || "pending";
    const tbody = document.getElementById("routingTableBody");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><p>Loading doubts...</p></div></td></tr>`;

    try {
        const url = `${API}/api/admin/doubts${statusFilter ? `?status_filter=${statusFilter}` : ""}`;
        const res = await fetch(url, { headers: authHeaders() });
        if (!res.ok) throw new Error("Could not load doubts.");
        const { data: doubts = [] } = await res.json();

        if (doubts.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7">${emptyState("No doubts found", "No doubts match the current filter.")}</td></tr>`;
            return;
        }

        tbody.innerHTML = doubts.map(d => {
            const tName = d.assigned_teacher?.name || "Unassigned";
            const dateStr = d.created_at ? new Date(d.created_at).toLocaleDateString("en-IN", { day:"2-digit", month:"short", year:"numeric" }) : "—";
            return `
                <tr>
                    <td><span class="badge badge-gray" style="font-size:11px;">${esc(d.doubt_code)}</span></td>
                    <td><span class="badge badge-blue">${esc(d.subject?.code || d.subject?.name || "—")}</span></td>
                    <td>
                        <div style="font-weight:600; font-size:13px;">${esc(d.title)}</div>
                        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">${esc((d.description || "").substring(0, 90))}${(d.description || "").length > 90 ? "..." : ""}</div>
                    </td>
                    <td style="font-size:13px;"><strong>${esc(tName)}</strong></td>
                    <td><span class="badge ${d.status === 'resolved' ? 'badge-green' : d.status === 'in_progress' ? 'badge-blue' : 'badge-amber'}">${esc(d.status)}</span></td>
                    <td style="font-size:12px; color:var(--text-muted);">${dateStr}</td>
                    <td>
                        <button class="btn btn-sm btn-primary"
                            onclick="openReassignDoubtModal(${d.id}, ${d.subject?.id || 'null'}, '${esc(d.doubt_code).replace(/'/g,"\\'")}')">
                            <i data-lucide="arrow-right-left"></i> Reassign
                        </button>
                    </td>
                </tr>
            `;
        }).join("");
        if (window.lucide) lucide.createIcons();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7">${emptyState("Error", e.message)}</td></tr>`;
    }
}

async function openReassignDoubtModal(doubtId, subjectId, doubtCode) {
    document.getElementById("reassignDoubtId").value = doubtId;
    document.getElementById("reassignDoubtCode").textContent = `Doubt: ${doubtCode}`;
    const sel = document.getElementById("reassignFacultySelect");
    sel.innerHTML = `<option value="">Loading assigned teachers...</option>`;
    openModal("modalReassignDoubt");

    if (!subjectId) {
        sel.innerHTML = `<option value="">No subject found — cannot reassign</option>`;
        return;
    }

    try {
        const res = await fetch(`${API}/api/admin/subjects/${subjectId}/teachers`, { headers: authHeaders() });
        const rawSubj = await res.json();
        const assignments = Array.isArray(rawSubj)
            ? rawSubj
            : (rawSubj.assignments || rawSubj.data || rawSubj.faculty || []);
        if (assignments.length === 0) {
            sel.innerHTML = `<option value="">No faculty assigned to this subject</option>`;
            return;
        }
        sel.innerHTML = `<option value="">Select faculty member...</option>` +
            assignments.map(a => `<option value="${a.teacher_id}">${esc(a.full_name)} (${esc(a.teacher_code)}) ${a.is_primary ? '— Primary' : ''}</option>`).join("");
    } catch (e) { sel.innerHTML = `<option value="">Error: ${esc(e.message)}</option>`; }
}

async function handleReassignDoubt(e) {
    e.preventDefault();
    const doubtId = document.getElementById("reassignDoubtId").value;
    const teacherId = parseInt(document.getElementById("reassignFacultySelect").value);
    if (!teacherId) { showToast("Please select a faculty member.", "error"); return; }

    try {
        const res = await fetch(`${API}/api/admin/doubts/${doubtId}/reassign`, {
            method: "PATCH", headers: authHeaders(), body: JSON.stringify({ teacher_id: teacherId }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to reassign doubt.");
        showToast("Doubt reassigned successfully!", "success");
        closeModal("modalReassignDoubt");
        await loadRoutingDoubts();
        await loadOverviewStats();
    } catch (e) { showToast(e.message, "error"); }
}

// ─── MODAL HELPERS ────────────────────────────────────────────────────────────
function openModal(id) {
    const el = document.getElementById(id);
    if (el) { el.classList.add("open"); if (window.lucide) lucide.createIcons(); }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove("open");
}

// Close modal on overlay click
document.addEventListener("click", e => {
    if (e.target.classList.contains("modal-overlay")) {
        e.target.classList.remove("open");
    }
});

// ─── TOAST ────────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;
    const iconMap = { success: "check-circle", error: "alert-circle", info: "info" };
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<i data-lucide="${iconMap[type]}"></i><span>${esc(message)}</span>`;
    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();
    setTimeout(() => { toast.style.opacity = "0"; toast.style.transition = "opacity 0.3s"; setTimeout(() => toast.remove(), 300); }, 4000);
}

// ─── UTILS ────────────────────────────────────────────────────────────────────
function esc(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"})[c]);
}

function emptyState(title, subtitle) {
    return `
        <div class="empty-state">
            <i data-lucide="inbox"></i>
            <h4>${esc(title)}</h4>
            ${subtitle ? `<p>${esc(subtitle)}</p>` : ""}
        </div>`;
}

function errRow(cols, msg) {
    return `<tr><td colspan="${cols}"><div class="empty-state"><i data-lucide="alert-circle"></i><h4>Error</h4><p>${esc(msg)}</p></div></td></tr>`;
}
