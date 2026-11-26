/* ==============================================================================
   CLARIQ — ADMIN LOGIN SCRIPT
   ============================================================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

async function handleAdminLogin(event) {
    event.preventDefault();

    const identifierInput = document.getElementById("adminIdentifier");
    const passwordInput = document.getElementById("adminPassword");
    const submitBtn = document.getElementById("btnLoginSubmit");
    const errorBanner = document.getElementById("errorBanner");

    const identifier = identifierInput.value.trim();
    const password = passwordInput.value;

    if (!identifier || !password) {
        showError("Please enter both username/email and password.");
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Authenticating...</span>`;
    hideError();

    try {
        const response = await fetch(`${API_BASE_URL}/api/admin/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                identifier: identifier,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Authentication failed. Please check credentials.");
        }

        // Store admin token & user data
        const token = data.access_token;
        sessionStorage.setItem("clariqAdminToken", token);
        localStorage.setItem("clariqAdminToken", token);
        if (data.admin) {
            sessionStorage.setItem("clariqAdminUser", JSON.stringify(data.admin));
            localStorage.setItem("clariqAdminUser", JSON.stringify(data.admin));
        }

        // Redirect to admin dashboard
        window.location.href = "dashboard.html";

    } catch (err) {
        showError(err.message);
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Sign In to Admin Panel</span> <i data-lucide="arrow-right" style="width: 16px; height: 16px;"></i>`;
        if (window.lucide) lucide.createIcons();
    }
}

function showError(msg) {
    const errorBanner = document.getElementById("errorBanner");
    if (errorBanner) {
        errorBanner.textContent = msg;
        errorBanner.style.display = "block";
    }
}

function hideError() {
    const errorBanner = document.getElementById("errorBanner");
    if (errorBanner) {
        errorBanner.style.display = "none";
    }
}
