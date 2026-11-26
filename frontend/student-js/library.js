/* ==============================================================================
   CLARIQ — STUDENT ACADEMIC LIBRARY SCRIPT
   Integrates directly with FastAPI /api/library/student endpoints
   ============================================================================== */

const API_BASE_URL = window.location.hostname === "localhost" ? "http://localhost:8000" : "http://127.0.0.1:8000";

let studentSubjects = [];
let selectedSubjectId = null;
let currentResources = [];
let isImportantOnly = false;

function getAuthToken() {
    return sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
}

function authHeaders() {
    return {
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
    initUserProfile();
    setupEventListeners();
    await loadSubjects();
});

async function initUserProfile() {
    try {
        const rawUser = localStorage.getItem("clariqUser") || sessionStorage.getItem("clariqUser");
        if (rawUser) {
            const user = JSON.parse(rawUser);
            // login.js stores name as 'name', fallback to full_name for compatibility
            const displayName = user.name || user.full_name || "Student";
            const nameEl = document.getElementById("studentName");
            const avatarEl = document.getElementById("studentAvatar");
            if (nameEl) nameEl.textContent = displayName;
            if (avatarEl) avatarEl.textContent = displayName.charAt(0).toUpperCase();
        }
    } catch (e) {
        console.error("Error reading user profile", e);
    }

    // Refresh dynamically from student dashboard profile
    const token = getAuthToken();
    if (!token) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/student/dashboard`, {
            headers: authHeaders()
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
        // Ignore transient network errors
    }
}

function setupEventListeners() {
    const subjectSelect = document.getElementById("subjectSelect");
    if (subjectSelect) {
        subjectSelect.addEventListener("change", (e) => {
            selectedSubjectId = parseInt(e.target.value) || null;
            updateSubjectBanner();
            loadResources();
        });
    }

    const searchInput = document.getElementById("libSearchInput");
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener("input", () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                loadResources();
            }, 300);
        });
    }

    const typeFilter = document.getElementById("typeFilter");
    if (typeFilter) {
        typeFilter.addEventListener("change", () => loadResources());
    }

    const facultyFilter = document.getElementById("facultyFilter");
    if (facultyFilter) {
        facultyFilter.addEventListener("change", () => loadResources());
    }

    const sortSelect = document.getElementById("sortSelect");
    if (sortSelect) {
        sortSelect.addEventListener("change", () => loadResources());
    }

    const btnToggleImportant = document.getElementById("btnToggleImportant");
    if (btnToggleImportant) {
        btnToggleImportant.addEventListener("click", () => {
            isImportantOnly = !isImportantOnly;
            btnToggleImportant.classList.toggle("active", isImportantOnly);
            loadResources();
        });
    }
}

// ==========================================
// LOAD SUBJECTS
// ==========================================
async function loadSubjects() {
    const subjectSelect = document.getElementById("subjectSelect");
    try {
        const response = await fetch(`${API_BASE_URL}/api/library/student/subjects`, {
            headers: authHeaders()
        });

        if (!response.ok) throw new Error("Failed to load subjects.");
        const data = await response.json();
        studentSubjects = data.data || [];

        if (studentSubjects.length === 0) {
            subjectSelect.innerHTML = `<option value="">No subjects assigned</option>`;
            return;
        }

        // Check if query param specifies subject_id
        const urlParams = new URLSearchParams(window.location.search);
        const querySubjectId = parseInt(urlParams.get("subject_id"));

        let optionsHtml = "";
        let matched = false;

        studentSubjects.forEach(s => {
            const isSelected = querySubjectId && querySubjectId === s.id;
            if (isSelected) matched = true;
            optionsHtml += `<option value="${s.id}" ${isSelected ? "selected" : ""}>${escapeHTML(s.code || "")} — ${escapeHTML(s.name)}</option>`;
        });

        subjectSelect.innerHTML = optionsHtml;
        selectedSubjectId = matched ? querySubjectId : studentSubjects[0].id;
        subjectSelect.value = selectedSubjectId;

        updateSubjectBanner();
        await loadResources();

    } catch (err) {
        console.error("Error loading subjects:", err);
        subjectSelect.innerHTML = `<option value="">Error loading subjects</option>`;
    }
}

function updateSubjectBanner() {
    const banner = document.getElementById("subjectBanner");
    const subjName = document.getElementById("bannerSubjectName");
    const subjCode = document.getElementById("bannerSubjectCode");

    const found = studentSubjects.find(s => s.id === selectedSubjectId);
    if (found && banner) {
        banner.style.display = "flex";
        subjName.textContent = found.name;
        subjCode.textContent = found.code ? `Course Code: ${found.code}` : "Course Materials & References";
    }
}

// ==========================================
// LOAD RESOURCES
// ==========================================
async function loadResources() {
    if (!selectedSubjectId) return;

    const loading = document.getElementById("loadingIndicator");
    const primaryGrid = document.getElementById("primaryGrid");
    const additionalGrid = document.getElementById("additionalGrid");
    const primaryEmpty = document.getElementById("primaryEmpty");
    const additionalEmpty = document.getElementById("additionalEmpty");
    const primaryCount = document.getElementById("primaryCountBadge");
    const additionalCount = document.getElementById("additionalCountBadge");
    const totalCount = document.getElementById("totalResourcesCount");

    if (loading) loading.style.display = "block";
    if (primaryEmpty) primaryEmpty.style.display = "none";
    if (additionalEmpty) additionalEmpty.style.display = "none";

    try {
        const search = document.getElementById("libSearchInput")?.value.trim() || "";
        const rType = document.getElementById("typeFilter")?.value || "";
        const fCategory = document.getElementById("facultyFilter")?.value || "";
        const sort = document.getElementById("sortSelect")?.value || "newest";

        const params = new URLSearchParams({
            subject_id: selectedSubjectId,
            sort: sort
        });
        if (search) params.append("search", search);
        if (rType) params.append("resource_type", rType);
        if (fCategory) params.append("faculty_category", fCategory);
        if (isImportantOnly) params.append("important_only", "true");

        const response = await fetch(`${API_BASE_URL}/api/library/student/resources?${params.toString()}`, {
            headers: authHeaders()
        });

        if (!response.ok) throw new Error("Failed to load resources.");
        const data = await response.json();
        currentResources = data.data || [];

        // Split into Primary vs Additional
        const primaryList = currentResources.filter(r => (r.faculty_category || "PRIMARY").toUpperCase() === "PRIMARY");
        const additionalList = currentResources.filter(r => (r.faculty_category || "").toUpperCase() === "ADDITIONAL");

        if (totalCount) totalCount.textContent = currentResources.length;
        if (primaryCount) primaryCount.textContent = `${primaryList.length} resource${primaryList.length === 1 ? "" : "s"}`;
        if (additionalCount) additionalCount.textContent = `${additionalList.length} resource${additionalList.length === 1 ? "" : "s"}`;

        // Render Primary Section
        if (primaryList.length > 0) {
            primaryGrid.innerHTML = primaryList.map(r => renderResourceCard(r)).join("");
            primaryEmpty.style.display = "none";
        } else {
            primaryGrid.innerHTML = "";
            primaryEmpty.style.display = "block";
        }

        // Render Additional Section
        if (additionalList.length > 0) {
            additionalGrid.innerHTML = additionalList.map(r => renderResourceCard(r)).join("");
            additionalEmpty.style.display = "none";
        } else {
            additionalGrid.innerHTML = "";
            additionalEmpty.style.display = "block";
        }

        if (window.lucide) lucide.createIcons();

    } catch (err) {
        console.error("Error loading resources:", err);
    } finally {
        if (loading) loading.style.display = "none";
    }
}

// ==========================================
// RENDER RESOURCE CARD
// ==========================================
function renderResourceCard(r) {
    const isYt = r.resource_type === "youtube";
    const typeLabel = r.resource_type.toUpperCase();
    const tagClass = isYt ? "tag-youtube" : (r.resource_type === "pdf" ? "tag-pdf" : "tag-doc");
    const uploadDate = r.created_at ? new Date(r.created_at).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric'
    }) : "";

    const isAdditional = (r.faculty_category || "").toUpperCase() === "ADDITIONAL";

    let ytPreviewHtml = "";
    if (isYt && r.youtube_thumbnail) {
        ytPreviewHtml = `
            <div class="yt-thumb-wrapper" onclick="openYtModal('${escapeHTML(r.youtube_video_id)}', '${escapeHTML(r.title)}')">
                <img src="${escapeHTML(r.youtube_thumbnail)}" alt="Thumbnail" class="yt-thumb">
                <div class="yt-play-overlay">
                    <div class="yt-play-btn">
                        <i data-lucide="play" style="fill: white; width: 22px; height: 22px;"></i>
                    </div>
                </div>
            </div>
        `;
    }

    return `
        <div class="resource-card" id="resource-${r.id}">
            <div>
                <div class="card-top">
                    <span class="card-type-tag ${tagClass}">
                        <i data-lucide="${isYt ? 'video' : (r.resource_type === 'pdf' ? 'file-text' : 'file')}"></i>
                        ${typeLabel}
                    </span>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        ${isAdditional ? '<span style="font-size: 11px; background: #F1F5F9; color: #475569; padding: 2px 7px; border-radius: 6px; font-weight: 600;">Additional</span>' : ''}
                        ${r.is_important ? '<span class="important-badge"><i data-lucide="star" style="fill: white; width: 12px; height: 12px;"></i> IMPORTANT</span>' : ''}
                    </div>
                </div>

                ${ytPreviewHtml}

                <h4 class="resource-title">${escapeHTML(r.title)}</h4>
                ${r.description ? `<p class="resource-desc">${escapeHTML(r.description)}</p>` : ''}

                <div class="resource-meta">
                    <span>
                        <i data-lucide="user" style="width: 14px; height: 14px;"></i>
                        <strong>${escapeHTML(r.teacher_name || "Faculty")}</strong>
                    </span>
                    <span>
                        <i data-lucide="calendar" style="width: 14px; height: 14px;"></i>
                        Uploaded on ${uploadDate}
                    </span>
                    ${r.file_size ? `
                        <span>
                            <i data-lucide="hard-drive" style="width: 14px; height: 14px;"></i>
                            ${formatBytes(r.file_size)}
                        </span>
                    ` : ''}
                </div>
            </div>

            <div class="card-actions">
                ${isYt ? `
                    <button class="btn-watch" onclick="openYtModal('${escapeHTML(r.youtube_video_id)}', '${escapeHTML(r.title)}')">
                        <i data-lucide="play" style="width: 16px; height: 16px;"></i>
                        Watch Video
                    </button>
                ` : `
                    ${r.resource_type === 'pdf' ? `
                        <button class="btn-preview" onclick="openPdfPreview(${r.id}, '${escapeHTML(r.title)}')">
                            <i data-lucide="eye" style="width: 16px; height: 16px;"></i>
                            Preview
                        </button>
                    ` : ''}
                    <button class="btn-download" onclick="downloadResourceFile(${r.id}, '${escapeHTML(r.original_filename || r.title)}')">
                        <i data-lucide="download" style="width: 16px; height: 16px;"></i>
                        Download
                    </button>
                `}
            </div>
        </div>
    `;
}

// ==========================================
// PREVIEW & DOWNLOAD HANDLERS
// ==========================================
async function openPdfPreview(resourceId, title) {
    const modal = document.getElementById("pdfModal");
    const modalTitle = document.getElementById("pdfModalTitle");
    const iframe = document.getElementById("pdfIframe");
    const downloadBtn = document.getElementById("pdfModalDownloadBtn");

    if (modalTitle) modalTitle.textContent = title;
    if (downloadBtn) {
        downloadBtn.onclick = () => downloadResourceFile(resourceId, title + ".pdf");
    }

    try {
        // Fetch raw PDF bytes with Authorization header
        const res = await fetch(`${API_BASE_URL}/api/library/student/resources/${resourceId}/download`, {
            headers: authHeaders()
        });

        if (!res.ok) throw new Error("Could not load document preview.");
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);

        if (iframe) iframe.src = objUrl;
        if (modal) modal.classList.add("active");

    } catch (err) {
        alert("Failed to preview document: " + err.message);
    }
}

function closePdfModal() {
    const modal = document.getElementById("pdfModal");
    const iframe = document.getElementById("pdfIframe");
    if (iframe) iframe.src = "";
    if (modal) modal.classList.remove("active");
}

async function downloadResourceFile(resourceId, filename) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/library/student/resources/${resourceId}/download`, {
            headers: authHeaders()
        });

        if (!res.ok) throw new Error("Download failed.");
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename || "resource";
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    } catch (err) {
        alert("Error downloading file: " + err.message);
    }
}

// ==========================================
// YOUTUBE MODAL
// ==========================================
function openYtModal(videoId, title) {
    const modal = document.getElementById("ytModal");
    const modalTitle = document.getElementById("ytModalTitle");
    const iframe = document.getElementById("ytIframe");

    if (modalTitle) modalTitle.textContent = title;
    if (iframe) {
        iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
    }
    if (modal) modal.classList.add("active");
}

function closeYtModal() {
    const modal = document.getElementById("ytModal");
    const iframe = document.getElementById("ytIframe");
    if (iframe) iframe.src = "";
    if (modal) modal.classList.remove("active");
}

// ==========================================
// UTILITIES
// ==========================================
function formatBytes(bytes, decimals = 1) {
    if (!bytes) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
