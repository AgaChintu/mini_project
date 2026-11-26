from app.models import (
    AcademicYear,
    Semester,
    Section,
    Subject,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
)


def seed_sample_academic_data(db_session):
    year = AcademicYear(name="Year 1 - Test", year_number=1, is_active=True)
    db_session.add(year)
    db_session.flush()

    sem = Semester(academic_year_id=year.id, semester_number=1, name="Semester I")
    db_session.add(sem)
    db_session.flush()

    sec = Section(academic_year_id=year.id, semester_id=sem.id, code="AIML", name="AIML Section")
    db_session.add(sec)
    db_session.flush()

    subj = Subject(code="CS101", name="Computer Science 101", subject_type="theory")
    db_session.add(subj)
    db_session.flush()

    unit = SyllabusUnit(subject_id=subj.id, unit_number=1, unit_name="Unit 1", proposed_lectures=8)
    db_session.add(unit)
    db_session.flush()

    topic = SyllabusTopic(unit_id=unit.id, name="Topic 1", display_order=1)
    db_session.add(topic)
    db_session.flush()

    subtopic = SyllabusSubtopic(topic_id=topic.id, name="Subtopic 1", display_order=1)
    db_session.add(subtopic)
    db_session.commit()

    return {"year": year, "sem": sem, "sec": sec, "subj": subj, "unit": unit, "topic": topic, "subtopic": subtopic}


def test_get_academic_years_api(client, db_session):
    seed_sample_academic_data(db_session)
    response = client.get("/api/academic/years")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) >= 1


def test_get_semesters_api(client, db_session):
    data = seed_sample_academic_data(db_session)
    response = client.get(f"/api/academic/semesters?academic_year_id={data['year'].id}")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) >= 1
    assert res["data"][0]["name"] == "Semester I"


def test_get_sections_api(client, db_session):
    data = seed_sample_academic_data(db_session)
    response = client.get(f"/api/academic/sections?academic_year_id={data['year'].id}")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) >= 1


def test_get_subjects_api(client, db_session):
    seed_sample_academic_data(db_session)
    response = client.get("/api/academic/subjects")
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert len(res["data"]) >= 1


def test_get_units_topics_subtopics_api(client, db_session):
    data = seed_sample_academic_data(db_session)

    # Units
    res_units = client.get(f"/api/academic/subjects/{data['subj'].id}/units")
    assert res_units.status_code == 200
    assert len(res_units.json()["data"]) >= 1

    # Topics
    res_topics = client.get(f"/api/academic/units/{data['unit'].id}/topics")
    assert res_topics.status_code == 200
    assert len(res_topics.json()["data"]) >= 1

    # Subtopics
    res_subtopics = client.get(f"/api/academic/topics/{data['topic'].id}/subtopics")
    assert res_subtopics.status_code == 200
    assert len(res_subtopics.json()["data"]) >= 1


def test_invalid_academic_ids_return_404(client):
    assert client.get("/api/academic/subjects/99999/units").status_code == 404
    assert client.get("/api/academic/units/99999/topics").status_code == 404
    assert client.get("/api/academic/topics/99999/subtopics").status_code == 404
