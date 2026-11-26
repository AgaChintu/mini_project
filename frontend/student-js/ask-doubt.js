/* ==============================================================================
   CLARIQ — ASK DOUBT SCRIPT
   Live integration with FastAPI backend & dynamic faculty selection
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

// Track selected attachment files
let attachmentFiles = [];

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

document.addEventListener("DOMContentLoaded", async () => {
    if (!checkAuth()) return;

    setupFormControls();
    setupAttachmentHandlers();
    await loadEnrolledSubjects();

    if (window.lucide) lucide.createIcons();
});

function setupFormControls() {
    const titleInput = document.querySelector(".title-textarea");
    const descInput = document.querySelector(".description-textarea");
    const countEl = document.querySelector(".character-count");
    const subjSelect = document.querySelector(".select-subj");
    const submitBtn = document.querySelector(".submit-button");

    if (descInput && countEl) {
        descInput.addEventListener("input", () => {
            countEl.textContent = `${descInput.value.length}/1000`;
        });
    }

    if (subjSelect) {
        subjSelect.addEventListener("change", async () => {
            const subjectId = subjSelect.value;
            await loadTeachersForSubject(subjectId);
        });
    }

    if (submitBtn) {
        submitBtn.addEventListener("click", handleSubmitDoubt);
    }
}

function setupAttachmentHandlers() {
    const fileInput = document.getElementById("attachment");
    const uploadBox = document.querySelector(".upload-box");
    const previewList = document.querySelector(".attachment-preview-list");

    if (!fileInput) return;

    // File input change
    fileInput.addEventListener("change", () => {
        for (const f of fileInput.files) {
            addFile(f);
        }
        fileInput.value = "";
    });

    // Drag-and-drop on upload box
    if (uploadBox) {
        uploadBox.addEventListener("dragover", (e) => {
            e.preventDefault();
            uploadBox.style.borderColor = "#4965E8";
            uploadBox.style.background = "#EEF2FF";
        });
        uploadBox.addEventListener("dragleave", () => {
            uploadBox.style.borderColor = "";
            uploadBox.style.background = "";
        });
        uploadBox.addEventListener("drop", (e) => {
            e.preventDefault();
            uploadBox.style.borderColor = "";
            uploadBox.style.background = "";
            for (const f of e.dataTransfer.files) {
                addFile(f);
            }
        });
    }

    function addFile(file) {
        const allowed = ["image/png", "image/jpeg", "application/pdf"];
        if (!allowed.includes(file.type)) {
            alert(`"${file.name}" is not supported. Please upload PNG, JPG, or PDF only.`);
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            alert(`"${file.name}" exceeds the 10 MB limit.`);
            return;
        }
        // Avoid duplicate filenames
        if (attachmentFiles.some(f => f.name === file.name && f.size === file.size)) return;
        attachmentFiles.push(file);
        renderPreviews();
    }

    function renderPreviews() {
        if (!previewList) return;
        if (attachmentFiles.length === 0) {
            previewList.innerHTML = "";
            return;
        }
        previewList.innerHTML = attachmentFiles.map((f, i) => {
            const isImg = f.type.startsWith("image/");
            const icon = isImg ? "🖼️" : "📄";
            const sizeMB = (f.size / (1024 * 1024)).toFixed(2);
            return `
                <div class="attachment-preview" style="display:inline-flex; align-items:center; gap:8px; background:#F1F5F9; border:1px solid #CBD5E1; border-radius:8px; padding:6px 10px; margin:4px 4px 4px 0; font-size:13px;">
                    <span>${icon}</span>
                    <span style="max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHTML(f.name)}</span>
                    <span style="color:#94A3B8; font-size:11px;">${sizeMB} MB</span>
                    <button type="button" onclick="removeAttachment(${i})" style="background:none; border:none; cursor:pointer; color:#EF4444; font-size:16px; line-height:1; padding:0 2px;" title="Remove">×</button>
                </div>
            `;
        }).join("");
    }

    // expose renderPreviews so removeAttachment can call it
    window._renderAttachmentPreviews = renderPreviews;
}

function removeAttachment(index) {
    attachmentFiles.splice(index, 1);
    if (window._renderAttachmentPreviews) window._renderAttachmentPreviews();
}

async function loadEnrolledSubjects() {
    const subjSelect = document.querySelector(".select-subj");
    if (!subjSelect) return;

    subjSelect.innerHTML = `<option value="" disabled selected>Loading subjects...</option>`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/subjects`, {
            headers: authHeaders()
        });

        if (!response.ok) {
            throw new Error("Failed to load subjects.");
        }

        const res = await response.json();
        const subjects = res.data || [];
        const warning = res.warning || null;

        if (warning) {
            // Show semester unassigned warning banner above form if exists
            const warningBanner = document.getElementById("semesterWarningBanner");
            if (warningBanner) {
                warningBanner.style.display = "block";
                warningBanner.innerHTML = `<strong>⚠ Semester Not Assigned:</strong> ${warning}`;
            }
            subjSelect.innerHTML = `<option value="" disabled selected>No subjects — semester not assigned</option>`;
            const submitBtn = document.querySelector(".submit-button");
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        if (subjects.length === 0) {
            subjSelect.innerHTML = `<option value="" disabled selected>No subjects assigned to your semester</option>`;
            return;
        }

        let options = `<option value="" disabled selected>Select subject (Semester ${subjects[0].semester_number || ""})</option>`;
        subjects.forEach(s => {
            options += `<option value="${s.id}">${escapeHTML(s.code)} — ${escapeHTML(s.name)}</option>`;
        });
        subjSelect.innerHTML = options;

        // Preselect subject if ?subject_id= is provided in URL
        const preselectedId = new URLSearchParams(window.location.search).get("subject_id");
        if (preselectedId && subjects.some(s => String(s.id) === String(preselectedId))) {
            subjSelect.value = String(preselectedId);
            await loadTeachersForSubject(preselectedId);
        }

    } catch (err) {
        console.error("Failed to load subjects:", err);
        subjSelect.innerHTML = `<option value="" disabled selected>Error loading subjects</option>`;
    }
}

async function loadTeachersForSubject(subjectId) {
    const teacherSection = document.querySelector(".teacher-section");
    const teacherSelect = document.querySelector(".select-teacher");
    if (!teacherSection || !teacherSelect) return;

    if (!subjectId) {
        teacherSection.hidden = true;
        return;
    }

    teacherSection.hidden = false;
    teacherSelect.innerHTML = `<option value="">Loading faculty list...</option>`;

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/subjects/${subjectId}/teachers`, {
            headers: authHeaders()
        });

        if (!response.ok) throw new Error("Could not load faculty.");

        const res = await response.json();
        const teachers = res.data || [];

        if (teachers.length === 0) {
            teacherSelect.innerHTML = `<option value="">No faculty assigned to this subject yet</option>`;
            teacherSection.hidden = true;
            return;
        }

        // Find primary teacher
        const primaryT = teachers.find(t => t.is_primary);
        const addlTeachers = teachers.filter(t => !t.is_primary);

        let options = "";
        if (primaryT) {
            // Default routes to primary
            options += `<option value="">Default — ${escapeHTML(primaryT.full_name)} (Primary Faculty)</option>`;
            options += `<option value="${primaryT.id}">${escapeHTML(primaryT.full_name)} (Primary Faculty)</option>`;
        } else {
            options += `<option value="">Default (Assigned Primary Faculty)</option>`;
        }

        addlTeachers.forEach(t => {
            options += `<option value="${t.id}">${escapeHTML(t.full_name)} (Additional Faculty)</option>`;
        });

        teacherSelect.innerHTML = options;

    } catch (err) {
        console.error("Error loading teachers:", err);
        teacherSelect.innerHTML = `<option value="">Default (Assigned Primary Faculty)</option>`;
    }
}

async function handleSubmitDoubt(e) {
    if (e) e.preventDefault();

    const titleInput = document.querySelector(".title-textarea");
    const descInput = document.querySelector(".description-textarea");
    const subjSelect = document.querySelector(".select-subj");
    const teacherSelect = document.querySelector(".select-teacher");
    const submitBtn = document.querySelector(".submit-button");

    const title = titleInput ? titleInput.value.trim() : "";
    const description = descInput ? descInput.value.trim() : "";
    const subjectId = subjSelect ? parseInt(subjSelect.value) : null;
    const teacherId = teacherSelect && teacherSelect.value ? parseInt(teacherSelect.value) : null;

    if (!subjectId || isNaN(subjectId)) {
        alert("Please select a subject.");
        if (subjSelect) subjSelect.focus();
        return;
    }

    if (!title || title.length < 4) {
        alert("Please enter a short descriptive title (minimum 4 characters).");
        if (titleInput) titleInput.focus();
        return;
    }

    if (!description || description.length < 10) {
        alert("Please describe your question in detail (minimum 10 characters).");
        if (descInput) descInput.focus();
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `Submitting Anonymously... <i data-lucide="loader-2" class="spin"></i>`;
    }

    try {
        // Build FormData for /api/student/doubts (supports optional file attachments + semester/AI pipeline)
        const formData = new FormData();
        formData.append("title", title);
        formData.append("description", description);
        formData.append("subject_id", subjectId.toString());
        if (teacherId) {
            formData.append("teacher_id", teacherId.toString());
        }

        // Attach selected files (PNG, JPG, PDF)
        for (const f of attachmentFiles) {
            formData.append("files", f);
        }

        const response = await fetch(`${API_BASE_URL}/api/student/doubts`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${getAuthToken()}`
                // No Content-Type: browser sets multipart boundary automatically
            },
            body: formData
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Failed to submit doubt.");
        }

        const attachMsg = attachmentFiles.length > 0 ? ` (${attachmentFiles.length} file${attachmentFiles.length > 1 ? "s" : ""} attached)` : "";
        alert(`Doubt submitted successfully${attachMsg}! Your question has been routed anonymously to your faculty.`);
        window.location.href = "my-doubts.html";

    } catch (err) {
        alert(err.message || "An error occurred while submitting doubt.");
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = `Submit Doubt <i data-lucide="arrow-right"></i>`;
            if (window.lucide) lucide.createIcons();
        }
    }
}

function getSelectedSubtopicIds() {
    // Try to read selected topic chips if the topic selector is present
    const chips = document.querySelectorAll(".topic-chips [data-subtopic-id]");
    if (chips && chips.length > 0) {
        return Array.from(chips).map(c => c.dataset.subtopicId).filter(Boolean);
    }
    return [];
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
