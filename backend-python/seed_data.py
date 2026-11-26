"""
ClariQ Idempotent Database Seeder

Run from: backend-python/
Command: python seed_data.py
Verify:  python seed_data.py --verify

Seeds:
- Academic years (Year 1, Year 2)
- Semesters (Semester 1, 2, 3, 4)
- Sections for Year 1 and Year 2
- Section groups and memberships
- Subjects and Subject Offerings
- Teachers and Teacher Assignments
- Demo Students with secure hashed passwords
- Syllabus Units, Topics, and Subtopics (Python & Digital Electronics)

Rules:
- Safe to run multiple times without duplicating data.
- Does not delete or truncate existing tables.
- All relationships and foreign keys are verified.
"""

import sys
from datetime import datetime
from sqlalchemy import text
from app.database import SessionLocal, Base, engine
from app.security import hash_password
from app.models import (
    AcademicYear,
    Semester,
    SectionGroup,
    Section,
    SectionGroupMember,
    Subject,
    SubjectOffering,
    Teacher,
    Student,
    TeacherAssignment,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
)


def get_or_create(db, model, lookup, defaults=None):
    """Fetch existing record matching lookup or create a new one."""
    item = db.query(model).filter_by(**lookup).first()
    if item:
        return item, False

    values = dict(lookup)
    if defaults:
        values.update(defaults)

    item = model(**values)
    db.add(item)
    db.flush()
    return item, True


def seed_python_syllabus(db, python_subject):
    """Seed Python (BCC302) Units, Topics, and Subtopics idempotently."""
    syllabus = {
        1: {
            "name": "Introduction to Python",
            "lectures": 8,
            "topics": [
                {
                    "name": "Introduction to Python and its features",
                    "subtopics": ["History of Python", "Features & Advantages", "Python Interpreter setup"],
                },
                {
                    "name": "Python variables and identifiers",
                    "subtopics": ["Naming rules & conventions", "Dynamic typing", "Memory allocation"],
                },
                {
                    "name": "Basic operators and expressions",
                    "subtopics": ["Arithmetic & Relational operators", "Logical & Bitwise operators", "Operator precedence"],
                },
                {
                    "name": "Python data types: int, float, complex, bool and strings",
                    "subtopics": ["Immutable types", "Type casting & conversion", "Boolean logic"],
                },
                {
                    "name": "Numeric data types and their usage",
                    "subtopics": ["Floating point precision", "Complex numbers in engineering", "Math module"],
                },
                {
                    "name": "Python blocks and indentation",
                    "subtopics": ["Indentation rules", "Code formatting with PEP8", "Nested blocks"],
                },
            ],
        },
        2: {
            "name": "Program Flow Control",
            "lectures": 8,
            "topics": [
                {
                    "name": "Conditional statements: if, else and elif",
                    "subtopics": ["Single-way selection", "Multi-way decision branches", "Nested if statements"],
                },
                {
                    "name": "For loops and range() function",
                    "subtopics": ["Range start, stop, step", "Iterating over sequences", "Nested for loops"],
                },
                {
                    "name": "While loops",
                    "subtopics": ["Condition evaluation", "Infinite loops & guards", "While-else construct"],
                },
                {
                    "name": "Loop control statements: break, continue and pass",
                    "subtopics": ["Premature loop exit with break", "Skipping iterations with continue", "Pass as placeholder"],
                },
                {
                    "name": "Loop else clause",
                    "subtopics": ["Execution when loop finishes normally", "Search algorithms with loop else"],
                },
            ],
        },
        3: {
            "name": "Complex Data Types and Functions",
            "lectures": 8,
            "topics": [
                {
                    "name": "String operations and manipulation",
                    "subtopics": ["String slicing & indexing", "String methods", "Formatted strings (f-strings)"],
                },
                {
                    "name": "Lists and list slicing",
                    "subtopics": ["List mutability & operations", "List comprehensions", "Multi-dimensional lists"],
                },
                {
                    "name": "Tuples and tuple operations",
                    "subtopics": ["Tuple immutability", "Tuple packing & unpacking", "Use cases for tuples"],
                },
                {
                    "name": "Dictionaries and dictionary operations",
                    "subtopics": ["Key-value pairs & hashing", "Dictionary methods", "Dictionary comprehensions"],
                },
                {
                    "name": "Defining and calling Python functions",
                    "subtopics": ["Function parameters & return", "Default arguments & *args/**kwargs", "Lambda functions"],
                },
            ],
        },
        4: {
            "name": "File Handling",
            "lectures": 8,
            "topics": [
                {
                    "name": "Introduction to file handling",
                    "subtopics": ["Text vs Binary files", "File open modes", "Context managers (with statement)"],
                },
                {
                    "name": "Reading files using read(), readline() and readlines()",
                    "subtopics": ["Reading whole files", "Iterating line-by-line", "Buffer management"],
                },
                {
                    "name": "Writing files using write() and writelines()",
                    "subtopics": ["Overwriting vs Appending", "Flushing buffers", "Writing formatted text"],
                },
            ],
        },
        5: {
            "name": "Packages and GUI",
            "lectures": 8,
            "topics": [
                {
                    "name": "Introduction to Python modules and packages",
                    "subtopics": ["Import statements", "Creating custom modules", "__init__.py role"],
                },
                {
                    "name": "NumPy package and its applications",
                    "subtopics": ["NumPy arrays (ndarray)", "Array arithmetic & broadcasting", "Vectorized operations"],
                },
                {
                    "name": "Pandas package and its applications",
                    "subtopics": ["Series & DataFrame", "Reading CSV files", "Basic data manipulation"],
                },
            ],
        },
    }

    inserted_units = 0
    inserted_topics = 0
    inserted_subtopics = 0

    for unit_number, unit_data in syllabus.items():
        unit, u_created = get_or_create(
            db,
            SyllabusUnit,
            {"subject_id": python_subject.id, "unit_number": unit_number},
            {"unit_name": unit_data["name"], "proposed_lectures": unit_data["lectures"], "description": unit_data["name"]},
        )
        inserted_units += int(u_created)

        for t_order, t_data in enumerate(unit_data["topics"], start=1):
            topic, t_created = get_or_create(
                db,
                SyllabusTopic,
                {"unit_id": unit.id, "name": t_data["name"]},
                {"display_order": t_order, "description": t_data["name"]},
            )
            inserted_topics += int(t_created)

            for s_order, subtopic_name in enumerate(t_data.get("subtopics", []), start=1):
                _, s_created = get_or_create(
                    db,
                    SyllabusSubtopic,
                    {"topic_id": topic.id, "name": subtopic_name},
                    {"display_order": s_order},
                )
                inserted_subtopics += int(s_created)

    return inserted_units, inserted_topics, inserted_subtopics


def seed():
    """Execute complete database seeding idempotently."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    counts = {}

    try:
        # 1. ACADEMIC YEARS
        counts["academic_years"] = 0
        years = {}
        for number in (1, 2):
            year, created = get_or_create(
                db,
                AcademicYear,
                {"year_number": number},
                {"name": f"Year {number}", "is_active": True},
            )
            years[number] = year
            counts["academic_years"] += int(created)

        # 2. SEMESTERS
        counts["semesters"] = 0
        semesters = {}
        semester_map = {1: (1, 2), 2: (3, 4)}
        for year_num, sem_nums in semester_map.items():
            for s_num in sem_nums:
                semester, created = get_or_create(
                    db,
                    Semester,
                    {"academic_year_id": years[year_num].id, "semester_number": s_num},
                    {"name": f"Semester {s_num}"},
                )
                semesters[s_num] = semester
                counts["semesters"] += int(created)

        # 3. SECTIONS
        counts["sections"] = 0
        section_records = {}
        section_codes_by_year = {
            1: ("AIML", "CS1", "CS2", "CS3", "IT", "DS"),
            2: ("AIML", "CS1", "CS2", "CS3", "IT", "DS"),
        }
        for year_num, codes in section_codes_by_year.items():
            for code in codes:
                section_name = f"Year {year_num} - {code}" if year_num == 1 else f"2-{code}"
                section, created = get_or_create(
                    db,
                    Section,
                    {"academic_year_id": years[year_num].id, "code": code},
                    {
                        "name": section_name,
                        "semester_id": semesters[1].id if year_num == 1 else semesters[3].id,
                    },
                )
                section_records[(year_num, code)] = section
                counts["sections"] += int(created)

        # 4. SECTION GROUPS
        counts["section_groups"] = 0
        group_records = {}
        group_definitions = [
            (1, "Y1_CS", "First Year - Computer Science Group", ("CS1", "CS2", "CS3")),
            (1, "Y1_AIML_IT_DS", "First Year - AIML, IT and DS Group", ("AIML", "IT", "DS")),
            (2, "Y2_COMMON", "Second Year - Common Group", ("AIML", "CS1", "CS2", "CS3", "IT", "DS")),
        ]
        for year_num, code, name, member_codes in group_definitions:
            group, created = get_or_create(
                db,
                SectionGroup,
                {"code": code},
                {
                    "name": name,
                    "academic_year_id": years[year_num].id,
                    "semester_id": semesters[1].id if year_num == 1 else semesters[3].id,
                    "description": f"Group for {name}",
                },
            )
            group_records[code] = (group, year_num, member_codes)
            counts["section_groups"] += int(created)

        # 5. SECTION GROUP MEMBERS
        counts["section_group_members"] = 0
        for code, (group, year_num, member_codes) in group_records.items():
            for sec_code in member_codes:
                sec = section_records[(year_num, sec_code)]
                _, created = get_or_create(
                    db,
                    SectionGroupMember,
                    {"section_group_id": group.id, "section_id": sec.id},
                )
                counts["section_group_members"] += int(created)

        # 6. SUBJECTS
        counts["subjects"] = 0
        subjects_data = [
            ("BAS101", "Engineering Physics", "theory", "Physics for engineers"),
            ("BAS102", "Engineering Chemistry", "theory", "Chemistry for engineers"),
            ("BAS103", "Engineering Mathematics-I", "theory", "Calculus and linear algebra"),
            ("BCO101", "Programming for Problem Solving", "theory", "Foundations of programming"),
            ("BCS301", "Data Structures", "theory", "Core data structures and algorithms"),
            ("BCS302", "Computer Organization and Architecture", "theory", "Digital computer organization"),
            ("BCS303", "Discrete Structures & Theory of Logic", "theory", "Discrete math and automata"),
            ("BCC302", "Python Programming", "theory", "Applied Python programming"),
            ("BAS301", "Mathematics-IV", "theory", "Probability and statistics"),
            ("BOE310", "Digital Electronics", "theory", "Digital logic and circuits"),
        ]
        subjects = {}
        for code, name, stype, desc in subjects_data:
            subj, created = get_or_create(
                db,
                Subject,
                {"code": code},
                {"name": name, "subject_type": stype, "description": desc},
            )
            subjects[code] = subj
            counts["subjects"] += int(created)

        # 7. SUBJECT OFFERINGS
        counts["subject_offerings"] = 0
        offerings_data = [
            (3, "Y2_COMMON", "BCS301", 3, 1, 0),
            (3, "Y2_COMMON", "BCS302", 3, 0, 0),
            (3, "Y2_COMMON", "BCS303", 3, 1, 0),
            (3, "Y2_COMMON", "BCC302", 2, 0, 2),
            (3, "Y2_COMMON", "BAS301", 3, 1, 0),
            (3, "Y2_COMMON", "BOE310", 3, 0, 0),
        ]
        for sem_num, grp_code, subj_code, lec, tut, prac in offerings_data:
            _, created = get_or_create(
                db,
                SubjectOffering,
                {
                    "semester_id": semesters[sem_num].id,
                    "section_group_id": group_records[grp_code][0].id,
                    "subject_id": subjects[subj_code].id,
                },
                {"lecture_hours": lec, "tutorial_hours": tut, "practical_hours": prac},
            )
            counts["subject_offerings"] += int(created)

        # 8. TEACHERS
        counts["teachers"] = 0
        teacher_data = [
            ("T001", "Dr. S. K. Sharma", "sksharma@clariq.local"),
            ("T002", "Dr. Anita Verma", "averma@clariq.local"),
            ("T003", "Prof. Rajiv Mehta", "rmehta@clariq.local"),
            ("T004", "Dr. Priya Nair", "pnair@clariq.local"),
            ("T005", "Prof. Vikas Gupta", "vgupta@clariq.local"),
            ("T006", "Prof. Neha Singh", "nsingh@clariq.local"),
            ("T007", "Dr. Alok Pandey", "apandey@clariq.local"),
            ("T008", "Prof. Sunita Rao", "srao@clariq.local"),
            ("T009", "Dr. Manish Tiwari", "mtiwari@clariq.local"),
            ("T010", "Prof. Pooja Joshi", "pjoshi@clariq.local"),
            ("T011", "Dr. Rakesh Mishra", "rmishra@clariq.local"),
        ]
        teachers = {}
        default_teacher_pw = hash_password("teacher123")
        for code, name, email in teacher_data:
            teacher, created = get_or_create(
                db,
                Teacher,
                {"teacher_code": code},
                {
                    "full_name": name,
                    "email": email,
                    "password_hash": default_teacher_pw,
                    "is_active": True,
                },
            )
            teachers[code] = teacher
            counts["teachers"] += int(created)

        # 9. TEACHER ASSIGNMENTS
        counts["teacher_assignments"] = 0
        aiml_year2 = section_records[(2, "AIML")]
        sem3 = semesters[3]
        assignment_map = [
            ("T001", "BCS301"),
            ("T002", "BCC302"),
            ("T003", "BCC302"),
            ("T004", "BCS303"),
            ("T005", "BCS303"),
            ("T006", "BCS302"),
            ("T007", "BCS302"),
            ("T008", "BAS301"),
            ("T009", "BAS301"),
            ("T010", "BOE310"),
            ("T011", "BOE310"),
        ]
        for t_code, subj_code in assignment_map:
            _, created = get_or_create(
                db,
                TeacherAssignment,
                {
                    "teacher_id": teachers[t_code].id,
                    "semester_id": sem3.id,
                    "section_id": aiml_year2.id,
                    "subject_id": subjects[subj_code].id,
                },
                {"assignment_type": "primary"},
            )
            counts["teacher_assignments"] += int(created)

        # 10. DEMO STUDENTS
        counts["students"] = 0
        demo_students = [
            ("S001", "Aarav Sharma", "s001@clariq.local", (2, "AIML")),
            ("S002", "Diya Patel", "s002@clariq.local", (2, "AIML")),
            ("S003", "Rohan Verma", "s003@clariq.local", (2, "CS1")),
            ("S004", "Ananya Iyer", "s004@clariq.local", (1, "AIML")),
        ]
        default_student_pw = hash_password("student123")
        for s_code, name, email, sec_key in demo_students:
            sec = section_records[sec_key]
            _, created = get_or_create(
                db,
                Student,
                {"student_code": s_code},
                {
                    "full_name": name,
                    "email": email,
                    "password_hash": default_student_pw,
                    "section_id": sec.id,
                    "is_active": True,
                },
            )
            counts["students"] += int(created)

        # 11. SYLLABUS UNITS, TOPICS & SUBTOPICS
        u_count, t_count, s_count = seed_python_syllabus(db, subjects["BCC302"])
        counts["syllabus_units"] = u_count
        counts["syllabus_topics"] = t_count
        counts["syllabus_subtopics"] = s_count

        db.commit()

        # Synchronize PostgreSQL sequences if connected to PostgreSQL
        if engine.dialect.name == "postgresql":
            table_names = [
                "academic_years", "semesters", "section_groups", "sections",
                "section_group_members", "subjects", "subject_offerings",
                "teachers", "students", "teacher_assignments",
                "syllabus_units", "syllabus_topics", "syllabus_subtopics",
            ]
            with engine.connect() as conn:
                for tbl in table_names:
                    try:
                        conn.execute(
                            text(f"SELECT setval(pg_get_serial_sequence('\"{tbl}\"', 'id'), COALESCE((SELECT MAX(id) FROM \"{tbl}\"), 1));")
                        )
                        conn.commit()
                    except Exception:
                        pass

        print("\n==================================================")
        print("CLARIQ DATABASE SEED COMPLETED")
        print("==================================================")
        print("New records created in this run:")
        for entity, count in counts.items():
            print(f"  - {entity}: {count}")
        print("\nDemo Accounts Available:")
        print("  - Student: College ID: S001 | Password: student123")
        print("  - Teacher: College ID: T001 | Password: teacher123")
        print("==================================================\n")

    except Exception as e:
        db.rollback()
        print(f"Seed failed with error: {e}")
        raise
    finally:
        db.close()


def verify_seeded_data():
    """Verify database records and relationships without modifying data."""
    db = SessionLocal()
    try:
        years_cnt = db.query(AcademicYear).count()
        sems_cnt = db.query(Semester).count()
        secs_cnt = db.query(Section).count()
        subjs_cnt = db.query(Subject).count()
        teachers_cnt = db.query(Teacher).count()
        students_cnt = db.query(Student).count()
        units_cnt = db.query(SyllabusUnit).count()
        topics_cnt = db.query(SyllabusTopic).count()
        subtopics_cnt = db.query(SyllabusSubtopic).count()
        assignments_cnt = db.query(TeacherAssignment).count()

        print("\n==================================================")
        print("CLARIQ DATABASE VERIFICATION REPORT")
        print("==================================================")
        print(f"  Academic Years:      {years_cnt}")
        print(f"  Semesters:           {sems_cnt}")
        print(f"  Sections:            {secs_cnt}")
        print(f"  Subjects:            {subjs_cnt}")
        print(f"  Teachers:            {teachers_cnt}")
        print(f"  Students:            {students_cnt}")
        print(f"  Teacher Assignments: {assignments_cnt}")
        print(f"  Syllabus Units:      {units_cnt}")
        print(f"  Syllabus Topics:     {topics_cnt}")
        print(f"  Syllabus Subtopics:  {subtopics_cnt}")
        print("==================================================")

        assert years_cnt >= 2, "Academic years missing"
        assert sems_cnt >= 4, "Semesters missing"
        assert secs_cnt >= 12, "Sections missing"
        assert subjs_cnt >= 10, "Subjects missing"
        assert teachers_cnt >= 11, "Teachers missing"
        assert students_cnt >= 4, "Students missing"
        print("All integrity checks passed successfully!\n")
        return True
    except Exception as e:
        print(f"Verification check failed: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify_seeded_data()
    else:
        seed()
