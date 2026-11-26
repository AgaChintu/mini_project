"""
Test suite for Academic Library and AI Copilot modules.
"""
import io
import pytest
from app.models.academic import Subject, AcademicYear, Semester, Section, SectionGroup, SectionGroupMember, SubjectOffering
from app.models.user import Teacher, Student
from app.models.assignment import SubjectTeacherAssignment
from app.models.doubt import Doubt
from app.models.academic_resource import AcademicResource, DoubtCluster, DoubtClusterMember
from app.security import hash_password, create_access_token


@pytest.fixture
def test_setup(db_session):
    # Create Year & Semester
    ay = AcademicYear(name="Year 2 Test", year_number=88, is_active=True)
    db_session.add(ay)
    db_session.flush()

    sem = Semester(academic_year_id=ay.id, semester_number=3, name="Semester III")
    db_session.add(sem)
    db_session.flush()

    sec = Section(academic_year_id=ay.id, semester_id=sem.id, code="SEC-LIB-1", name="Section Library")
    db_session.add(sec)
    db_session.flush()

    sg = SectionGroup(academic_year_id=ay.id, semester_id=sem.id, code="GRP-LIB-1", name="Group Library")
    db_session.add(sg)
    db_session.flush()

    sgm = SectionGroupMember(section_group_id=sg.id, section_id=sec.id)
    db_session.add(sgm)
    db_session.flush()

    subj = Subject(code="CS-LIB-101", name="Data Structures Library", department="CSE", is_active=True)
    db_session.add(subj)
    db_session.flush()

    offering = SubjectOffering(semester_id=sem.id, section_group_id=sg.id, subject_id=subj.id)
    db_session.add(offering)
    db_session.flush()

    # Primary Teacher
    t_primary = Teacher(
        teacher_code="T-PRIM-001",
        full_name="Dr. Primary Professor",
        email="primary@clariq.edu",
        password_hash=hash_password("password123"),
        department="CSE",
        is_active=True,
    )
    db_session.add(t_primary)
    db_session.flush()

    # Additional Teacher
    t_addl = Teacher(
        teacher_code="T-ADDL-002",
        full_name="Prof. Additional Faculty",
        email="additional@clariq.edu",
        password_hash=hash_password("password123"),
        department="CSE",
        is_active=True,
    )
    db_session.add(t_addl)
    db_session.flush()

    # Primary Assignment
    sta_prim = SubjectTeacherAssignment(
        subject_id=subj.id,
        teacher_id=t_primary.id,
        is_primary=True,
        is_active=True,
    )
    db_session.add(sta_prim)

    # Additional Assignment
    sta_addl = SubjectTeacherAssignment(
        subject_id=subj.id,
        teacher_id=t_addl.id,
        is_primary=False,
        is_active=True,
    )
    db_session.add(sta_addl)
    db_session.flush()

    # Student
    stud = Student(
        student_code="S-LIB-001",
        full_name="Anushka Sharma",
        email="student.lib@clariq.edu",
        password_hash=hash_password("password123"),
        section_id=sec.id,
        current_semester=3,
        is_active=True,
    )
    db_session.add(stud)
    db_session.flush()

    # Doubt for clustering
    doubt1 = Doubt(
        doubt_code="DBT-LIB-001",
        student_id=stud.id,
        section_id=sec.id,
        subject_id=subj.id,
        title="How does Binary Search Tree work?",
        question="What is the time complexity of insertion in BST?",
        description="I am confused about worst-case insertion in a binary search tree.",
        status="pending",
    )
    doubt2 = Doubt(
        doubt_code="DBT-LIB-002",
        student_id=stud.id,
        section_id=sec.id,
        subject_id=subj.id,
        title="Binary Search Tree insertion duplicates",
        question="How does duplicate value insertion happen in a binary search tree?",
        description="Can we insert duplicate keys in a BST or do we need a counter?",
        status="pending",
    )
    db_session.add_all([doubt1, doubt2])
    db_session.commit()

    prim_token = create_access_token({"sub": str(t_primary.id), "user_id": t_primary.id, "role": "TEACHER"})
    addl_token = create_access_token({"sub": str(t_addl.id), "user_id": t_addl.id, "role": "TEACHER"})
    stud_token = create_access_token({"sub": str(stud.id), "user_id": stud.id, "role": "STUDENT"})

    return {
        "subj": subj,
        "t_primary": t_primary,
        "t_addl": t_addl,
        "stud": stud,
        "doubt1": doubt1,
        "doubt2": doubt2,
        "prim_token": prim_token,
        "addl_token": addl_token,
        "stud_token": stud_token,
    }


# ==========================================
# LIBRARY TESTS
# ==========================================

def test_teacher_my_subjects(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    res = client.get("/api/library/teacher/subjects", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 1
    assert data[0]["code"] == "CS-LIB-101"
    assert data[0]["faculty_category"] == "PRIMARY"

    # Additional teacher gets ADDITIONAL category
    addl_headers = {"Authorization": f"Bearer {test_setup['addl_token']}"}
    res2 = client.get("/api/library/teacher/subjects", headers=addl_headers)
    assert res2.status_code == 200
    assert res2.json()["data"][0]["faculty_category"] == "ADDITIONAL"


def test_primary_faculty_upload_youtube(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    payload = {
        "subject_id": str(test_setup["subj"].id),
        "title": "Introduction to BST Video Tutorial",
        "description": "Watch this 15 min tutorial before class",
        "resource_type": "youtube",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    res = client.post("/api/library/teacher/resources", data=payload, headers=headers)
    assert res.status_code == 201
    d = res.json()["data"]
    assert d["title"] == "Introduction to BST Video Tutorial"
    assert d["faculty_category"] == "PRIMARY"
    assert d["youtube_video_id"] == "dQw4w9WgXcQ"
    assert d["resource_type"] == "youtube"


def test_additional_faculty_upload_with_important(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['addl_token']}"}
    # Create dummy PDF
    pdf_bytes = b"%PDF-1.4 dummy pdf content for testing"
    files = {
        "document": ("bst_practice_questions.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    data = {
        "subject_id": str(test_setup["subj"].id),
        "title": "BST Solved Question Bank",
        "description": "Important questions for mid-terms",
        "resource_type": "pdf",
        "is_important": "true",
    }
    res = client.post("/api/library/teacher/resources", data=data, files=files, headers=headers)
    assert res.status_code == 201
    d = res.json()["data"]
    assert d["faculty_category"] == "ADDITIONAL"
    assert d["is_important"] is True


def test_student_browse_and_download(client, test_setup):
    # Upload one primary and one additional resource first within this test transaction
    prim_headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    client.post("/api/library/teacher/resources", data={
        "subject_id": str(test_setup["subj"].id),
        "title": "Primary Notes",
        "description": "Core syllabus",
        "resource_type": "youtube",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }, headers=prim_headers)

    addl_headers = {"Authorization": f"Bearer {test_setup['addl_token']}"}
    client.post("/api/library/teacher/resources", data={
        "subject_id": str(test_setup["subj"].id),
        "title": "Additional Solved Problems",
        "description": "Extra practice",
        "resource_type": "youtube",
        "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "is_important": "true",
    }, headers=addl_headers)

    # First, student fetches their subjects
    stud_headers = {"Authorization": f"Bearer {test_setup['stud_token']}"}
    res_subj = client.get("/api/library/student/subjects", headers=stud_headers)
    assert res_subj.status_code == 200
    assert len(res_subj.json()["data"]) >= 1

    # Student fetches resources for the subject
    res_list = client.get(
        f"/api/library/student/resources?subject_id={test_setup['subj'].id}",
        headers=stud_headers
    )
    assert res_list.status_code == 200
    items = res_list.json()["data"]
    assert len(items) >= 2

    # Verify both PRIMARY and ADDITIONAL resources are returned
    categories = {item["faculty_category"] for item in items}
    assert "PRIMARY" in categories
    assert "ADDITIONAL" in categories


# ==========================================
# AI COPILOT TESTS
# ==========================================

def test_copilot_dashboard_stats(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    res = client.get("/api/copilot/dashboard", headers=headers)
    assert res.status_code == 200
    d = res.json()["data"]
    assert d["total_doubts"] >= 2


def test_copilot_process_and_cluster_doubts(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    res = client.post("/api/copilot/process-doubts", headers=headers)
    assert res.status_code == 200

    # Verify clusters list
    res_clusters = client.get("/api/copilot/clusters", headers=headers)
    assert res_clusters.status_code == 200
    clusters = res_clusters.json()["data"]
    assert len(clusters) >= 1
    cluster_id = clusters[0]["id"]

    # Verify cluster detail
    res_detail = client.get(f"/api/copilot/clusters/{cluster_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()["data"]
    assert len(detail["member_doubts"]) >= 1


def test_copilot_generate_answer_and_publish(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}

    # Ensure a cluster exists
    client.post("/api/copilot/process-doubts", headers=headers)
    clusters = client.get("/api/copilot/clusters", headers=headers).json()["data"]
    cluster_id = clusters[0]["id"]

    # 1. Generate answer draft (Groq + RAG)
    res_gen = client.post(f"/api/copilot/clusters/{cluster_id}/generate-answer", headers=headers)
    assert res_gen.status_code == 200
    gen_data = res_gen.json()["data"]
    assert "draft" in gen_data
    assert len(gen_data["draft"]) > 0

    # 2. Save draft
    res_draft = client.post(
        f"/api/copilot/clusters/{cluster_id}/save-draft",
        json={"answer_text": "Teacher edited: In BST, average insertion is O(log n)."},
        headers=headers,
    )
    assert res_draft.status_code == 200

    # 3. Publish answer (Human-in-the-Loop)
    res_pub = client.post(
        f"/api/copilot/clusters/{cluster_id}/publish",
        json={"answer_text": "Verified Answer: Average insertion time is O(log n), worst case O(n) for skewed trees."},
        headers=headers,
    )
    assert res_pub.status_code == 200

    # 4. Verify cluster is marked resolved
    cluster_check = client.get(f"/api/copilot/clusters/{cluster_id}", headers=headers).json()["data"]
    assert cluster_check["status"] == "resolved"
    assert "Average insertion time" in cluster_check["published_answer"]


def test_copilot_priority_override_and_analytics(client, test_setup):
    headers = {"Authorization": f"Bearer {test_setup['prim_token']}"}
    client.post("/api/copilot/process-doubts", headers=headers)
    clusters = client.get("/api/copilot/clusters", headers=headers).json()["data"]
    cluster_id = clusters[0]["id"]

    # Override priority to high
    res_prio = client.put(
        f"/api/copilot/clusters/{cluster_id}/priority",
        json={"priority": "high", "reason": "Mid-term upcoming next week"},
        headers=headers,
    )
    assert res_prio.status_code == 200

    # Check analytics
    res_analytics = client.get("/api/copilot/analytics?days=30", headers=headers)
    assert res_analytics.status_code == 200
    analytics_data = res_analytics.json()["data"]
    assert analytics_data["total_doubts_in_period"] >= 2
    assert "topic_heatmap" in analytics_data
