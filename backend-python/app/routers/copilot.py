"""
AI Copilot router — smart doubt clustering, Groq LLM answer generation,
analytics, and cluster management for teachers.

CRITICAL: AI-generated answers are NEVER auto-published.
Only an authenticated teacher can call /publish to release an answer to students.
NO RAG — pure Groq reasoning grounded directly on student doubt text.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Teacher
from app.models.academic import Subject
from app.models.doubt import Doubt
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.models.academic_resource import AcademicResource, DoubtCluster, DoubtClusterMember
from app.services.ai_service import (
    ai_service,
    compute_similarity,
    detect_priority_groq,
    generate_ai_answer_groq,
    check_spam_groq,
)

logger = logging.getLogger("clariq.copilot")

router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])
security = HTTPBearer()

CLUSTER_SIMILARITY_THRESHOLD = 0.35


# ─────────────────────────── Auth ──────────────────────────────────────────

def _get_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Teacher:
    payload = decode_access_token(credentials.credentials)
    if not payload or str(payload.get("role", "")).upper() != "TEACHER":
        raise HTTPException(status_code=401, detail="Teacher authentication required.")
    tid = int(payload.get("sub") or payload.get("user_id"))
    t = db.query(Teacher).filter(Teacher.id == tid, Teacher.is_active == True).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return t


def _teacher_subject_ids(teacher: Teacher, db: Session) -> set:
    sta_ids = {a.subject_id for a in db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher.id,
        SubjectTeacherAssignment.is_active == True,
    ).all()}
    legacy_ids = {a.subject_id for a in db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher.id
    ).all()}
    return sta_ids | legacy_ids


# ─────────────────────────── Overview Dashboard ────────────────────────────

@router.get("/dashboard")
def copilot_dashboard(
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)

    doubts_q = db.query(Doubt).filter(Doubt.subject_id.in_(subject_ids)) if subject_ids else db.query(Doubt).filter(False)
    total_doubts = doubts_q.count()
    resolved = doubts_q.filter(Doubt.status == "resolved").count()
    pending = doubts_q.filter(Doubt.status == "pending").count()

    clusters_q = db.query(DoubtCluster).filter(DoubtCluster.teacher_id == teacher.id)
    total_clusters = clusters_q.count()
    high_priority = clusters_q.filter(
        or_(DoubtCluster.teacher_priority == "high", DoubtCluster.ai_priority == "high"),
        DoubtCluster.status != "resolved",
    ).count()
    drafts = clusters_q.filter(DoubtCluster.ai_draft_answer != None, DoubtCluster.published_answer == None).count()

    week_ago = datetime.utcnow() - timedelta(days=7)
    weekly_new = doubts_q.filter(Doubt.created_at >= week_ago).count()

    resources = db.query(AcademicResource).filter(
        AcademicResource.teacher_id == teacher.id,
        AcademicResource.status == "active",
    ).count()

    return {
        "success": True,
        "data": {
            "total_doubts": total_doubts,
            "resolved_doubts": resolved,
            "pending_doubts": pending,
            "total_clusters": total_clusters,
            "high_priority_clusters": high_priority,
            "ai_drafts_pending_review": drafts,
            "doubts_last_7_days": weekly_new,
            "library_resources_uploaded": resources,
        },
    }


# ─────────────────────────── Cluster / Master Doubt Cards ─────────────────

def _cluster_to_dict(c: DoubtCluster, include_members: bool = False) -> dict:
    priority = c.teacher_priority or c.ai_priority or "medium"
    d = {
        "id": c.id,
        "cluster_title": c.cluster_title,
        "ai_summary": c.ai_summary,
        "keywords": c.keywords,
        "topic": c.topic,
        "subject_id": c.subject_id,
        "subject_name": c.subject.name if c.subject else None,
        "priority": priority,
        "ai_priority": c.ai_priority,
        "teacher_priority": c.teacher_priority,
        "priority_reason": c.priority_reason,
        "status": c.status,
        "doubt_count": c.doubt_count,
        "has_ai_draft": c.ai_draft_answer is not None,
        "has_published_answer": c.published_answer is not None,
        "published_at": c.published_at.isoformat() if c.published_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
    if include_members:
        member_doubts = []
        for m in c.members:
            doubt = m.doubt
            if doubt:
                member_doubts.append({
                    "id": doubt.id,
                    "title": doubt.title or doubt.question[:60],
                    "question": doubt.question,
                    "description": doubt.description,
                    "status": doubt.status,
                    "created_at": doubt.created_at.isoformat() if doubt.created_at else None,
                    "similarity_score": m.similarity_score,
                    "added_by": m.added_by,
                })
        d["member_doubts"] = member_doubts
        d["ai_draft_answer"] = c.ai_draft_answer
        d["teacher_edited_answer"] = c.teacher_edited_answer
        d["published_answer"] = c.published_answer
    return d


@router.get("/clusters")
def list_clusters(
    subject_id: Optional[int] = Query(None),
    priority: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    q = db.query(DoubtCluster).filter(DoubtCluster.subject_id.in_(subject_ids)) if subject_ids else db.query(DoubtCluster).filter(False)

    if subject_id:
        q = q.filter(DoubtCluster.subject_id == subject_id)
    if priority:
        q = q.filter(
            or_(DoubtCluster.teacher_priority == priority, DoubtCluster.ai_priority == priority)
        )
    if status_filter:
        q = q.filter(DoubtCluster.status == status_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(
            DoubtCluster.cluster_title.ilike(like) | DoubtCluster.ai_summary.ilike(like)
        )

    total = q.count()
    clusters = q.order_by(desc(DoubtCluster.doubt_count), desc(DoubtCluster.updated_at))\
                .offset((page - 1) * per_page).limit(per_page).all()

    return {
        "success": True,
        "total": total,
        "data": [_cluster_to_dict(c) for c in clusters],
    }


@router.get("/clusters/{cluster_id}")
def get_cluster_detail(
    cluster_id: int,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    c = db.query(DoubtCluster).filter(
        DoubtCluster.id == cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not c:
        raise HTTPException(404, "Cluster not found.")
    return {"success": True, "data": _cluster_to_dict(c, include_members=True)}


# ─────────────────────────── Re-cluster / Process doubts ───────────────────

@router.post("/process-doubts")
def process_and_cluster_doubts(
    subject_id: Optional[int] = None,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    """
    Groups doubts into DoubtCluster (Master Doubt Cards) using TF-IDF cosine similarity.
    """
    subject_ids = _teacher_subject_ids(teacher, db)
    if subject_id:
        if subject_id not in subject_ids:
            raise HTTPException(403, "Not authorised for this subject.")
        subject_ids = {subject_id}

    doubts = db.query(Doubt).filter(
        Doubt.subject_id.in_(subject_ids),
    ).order_by(Doubt.created_at).all()

    created = 0
    updated = 0

    for doubt in doubts:
        existing_member = db.query(DoubtClusterMember).filter(
            DoubtClusterMember.doubt_id == doubt.id
        ).first()
        if existing_member:
            continue

        doubt_text = f"{doubt.title or ''} {doubt.question or ''} {doubt.description or ''}"
        subj = doubt.subject
        subj_name = subj.name if subj else ""

        subject_clusters = db.query(DoubtCluster).filter(
            DoubtCluster.subject_id == doubt.subject_id
        ).all()

        best_cluster = None
        best_score = 0.0

        for cluster in subject_clusters:
            cluster_text = f"{cluster.cluster_title} {cluster.ai_summary or ''} {cluster.keywords or ''}"
            score = compute_similarity(doubt_text, cluster_text)
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster and best_score >= CLUSTER_SIMILARITY_THRESHOLD:
            member = DoubtClusterMember(
                cluster_id=best_cluster.id,
                doubt_id=doubt.id,
                similarity_score=round(best_score, 4),
                added_by="ai",
            )
            db.add(member)
            best_cluster.doubt_count = (best_cluster.doubt_count or 0) + 1
            best_cluster.updated_at = datetime.utcnow()

            priority_data = detect_priority_groq(
                best_cluster.cluster_title,
                best_cluster.keywords or "",
                best_cluster.doubt_count,
                subj_name,
            )
            best_cluster.ai_priority = priority_data["priority"]
            best_cluster.priority_reason = priority_data["reason"]
            updated += 1

        else:
            processed = ai_service.process_new_doubt(
                doubt.title or doubt.question[:60],
                doubt.description or doubt.question,
                subj_name,
            )
            priority_data = detect_priority_groq(
                processed["cluster_title"],
                processed["keywords"],
                1,
                subj_name,
            )
            cluster = DoubtCluster(
                subject_id=doubt.subject_id,
                teacher_id=teacher.id,
                cluster_title=processed["cluster_title"],
                ai_summary=processed["ai_summary"],
                keywords=processed["keywords"],
                topic=processed.get("topic"),
                ai_priority=priority_data["priority"],
                priority_reason=priority_data["reason"],
                doubt_count=1,
                status="pending",
            )
            db.add(cluster)
            db.flush()

            member = DoubtClusterMember(
                cluster_id=cluster.id,
                doubt_id=doubt.id,
                similarity_score=1.0,
                added_by="ai",
            )
            db.add(member)
            created += 1

    db.commit()
    return {
        "success": True,
        "message": f"Processed {len(doubts)} doubts. Created {created} new clusters, updated {updated} existing.",
    }


# ─────────────────────────── AI Answer Generation (Groq, No RAG) ──────────

@router.post("/clusters/{cluster_id}/generate-answer")
def generate_answer_draft(
    cluster_id: int,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    """
    Generates an AI answer draft for a cluster using Groq directly.
    NO RAG, NO fake citations.
    NEVER publishes automatically — returns draft for teacher review only.
    """
    subject_ids = _teacher_subject_ids(teacher, db)
    cluster = db.query(DoubtCluster).filter(
        DoubtCluster.id == cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not cluster:
        raise HTTPException(404, "Cluster not found.")

    individual_doubts = []
    for m in cluster.members:
        if m.doubt:
            text = m.doubt.question or m.doubt.title or ""
            if text:
                individual_doubts.append(text)

    subject = cluster.subject
    result = generate_ai_answer_groq(
        cluster_title=cluster.cluster_title,
        summary=cluster.ai_summary or "",
        keywords=cluster.keywords or "",
        individual_doubts=individual_doubts,
        subject=subject.name if subject else "",
    )

    cluster.ai_draft_answer = result["draft"]
    cluster.status = "answer_drafted"
    cluster.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "data": {
            "cluster_id": cluster_id,
            "draft": result["draft"],
            "used_groq": result["used_groq"],
        },
    }


# ─────────────────────────── Teacher: save draft / publish ─────────────────

class DraftRequest(BaseModel):
    answer_text: str = Field(..., min_length=10)


@router.post("/clusters/{cluster_id}/save-draft")
def save_teacher_draft(
    cluster_id: int,
    body: DraftRequest,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    cluster = db.query(DoubtCluster).filter(
        DoubtCluster.id == cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not cluster:
        raise HTTPException(404, "Cluster not found.")
    cluster.teacher_edited_answer = body.answer_text.strip()
    cluster.status = "answer_drafted"
    cluster.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Draft saved."}


@router.post("/clusters/{cluster_id}/publish")
def publish_cluster_answer(
    cluster_id: int,
    body: DraftRequest,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    """
    HUMAN-IN-THE-LOOP: Only a teacher can call this endpoint to publish an answer.
    Backend enforces this — AI alone cannot trigger this endpoint.
    """
    subject_ids = _teacher_subject_ids(teacher, db)
    cluster = db.query(DoubtCluster).filter(
        DoubtCluster.id == cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not cluster:
        raise HTTPException(404, "Cluster not found.")

    cluster.published_answer = body.answer_text.strip()
    cluster.published_at = datetime.utcnow()
    cluster.published_by_teacher_id = teacher.id
    cluster.status = "resolved"
    cluster.updated_at = datetime.utcnow()

    # Resolve individual doubts that are part of this cluster
    for m in cluster.members:
        if m.doubt and m.doubt.status not in ("resolved",):
            m.doubt.status = "resolved"

    db.commit()
    return {"success": True, "message": "Answer published to students."}


# ─────────────────────────── Priority override ─────────────────────────────

class PriorityOverride(BaseModel):
    priority: str = Field(..., pattern="^(high|medium|low)$")
    reason: Optional[str] = None


@router.put("/clusters/{cluster_id}/priority")
def override_priority(
    cluster_id: int,
    body: PriorityOverride,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    cluster = db.query(DoubtCluster).filter(
        DoubtCluster.id == cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not cluster:
        raise HTTPException(404, "Cluster not found.")
    cluster.teacher_priority = body.priority
    if body.reason:
        cluster.priority_reason = body.reason
    cluster.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": f"Priority set to {body.priority}."}


# ─────────────────────────── Manual cluster operations ─────────────────────

class MoveDoubtRequest(BaseModel):
    doubt_id: int
    target_cluster_id: int


@router.post("/clusters/move-doubt")
def move_doubt_to_cluster(
    body: MoveDoubtRequest,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    existing = db.query(DoubtClusterMember).filter(
        DoubtClusterMember.doubt_id == body.doubt_id
    ).first()
    if existing:
        old_cluster = db.query(DoubtCluster).filter(
            DoubtCluster.id == existing.cluster_id,
            DoubtCluster.subject_id.in_(subject_ids),
        ).first()
        if not old_cluster:
            raise HTTPException(403, "Access denied.")
        old_cluster.doubt_count = max(0, old_cluster.doubt_count - 1)
        db.delete(existing)

    target = db.query(DoubtCluster).filter(
        DoubtCluster.id == body.target_cluster_id,
        DoubtCluster.subject_id.in_(subject_ids),
    ).first()
    if not target:
        raise HTTPException(404, "Target cluster not found.")

    new_member = DoubtClusterMember(
        cluster_id=body.target_cluster_id,
        doubt_id=body.doubt_id,
        similarity_score=None,
        added_by="teacher",
    )
    db.add(new_member)
    target.doubt_count = target.doubt_count + 1
    target.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Doubt moved successfully."}


# ─────────────────────────── Analytics ────────────────────────────────────

@router.get("/analytics")
def get_analytics(
    subject_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    subject_ids = _teacher_subject_ids(teacher, db)
    if subject_id:
        subject_ids = {subject_id} if subject_id in subject_ids else set()

    since = datetime.utcnow() - timedelta(days=days)

    doubts = db.query(Doubt).filter(
        Doubt.subject_id.in_(subject_ids),
        Doubt.created_at >= since,
    ).all() if subject_ids else []

    subject_dist = {}
    topic_dist = {}
    for d in doubts:
        sname = d.subject.name if d.subject else "Unknown"
        subject_dist[sname] = subject_dist.get(sname, 0) + 1
        topic = getattr(d, "cluster_title", None) or "General"
        topic_dist[topic] = topic_dist.get(topic, 0) + 1

    heatmap = sorted(topic_dist.items(), key=lambda x: -x[1])[:20]

    clusters = db.query(DoubtCluster).filter(
        DoubtCluster.subject_id.in_(subject_ids)
    ).all() if subject_ids else []

    resolved_clusters = sum(1 for c in clusters if c.status == "resolved")
    high_priority_clusters = sum(
        1 for c in clusters if (c.teacher_priority or c.ai_priority) == "high"
    )

    return {
        "success": True,
        "data": {
            "period_days": days,
            "total_doubts_in_period": len(doubts),
            "resolved_doubts": sum(1 for d in doubts if d.status == "resolved"),
            "pending_doubts": sum(1 for d in doubts if d.status != "resolved"),
            "subject_distribution": [
                {"subject": k, "count": v} for k, v in sorted(subject_dist.items(), key=lambda x: -x[1])
            ],
            "topic_heatmap": [{"topic": t, "count": c} for t, c in heatmap],
            "total_clusters": len(clusters),
            "resolved_clusters": resolved_clusters,
            "high_priority_clusters": high_priority_clusters,
        },
    }


# ─────────────────────────── Spam check ───────────────────────────────────

class SpamCheckRequest(BaseModel):
    title: str
    description: str


@router.post("/moderation/check")
def check_moderation(body: SpamCheckRequest):
    result = check_spam_groq(body.title, body.description)
    return {"success": True, "data": result}
