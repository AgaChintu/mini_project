/**
 * Frontend Contract & API Integration Test
 * Simulates the exact fetch() calls and payloads from:
 * - student-js/login.js
 * - student-js/dashboard.js
 * - teacher-js/dashboard.js
 * - student-pages/register.html
 */

const API_BASE = "http://127.0.0.1:8000";

async function runFrontendContractTests() {
    console.log("=== STARTING FRONTEND API CONTRACT AUDIT ===");

    // 1. Test Student Login Contract
    console.log("\n[1] Testing Student Login Contract (student-js/login.js)");
    const sLoginRes = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ college_id: "S001", password: "student123" })
    });
    if (!sLoginRes.ok) throw new Error(`Student login failed: ${sLoginRes.status}`);
    const sLoginData = await sLoginRes.json();
    console.log("  Response payload keys:", Object.keys(sLoginData));
    if (!sLoginData.access_token || sLoginData.role !== "STUDENT") {
        throw new Error("Student login contract mismatch");
    }
    const studentToken = sLoginData.access_token;
    console.log("  [PASS] Student Login Contract verified");

    // 2. Test Student Dashboard Contract
    console.log("\n[2] Testing Student Dashboard Contract (student-js/dashboard.js)");
    const sDashRes = await fetch(`${API_BASE}/api/student/dashboard`, {
        headers: { "Authorization": `Bearer ${studentToken}` }
    });
    if (!sDashRes.ok) throw new Error(`Student dashboard failed: ${sDashRes.status}`);
    const sDashData = await sDashRes.json();
    console.log("  Profile full_name:", sDashData.profile?.full_name);
    console.log("  Enrolled subjects count:", sDashData.subjects?.length);
    console.log("  Stats:", sDashData.statistics);
    if (!sDashData.profile || !sDashData.subjects || !sDashData.statistics) {
        throw new Error("Student dashboard response schema mismatch");
    }
    console.log("  [PASS] Student Dashboard Contract verified");

    // 3. Test Student Doubts List Contract
    console.log("\n[3] Testing Student Doubts Retrieval (student-js/dashboard.js)");
    const sDoubtsRes = await fetch(`${API_BASE}/api/student/doubts`, {
        headers: { "Authorization": `Bearer ${studentToken}` }
    });
    if (!sDoubtsRes.ok) throw new Error(`Student doubts retrieval failed: ${sDoubtsRes.status}`);
    const sDoubtsData = await sDoubtsRes.json();
    if (!Array.isArray(sDoubtsData.data)) throw new Error("Student doubts list is not an array");
    console.log("  [PASS] Student Doubts Contract verified");

    // 4. Test Teacher Login Contract
    console.log("\n[4] Testing Teacher Login Contract (teacher-js/dashboard.js)");
    const tLoginRes = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ college_id: "T001", password: "teacher123" })
    });
    if (!tLoginRes.ok) throw new Error(`Teacher login failed: ${tLoginRes.status}`);
    const tLoginData = await tLoginRes.json();
    if (!tLoginData.access_token || tLoginData.role !== "TEACHER") {
        throw new Error("Teacher login contract mismatch");
    }
    const teacherToken = tLoginData.access_token;
    console.log("  [PASS] Teacher Login Contract verified");

    // 5. Test Teacher Dashboard Contract
    console.log("\n[5] Testing Teacher Dashboard Contract (teacher-js/dashboard.js)");
    const tDashRes = await fetch(`${API_BASE}/api/teacher/dashboard`, {
        headers: { "Authorization": `Bearer ${teacherToken}` }
    });
    if (!tDashRes.ok) throw new Error(`Teacher dashboard failed: ${tDashRes.status}`);
    const tDashData = await tDashRes.json();
    console.log("  Profile full_name:", tDashData.profile?.full_name);
    console.log("  Assigned subjects count:", tDashData.assigned_subjects?.length);
    console.log("  Stats:", tDashData.statistics);
    if (!tDashData.profile || !tDashData.assigned_subjects || !tDashData.statistics) {
        throw new Error("Teacher dashboard response schema mismatch");
    }
    console.log("  [PASS] Teacher Dashboard Contract verified");

    // 6. Test Teacher Assigned Subject Doubts & AI Clustering Contract
    const firstSubj = tDashData.assigned_subjects[0];
    if (firstSubj) {
        console.log(`\n[6] Testing Subject Doubts & Clusters Contract for Subject ${firstSubj.id}`);
        const tSubjDoubtsRes = await fetch(`${API_BASE}/api/teacher/subjects/${firstSubj.id}/doubts`, {
            headers: { "Authorization": `Bearer ${teacherToken}` }
        });
        if (!tSubjDoubtsRes.ok) throw new Error(`Teacher subject doubts failed: ${tSubjDoubtsRes.status}`);
        const tSubjDoubtsData = await tSubjDoubtsRes.json();
        console.log("  Subject:", tSubjDoubtsData.subject?.name);
        console.log("  AI Overview:", tSubjDoubtsData.ai_overview);
        console.log("  Clusters count:", tSubjDoubtsData.clusters?.length);
        if (!tSubjDoubtsData.subject || !tSubjDoubtsData.clusters) {
            throw new Error("Teacher subject doubts schema mismatch");
        }
        console.log("  [PASS] Teacher Subject Doubts Contract verified");
    }

    // 7. Test Teacher Registration Authorization Key Requirement
    console.log("\n[7] Testing Teacher Registration Authorization Key Enforcement (register.html)");
    // A. Without key / with invalid key
    const badRegRes = await fetch(`${API_BASE}/api/auth/teacher/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            full_name: "Test Faculty",
            email: "invalid.test@faculty.edu",
            password: "password123",
            confirm_password: "password123",
            department: "Computer Science",
            designation: "Assistant Professor",
            faculty_invite_code: "WRONG_KEY"
        })
    });
    if (badRegRes.status !== 403) {
        throw new Error(`Expected 403 Forbidden for bad key, got ${badRegRes.status}`);
    }
    console.log("  Invalid key correctly rejected with HTTP 403");
    console.log("  [PASS] Teacher Registration Authorization Key verified");

    console.log("\n=== ALL FRONTEND CONTRACT TESTS PASSED 100% ===\n");
}

runFrontendContractTests().catch(err => {
    console.error("CONTRACT AUDIT ERROR:", err);
    process.exit(1);
});
