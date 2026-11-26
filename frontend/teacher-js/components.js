// ==============================================================================
// CLARIQ — TEACHER SHARED COMPONENTS (SIDEBAR & TOPBAR)
// ==============================================================================

function applyTeacherTopbarProfile(name) {
    const cleanName = (name || "").trim();
    if (!cleanName) return;

    const navName = document.getElementById("tNavName");
    const navAvatar = document.getElementById("tNavAvatar");
    if (navName) navName.textContent = cleanName;
    if (navAvatar) navAvatar.textContent = cleanName.charAt(0).toUpperCase();
}

async function populateTeacherTopbar() {
    // 1. Apply cached teacher profile immediately (no UI flicker)
    try {
        const rawUser = sessionStorage.getItem("clariqUser") || localStorage.getItem("clariqUser");
        if (rawUser) {
            const parsed = JSON.parse(rawUser);
            if (parsed) {
                const teacherName = parsed.full_name || parsed.name || "";
                if (teacherName) applyTeacherTopbarProfile(teacherName);
            }
        }
    } catch (e) {
        // Ignore parse error
    }

    // 2. Refresh from backend to guarantee up-to-date faculty name
    const token = sessionStorage.getItem("clariqToken") || localStorage.getItem("clariqToken");
    if (!token) return;

    try {
        const apiBase = window.location.hostname === "localhost" ? "http://localhost:8000" : "http://127.0.0.1:8000";
        const res = await fetch(`${apiBase}/api/teacher/dashboard`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        if (!res.ok) return;
        const data = await res.json();
        const profile = data.profile || (data.data && data.data.profile);
        if (profile && profile.full_name) {
            applyTeacherTopbarProfile(profile.full_name);
        }
    } catch (e) {
        // Ignore background network errors if cached name is already shown
    }
}

// Active page highlighting in sidebar
function initializeSidebar() {
    const currentPage = window.location.pathname.split("/").pop();
    const navLinks = document.querySelectorAll(".sidebar a");
    navLinks.forEach(link => {
        const linkPage = link.getAttribute("href");
        if (linkPage === currentPage) {
            link.classList.add("nav-item-active");
        }
    });
}

function initSharedComponents() {
    // 1. Sidebar
    const sidebarContainer = document.getElementById("sidebar-container");
    if (sidebarContainer) {
        fetch("../components/teacher-sidebar.html", { cache: "no-store" })
            .then(res => res.text())
            .then(html => {
                sidebarContainer.innerHTML = html;
                initializeSidebar();
                if (window.lucide) lucide.createIcons();
            })
            .catch(err => console.error("Error loading sidebar:", err));
    }

    // 2. Topbar
    const topbarContainer = document.getElementById("topbar-container");
    if (topbarContainer) {
        fetch("../components/teacher-topbar.html", { cache: "no-store" })
            .then(res => res.text())
            .then(html => {
                topbarContainer.innerHTML = html;
                if (window.lucide) lucide.createIcons();
                populateTeacherTopbar();
            })
            .catch(err => console.error("Error loading topbar:", err));
    } else {
        // If page has inline topbar (e.g. dashboard.html), populate directly
        populateTeacherTopbar();
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSharedComponents);
} else {
    initSharedComponents();
}
