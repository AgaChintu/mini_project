/* ==============================================================================
   CLARIQ — FACULTY ACADEMIC LIBRARY MANAGEMENT SCRIPT
   Integrates directly with FastAPI /api/library/teacher endpoints
   ============================================================================== */

const API_BASE_URL = window.location.hostname === "localhost" ? "http://localhost:8000" : "http://127.0.0.1:8000";

let teacherSubjects = [];
let selectedFormat = "pdf"; // pdf / doc / youtube
let currentSelectedFile = null;
let allResources = [];

function getAuthToken() {
    return sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
}

function authHeaders(isJson = true) {
    const headers = {
        "Authorization": `Bearer ${getAuthToken()}`
    };
    if (isJson) headers["Content-Type"] = "application/json";
    return headers;
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
    setupFormControls();
    await loadTeacherSubjects();
    await loadManagedResources();
});

// ==========================================
// FORM CONTROLS & LISTENERS
// ==========================================
function setupFormControls() {
    // Subject selector change
    const subjectSelect = document.getElementById("resourceSubjectSelect");
    if (subjectSelect) {
        subjectSelect.addEventListener("change", handleSubjectSelectionChange);
    }

    // Type selector tabs
    const typeTabs = document.querySelectorAll(".type-tab");
    typeTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            typeTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            selectedFormat = tab.getAttribute("data-type");
            toggleUploadSections();
        });
    });

    // Drag and Drop & Browse
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("docFileInput");

    if (dropZone && fileInput) {
        fileInput.addEventListener("click", (e) => e.stopPropagation());
        dropZone.addEventListener("click", (e) => {
            if (e.target !== fileInput) {
                fileInput.click();
            }
        });

        dropZone.addEventListener("dragover", (e) => {
            e.preventDefault();
            dropZone.classList.add("dragover");
        });

        dropZone.addEventListener("dragleave", () => {
            dropZone.classList.remove("dragover");
        });

        dropZone.addEventListener("drop", (e) => {
            e.preventDefault();
            dropZone.classList.remove("dragover");
            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleFileSelection(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files[0]) {
                handleFileSelection(e.target.files[0]);
            }
        });
    }

    const btnRemoveFile = document.getElementById("btnRemoveFile");
    if (btnRemoveFile) {
        btnRemoveFile.addEventListener("click", (e) => {
            e.stopPropagation();
            clearSelectedFile();
        });
    }

    // YouTube URL input preview
    const ytInput = document.getElementById("ytUrlInput");
    if (ytInput) {
        ytInput.addEventListener("input", () => {
            const url = ytInput.value.trim();
            const vid = extractYouTubeId(url);
            const previewBox = document.getElementById("ytLivePreview");
            const previewImg = document.getElementById("ytPreviewImg");

            if (vid) {
                previewImg.src = `https://img.youtube.com/vi/${vid}/hqdefault.jpg`;
                previewBox.style.display = "block";
            } else {
                previewBox.style.display = "none";
                previewImg.src = "";
            }
        });
    }

    // Upload form submit
    const uploadForm = document.getElementById("uploadResourceForm");
    if (uploadForm) {
        uploadForm.addEventListener("submit", handleResourceUpload);
    }

    // Manage filters
    const manageSearch = document.getElementById("manageSearchInput");
    const manageSubj = document.getElementById("manageSubjectFilter");
    const manageType = document.getElementById("manageTypeFilter");

    if (manageSearch) manageSearch.addEventListener("input", debounce(loadManagedResources, 300));
    if (manageSubj) manageSubj.addEventListener("change", loadManagedResources);
    if (manageType) manageType.addEventListener("change", loadManagedResources);

    // Edit form submit
    const editForm = document.getElementById("editResourceForm");
    if (editForm) {
        editForm.addEventListener("submit", handleEditSubmit);
    }
}

function toggleUploadSections() {
    const docSection = document.getElementById("docUploadSection");
    const ytSection = document.getElementById("youtubeUploadSection");
    const fileInput = document.getElementById("docFileInput");

    if (selectedFormat === "youtube") {
        docSection.style.display = "none";
        ytSection.style.display = "block";
    } else {
        docSection.style.display = "block";
        ytSection.style.display = "none";
        if (fileInput) {
            fileInput.accept = selectedFormat === "pdf" ? ".pdf,application/pdf" : ".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
        }
    }
}

function handleFileSelection(file) {
    const dotIdx = file.name.lastIndexOf(".");
    const ext = dotIdx >= 0 ? file.name.substring(dotIdx).toLowerCase() : "";
    const allowed = [".pdf", ".doc", ".docx"];

    if (!allowed.includes(ext)) {
        showUploadStatus("Unsupported file format. Please upload a PDF, DOC, or DOCX document.", true);
        return;
    }
    if (file.size === 0) {
        showUploadStatus("Selected file is empty (0 bytes).", true);
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showUploadStatus("File size exceeds 50 MB limit.", true);
        return;
    }

    currentSelectedFile = file;
    document.getElementById("selectedFileName").textContent = file.name;
    document.getElementById("selectedFileSize").textContent = `(${formatBytes(file.size)})`;
    document.getElementById("selectedFileInfo").style.display = "flex";
    const statusBanner = document.getElementById("uploadStatusBanner");
    if (statusBanner) statusBanner.style.display = "none";
    if (window.lucide) lucide.createIcons();
}

function showUploadStatus(message, isError = false) {
    const banner = document.getElementById("uploadStatusBanner");
    if (!banner) {
        alert(message);
        return;
    }
    banner.style.display = "block";
    banner.style.background = isError ? "#FEF2F2" : "#ECFDF5";
    banner.style.border = isError ? "1px solid #FECACA" : "1px solid #A7F3D0";
    banner.style.color = isError ? "#B91C1C" : "#065F46";
    banner.textContent = message;
}

function clearSelectedFile() {
    currentSelectedFile = null;
    document.getElementById("docFileInput").value = "";
    document.getElementById("selectedFileInfo").style.display = "none";
}

function extractYouTubeId(url) {
    const match = url.match(/(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/)([A-Za-z0-9_\-]{11})/);
    return match ? match[1] : null;
}

// ==========================================
// LOAD SUBJECTS & HIERARCHY
// ==========================================
async function loadTeacherSubjects() {
    const subjectSelect = document.getElementById("resourceSubjectSelect");
    const filterSelect = document.getElementById("manageSubjectFilter");

    try {
        const response = await fetch(`${API_BASE_URL}/api/library/teacher/subjects`, {
            headers: authHeaders()
        });

        if (!response.ok) throw new Error("Failed to load your assigned subjects.");
        const data = await response.json();
        teacherSubjects = data.data || [];

        if (teacherSubjects.length === 0) {
            subjectSelect.innerHTML = `<option value="">No active subject assignments found</option>`;
            return;
        }

        let optionsHtml = `<option value="">-- Select Subject --</option>`;
        let filterHtml = `<option value="">All Subjects</option>`;

        teacherSubjects.forEach(s => {
            const roleBadge = s.faculty_category === "PRIMARY" ? "★ Primary Faculty" : "Additional Faculty";
            optionsHtml += `<option value="${s.id}" data-category="${s.faculty_category}">${escapeHTML(s.code || "")} — ${escapeHTML(s.name)} (${roleBadge})</option>`;
            filterHtml += `<option value="${s.id}">${escapeHTML(s.code || "")} — ${escapeHTML(s.name)}</option>`;
        });

        subjectSelect.innerHTML = optionsHtml;
        if (filterSelect) filterSelect.innerHTML = filterHtml;

    } catch (err) {
        console.error("Error loading teacher subjects:", err);
        subjectSelect.innerHTML = `<option value="">Error loading subjects</option>`;
    }
}

function handleSubjectSelectionChange() {
    const select = document.getElementById("resourceSubjectSelect");
    const noticeDiv = document.getElementById("facultyRoleNotice");
    const importantWrapper = document.getElementById("importantToggleWrapper");

    const selectedOption = select.options[select.selectedIndex];
    const category = selectedOption ? selectedOption.getAttribute("data-category") : null;

    if (!category) {
        noticeDiv.innerHTML = "";
        importantWrapper.style.display = "none";
        return;
    }

    if (category === "PRIMARY") {
        noticeDiv.innerHTML = `
            <span class="faculty-role-pill pill-primary">
                <i data-lucide="award" style="width: 12px; height: 12px;"></i>
                Designated Primary Faculty for this Subject
            </span>
            <p style="font-size: 11px; color: #64748B; margin: 4px 0 0;">
                Your uploads will be featured in the <strong>Primary Faculty Documents</strong> section on student dashboards.
            </p>
        `;
        importantWrapper.style.display = "none";
        document.getElementById("importantCheckbox").checked = false;
    } else {
        noticeDiv.innerHTML = `
            <span class="faculty-role-pill pill-additional">
                <i data-lucide="book-marked" style="width: 12px; height: 12px;"></i>
                Contributing Additional Faculty
            </span>
            <p style="font-size: 11px; color: #64748B; margin: 4px 0 0;">
                Your resources appear under <strong>Additional Faculty Documents</strong>. You can mark important resources below.
            </p>
        `;
        importantWrapper.style.display = "block";
    }

    if (window.lucide) lucide.createIcons();
}

// ==========================================
// UPLOAD RESOURCE HANDLER
// ==========================================
async function handleResourceUpload(e) {
    e.preventDefault();

    const subjectId = document.getElementById("resourceSubjectSelect").value;
    const title = document.getElementById("resourceTitle").value.trim();
    const desc = document.getElementById("resourceDesc").value.trim();
    const submitBtn = document.getElementById("btnSubmitResource");

    if (!subjectId) {
        alert("Please select a subject.");
        return;
    }
    if (!title) {
        alert("Please provide a resource title.");
        return;
    }

    const formData = new FormData();
    formData.append("subject_id", subjectId);
    formData.append("title", title);
    formData.append("description", desc);
    formData.append("resource_type", selectedFormat);

    if (selectedFormat === "youtube") {
        const ytUrl = document.getElementById("ytUrlInput").value.trim();
        const customTitle = document.getElementById("ytCustomTitle").value.trim();
        if (!ytUrl) {
            alert("Please provide a YouTube video URL.");
            return;
        }
        if (!extractYouTubeId(ytUrl)) {
            alert("Invalid YouTube URL format.");
            return;
        }
        formData.append("youtube_url", ytUrl);
        formData.append("youtube_title", customTitle || title);
    } else {
        if (!currentSelectedFile) {
            alert("Please select a document file to upload.");
            return;
        }
        formData.append("document", currentSelectedFile);
    }

    const isImportant = document.getElementById("importantCheckbox")?.checked || false;
    formData.append("is_important", isImportant ? "true" : "false");

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<i data-lucide="loader" class="animate-spin"></i> Uploading & Publishing...`;
    if (window.lucide) lucide.createIcons();

    const progressWrapper = document.getElementById("uploadProgressWrapper");
    const progressBar = document.getElementById("uploadProgressBar");
    const progressPercent = document.getElementById("uploadProgressPercent");
    const progressLabel = document.getElementById("uploadProgressLabel");
    const statusBanner = document.getElementById("uploadStatusBanner");
    if (statusBanner) statusBanner.style.display = "none";

    if (progressWrapper && selectedFormat !== "youtube") {
        progressWrapper.style.display = "block";
        progressBar.style.width = "0%";
        progressPercent.textContent = "0%";
        progressLabel.textContent = "Uploading document...";
    }

    try {
        const result = await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", `${API_BASE_URL}/api/library/teacher/resources`, true);
            xhr.setRequestHeader("Authorization", `Bearer ${getAuthToken()}`);

            xhr.upload.onprogress = (evt) => {
                if (evt.lengthComputable && progressBar && progressPercent) {
                    const pct = Math.min(100, Math.round((evt.loaded / evt.total) * 100));
                    progressBar.style.width = `${pct}%`;
                    progressPercent.textContent = `${pct}%`;
                    if (pct === 100 && progressLabel) {
                        progressLabel.textContent = "Processing & saving...";
                    }
                }
            };

            xhr.onload = () => {
                let parsed = {};
                try {
                    parsed = JSON.parse(xhr.responseText || "{}");
                } catch (_) {
                    parsed = {};
                }
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(parsed);
                } else {
                    reject(new Error(parsed.detail || `Upload failed (HTTP ${xhr.status}).`));
                }
            };

            xhr.onerror = () => reject(new Error("Network error while uploading. Ensure backend is running."));
            xhr.send(formData);
        });

        showUploadStatus("Resource published to Academic Library successfully!", false);
        document.getElementById("uploadResourceForm").reset();
        clearSelectedFile();
        document.getElementById("ytLivePreview").style.display = "none";
        document.getElementById("facultyRoleNotice").innerHTML = "";
        document.getElementById("importantToggleWrapper").style.display = "none";

        // Reset format tabs back to PDF default cleanly
        selectedFormat = "pdf";
        document.querySelectorAll(".type-tab").forEach(t => {
            t.classList.toggle("active", t.getAttribute("data-type") === "pdf");
        });
        toggleUploadSections();

        await loadManagedResources();

    } catch (err) {
        showUploadStatus("Upload error: " + err.message, true);
    } finally {
        if (progressWrapper) progressWrapper.style.display = "none";
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i data-lucide="upload"></i> Publish to Academic Library`;
        if (window.lucide) lucide.createIcons();
    }
}

// ==========================================
// LOAD MANAGED RESOURCES
// ==========================================
async function loadManagedResources() {
    const tableBody = document.getElementById("manageResourcesBody");
    const countPill = document.getElementById("resourceCountPill");

    const search = document.getElementById("manageSearchInput")?.value.trim() || "";
    const subjectId = document.getElementById("manageSubjectFilter")?.value || "";
    const rType = document.getElementById("manageTypeFilter")?.value || "";

    const params = new URLSearchParams();
    if (search) params.append("search", search);
    if (subjectId) params.append("subject_id", subjectId);
    if (rType) params.append("resource_type", rType);

    try {
        const res = await fetch(`${API_BASE_URL}/api/library/teacher/resources?${params.toString()}`, {
            headers: authHeaders()
        });

        if (!res.ok) throw new Error("Failed to load resources.");
        const data = await res.json();
        allResources = data.data || [];

        if (countPill) countPill.textContent = `${allResources.length} item${allResources.length === 1 ? '' : 's'}`;

        if (allResources.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #94A3B8; padding: 32px;">No published resources found matching your criteria.</td></tr>`;
            return;
        }

        tableBody.innerHTML = allResources.map(r => renderManageRow(r)).join("");
        if (window.lucide) lucide.createIcons();

    } catch (err) {
        console.error("Error loading managed resources:", err);
        tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #DC2626; padding: 20px;">Error loading resources.</td></tr>`;
    }
}

function renderManageRow(r) {
    const isYt = r.resource_type === "youtube";
    const typeLabel = r.resource_type.toUpperCase();
    const tagClass = isYt ? "background: #FFEDD5; color: #EA580C;" : (r.resource_type === "pdf" ? "background: #FEE2E2; color: #DC2626;" : "background: #E0E7FF; color: #4338CA;");

    const isPrimary = (r.faculty_category || "PRIMARY").toUpperCase() === "PRIMARY";
    const catHtml = isPrimary 
        ? `<span style="font-size: 11px; font-weight: 700; color: #2563EB; background: #EFF6FF; padding: 3px 8px; border-radius: 6px;">Primary</span>`
        : `<span style="font-size: 11px; font-weight: 700; color: #D97706; background: #FEF3C7; padding: 3px 8px; border-radius: 6px;">Additional ${r.is_important ? '⭐' : ''}</span>`;

    const uploadDate = r.created_at ? new Date(r.created_at).toLocaleDateString() : "";

    return `
        <tr>
            <td>
                <div style="font-weight: 600; color: #1E293B;">${escapeHTML(r.title)}</div>
                <div style="font-size: 11px; color: #64748B;">${escapeHTML(r.subject_code || "")} — ${escapeHTML(r.subject_name || "")}</div>
            </td>
            <td>
                <span class="res-type-badge" style="${tagClass}">
                    ${typeLabel}
                </span>
            </td>
            <td>${catHtml}</td>
            <td style="color: #64748B; font-size: 12px;">${uploadDate}</td>
            <td style="text-align: right;">
                <div style="display: inline-flex; gap: 4px;">
                    ${isYt ? `
                        <a href="${escapeHTML(r.youtube_url)}" target="_blank" class="btn-icon-action" title="Open YouTube Link">
                            <i data-lucide="external-link" style="width: 16px; height: 16px;"></i>
                        </a>
                    ` : `
                        <button type="button" class="btn-icon-action" title="Download File" onclick="downloadTeacherResource(${r.id}, '${escapeHTML(r.original_filename || r.title)}')">
                            <i data-lucide="download" style="width: 16px; height: 16px;"></i>
                        </button>
                    `}
                    <button type="button" class="btn-icon-action" title="Edit" onclick="openEditModal(${r.id})">
                        <i data-lucide="edit-3" style="width: 16px; height: 16px;"></i>
                    </button>
                    <button type="button" class="btn-icon-action btn-icon-delete" title="Delete" onclick="deleteResource(${r.id}, '${escapeHTML(r.title)}')">
                        <i data-lucide="trash-2" style="width: 16px; height: 16px;"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
}

// ==========================================
// EDIT RESOURCE MODAL
// ==========================================
function openEditModal(resourceId) {
    const r = allResources.find(item => item.id === resourceId);
    if (!r) return;

    document.getElementById("editResourceId").value = r.id;
    document.getElementById("editTitle").value = r.title;
    document.getElementById("editDesc").value = r.description || "";

    const impWrapper = document.getElementById("editImportantWrapper");
    const impCheck = document.getElementById("editImportantCheckbox");

    if (r.faculty_category === "ADDITIONAL") {
        impWrapper.style.display = "block";
        impCheck.checked = !!r.is_important;
    } else {
        impWrapper.style.display = "none";
    }

    document.getElementById("editResourceModal").style.display = "flex";
    if (window.lucide) lucide.createIcons();
}

function closeEditModal() {
    document.getElementById("editResourceModal").style.display = "none";
}

async function handleEditSubmit(e) {
    e.preventDefault();
    const id = document.getElementById("editResourceId").value;
    const title = document.getElementById("editTitle").value.trim();
    const description = document.getElementById("editDesc").value.trim();
    const impCheck = document.getElementById("editImportantCheckbox");

    const payload = { title, description };
    if (document.getElementById("editImportantWrapper").style.display !== "none") {
        payload.is_important = impCheck.checked;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/library/teacher/resources/${id}`, {
            method: "PUT",
            headers: authHeaders(),
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || "Failed to update resource.");
        }

        closeEditModal();
        await loadManagedResources();

    } catch (err) {
        alert("Update failed: " + err.message);
    }
}

// ==========================================
// DELETE RESOURCE
// ==========================================
async function deleteResource(id, title) {
    if (!confirm(`Are you sure you want to delete "${title}"?\nThis will also remove it from students' libraries and the AI Copilot knowledge base.`)) {
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/api/library/teacher/resources/${id}`, {
            method: "DELETE",
            headers: authHeaders()
        });

        if (!res.ok) throw new Error("Failed to delete resource.");
        await loadManagedResources();

    } catch (err) {
        alert("Delete failed: " + err.message);
    }
}

async function downloadTeacherResource(id, filename) {
    try {
        const res = await fetch(`${API_BASE_URL}/api/library/teacher/resources/${id}/download`, {
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
        alert("Download error: " + err.message);
    }
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
