/* ==============================================================================
   CLARIQ — STUDENT DOUBT DETAILS SCRIPT
   Live integration with FastAPI backend & Supabase PostgreSQL
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

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

const params = new URLSearchParams(window.location.search);
const doubtId = params.get("id");

document.addEventListener("DOMContentLoaded", async () => {
    if (!checkAuth()) return;
    if (!doubtId) {
        alert("No doubt specified.");
        window.location.href = "my-doubts.html";
        return;
    }

    await loadStudentProfile();
    await loadDoubtDetails();

    if (window.lucide) lucide.createIcons();
});

async function loadStudentProfile() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/student/dashboard`, {
            headers: authHeaders()
        });
        if (response.ok) {
            const data = await response.json();
            const p = data.profile;
            const nameEl = document.getElementById("detailTopName");
            const avatarEl = document.getElementById("detailTopAvatar");
            if (nameEl) nameEl.textContent = p.full_name;
            if (avatarEl) avatarEl.textContent = p.full_name.charAt(0).toUpperCase();
        }
    } catch (err) {
        console.error("Profile load error:", err);
    }
}

async function loadDoubtDetails() {
    const subjectEl = document.getElementById("doubtSubject");
    const questionEl = document.getElementById("doubtQuestion");
    const descEl = document.getElementById("doubtDescription");
    const tagsEl = document.getElementById("doubtTags");
    const facultyNameEl = document.getElementById("assignedFacultyName");
    const facultyDeptEl = document.getElementById("assignedFacultyDept");
    const answerContentEl = document.getElementById("verifiedAnswerContent");

    try {
        const response = await fetch(`${API_BASE_URL}/api/student/doubts/${doubtId}`, {
            headers: authHeaders()
        });

        if (!response.ok) {
            throw new Error("Unable to retrieve doubt from server.");
        }

        const res = await response.json();
        const d = res.data;

        if (subjectEl) subjectEl.textContent = d.subject ? `${d.subject.code || ''} — ${d.subject.name}` : "Subject";
        if (questionEl) questionEl.textContent = d.title || d.description;
        if (descEl) descEl.textContent = d.description || "";

        if (tagsEl) {
            const isResolved = d.status === "resolved";
            tagsEl.innerHTML = `
                <span class="doubt-tag" style="background: ${isResolved ? '#DCFCE7' : '#FEF3C7'}; color: ${isResolved ? '#166534' : '#92400E'}; font-weight: 700;">
                    ${isResolved ? 'Resolved' : 'Pending Review'}
                </span>
                <span class="doubt-tag">ID: ${escapeHTML(d.doubt_code)}</span>
                <span class="doubt-tag">Submitted ${d.created_at ? new Date(d.created_at).toLocaleDateString('en-IN') : ''}</span>
            `;
        }

        if (facultyNameEl) {
            facultyNameEl.textContent = d.assigned_teacher ? d.assigned_teacher.name : "Primary Faculty (Auto-assigned)";
        }
        if (facultyDeptEl) {
            facultyDeptEl.textContent = d.assigned_teacher ? `${d.assigned_teacher.department} • ${d.assigned_teacher.designation || 'Faculty'}` : "Assigned Department Faculty";
        }

        if (answerContentEl) {
            if (d.verified_answers && d.verified_answers.length > 0) {
                answerContentEl.innerHTML = d.verified_answers.map(ans => `
                    <div style="background: #ECFDF5; border-left: 4px solid #10B981; padding: 16px 20px; border-radius: 0 10px 10px 0;">
                        <div style="display: flex; align-items: center; gap: 8px; color: #047857; font-weight: 700; margin-bottom: 8px;">
                            <i data-lucide="badge-check" style="width: 18px; height: 18px;"></i>
                            <span>Verified Answer by ${escapeHTML(ans.teacher_name)}</span>
                        </div>
                        <p style="margin: 0 0 10px; color: #065F46; line-height: 1.6; font-size: 15px; white-space: pre-wrap;">${escapeHTML(ans.answer_text)}</p>
                        ${ans.resource_url ? `<a href="${escapeHTML(ans.resource_url)}" target="_blank" style="display:inline-block; color:#2563EB; font-weight:600; font-size:13px;">View External Resource &rarr;</a>` : ''}
                        <div style="font-size: 12px; color: #059669; margin-top: 10px;">Answer published on ${ans.created_at ? new Date(ans.created_at).toLocaleString('en-IN') : ''}</div>
                    </div>
                `).join("");
            } else {
                answerContentEl.innerHTML = `
                    <div style="background: #F8FAFC; border: 1px dashed #CBD5E1; border-radius: 12px; padding: 24px; text-align: center; color: #64748B;">
                        <i data-lucide="clock" style="width: 28px; height: 28px; color: #D97706; margin-bottom: 8px;"></i>
                        <h4 style="font-size: 15px; font-weight: 600; color: #334155; margin: 0 0 4px;">Awaiting Faculty Verification</h4>
                        <p style="font-size: 13px; margin: 0;">This doubt has been delivered to your faculty. Answers will appear here once verified.</p>
                    </div>
                `;
            }
        }

        if (window.lucide) lucide.createIcons();

    } catch (err) {
        if (questionEl) questionEl.textContent = `Error: ${err.message}`;
    }
}

function escapeHTML(str) {
    return String(str ?? "").replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
    })[c]);
}
