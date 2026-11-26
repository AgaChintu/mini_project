/* ==========================================
   CLARIQ LOGIN
========================================== */

const API_BASE_URL = "http://127.0.0.1:8000";

const collegeId = document.getElementById("collegeId");
const password = document.getElementById("password");

const togglePassword = document.getElementById("togglePassword");

const loginForm = document.getElementById("loginForm");

const loginBtn = document.getElementById("loginBtn");
const loginBtnText = document.getElementById("loginBtnText");


/* ==========================================
   PASSWORD VISIBILITY
========================================== */

togglePassword.addEventListener("click", function () {

    const hidden = password.type === "password";

    password.type = hidden ? "text" : "password";

    togglePassword.innerHTML = hidden
        ? '<i data-lucide="eye-off"></i>'
        : '<i data-lucide="eye"></i>';

    togglePassword.setAttribute(
        "aria-label",
        hidden ? "Hide password" : "Show password"
    );

    lucide.createIcons();

});


/* ==========================================
   ERROR HANDLING
========================================== */

function showError(input, message) {

    input.classList.add("input-error");

    const error = document.createElement("span");

    error.className = "field-error";
    error.textContent = message;

    input.closest(".form-group").appendChild(error);

}


function clearErrors() {

    document.querySelectorAll(".field-error").forEach(error => {
        error.remove();
    });

    document.querySelectorAll(".input-error").forEach(input => {
        input.classList.remove("input-error");
    });

}


/* ==========================================
   VALIDATION
========================================== */

function validateForm() {

    clearErrors();

    let valid = true;

    if (!collegeId.value.trim()) {

        showError(collegeId, "Please enter your College ID.");

        valid = false;

    }

    if (!password.value.trim()) {

        showError(password, "Please enter your password.");

        valid = false;

    }

    return valid;

}


/* ==========================================
   LOGIN
========================================== */

loginForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    if (!validateForm()) return;

    loginBtn.disabled = true;
    loginBtnText.textContent = "Signing in...";

    try {

        const response = await fetch(
            `${API_BASE_URL}/api/auth/login`,
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    college_id: collegeId.value.trim(),
                    password: password.value
                })
            }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Login failed.");
        }

        // Store the token for both sessionStorage and localStorage
        sessionStorage.setItem("clariqToken", data.access_token);
        localStorage.setItem("clariqToken", data.access_token);

        const userData = {
            id: data.user_id,
            collegeId: data.college_id,
            name: data.name,
            role: data.role,
            department: data.department || "",
            email: data.email || ""
        };

        sessionStorage.setItem("clariqUser", JSON.stringify(userData));
        localStorage.setItem("clariqUser", JSON.stringify(userData));
        localStorage.setItem("clariqStudentId", data.college_id);
        localStorage.setItem("clariqTeacherId", data.college_id);

        // Redirect according to the role returned by the backend.
        if (data.role === "STUDENT") {

            window.location.href = "dashboard.html";

        } else if (data.role === "TEACHER") {

            window.location.href = "../teacher-pages/dashboard.html";

        } else {

            throw new Error("Unknown account role.");

        }

    }

    catch (error) {

        console.error("Login error:", error);

        alert(error.message || "Unable to connect to the server.");

    }

    finally {

        loginBtn.disabled = false;
        loginBtnText.textContent = "Login";

    }

});


/* ==========================================
   CLEAR ERRORS WHILE TYPING
========================================== */

[collegeId, password].forEach(input => {

    input.addEventListener("input", function () {

        input.classList.remove("input-error");

        const error = input.closest(".form-group")
            .querySelector(".field-error");

        if (error) error.remove();

    });

});