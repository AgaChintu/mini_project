"""
ClariQ AI Chatbot Router — Student & Teacher conversational academic assistants.
Powered directly by Groq API.
Enforces strict user isolation and role-specific system prompts.
"""
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Student, Teacher
from app.models.chatbot import ChatConversation, ChatMessage
from app.services.chatbot_service import (
    generate_student_reply,
    generate_teacher_reply,
)

logger = logging.getLogger("clariq.chatbot")

router = APIRouter(prefix="/api/chatbot", tags=["AI Chatbot"])
security = HTTPBearer()


# ─────────────────────────── Auth Dependencies ──────────────────────────────

def _get_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Student:
    payload = decode_access_token(credentials.credentials)
    if not payload or str(payload.get("role", "")).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student authentication required.",
        )
    sid = int(payload.get("sub") or payload.get("user_id"))
    student = db.query(Student).filter(Student.id == sid, Student.is_active == True).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    return student


def _get_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Teacher:
    payload = decode_access_token(credentials.credentials)
    if not payload or str(payload.get("role", "")).upper() != "TEACHER":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Teacher authentication required.",
        )
    tid = int(payload.get("sub") or payload.get("user_id"))
    teacher = db.query(Teacher).filter(Teacher.id == tid, Teacher.is_active == True).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return teacher


def _get_current_user_and_role(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Authenticates either a Student or Teacher."""
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Authentication token required.")

    role = str(payload.get("role", "")).upper()
    uid = int(payload.get("sub") or payload.get("user_id"))

    if role == "STUDENT":
        user = db.query(Student).filter(Student.id == uid, Student.is_active == True).first()
    elif role == "TEACHER":
        user = db.query(Teacher).filter(Teacher.id == uid, Teacher.is_active == True).first()
    else:
        raise HTTPException(status_code=403, detail="Access denied for this role.")

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    return {"user_id": uid, "user_role": role, "user": user}


# ─────────────────────────── Pydantic Schemas ───────────────────────────────

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None


class CreateConversationRequest(BaseModel):
    title: Optional[str] = "New Chat"


# ─────────────────────────── Helper Functions ───────────────────────────────

def _resolve_or_create_conversation(
    db: Session,
    user_id: int,
    user_role: str,
    conv_id: Optional[str],
    first_message: str,
) -> ChatConversation:
    """Finds an existing conversation owned by the user, or creates a new one."""
    if conv_id:
        existing = db.query(ChatConversation).filter(
            ChatConversation.id == conv_id,
            ChatConversation.user_id == user_id,
            ChatConversation.user_role == user_role,
        ).first()
        if existing:
            return existing

    # Create new conversation with title derived from first message
    title = first_message.strip()[:40]
    if len(first_message.strip()) > 40:
        title += "..."
    new_conv = ChatConversation(
        id=str(uuid.uuid4()),
        user_id=user_id,
        user_role=user_role,
        title=title or "New Chat",
    )
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)
    return new_conv


# ─────────────────────────── Student Chat Endpoint ──────────────────────────

@router.post("/student/message")
def student_chat_message(
    body: ChatMessageRequest,
    student: Student = Depends(_get_student),
    db: Session = Depends(get_db),
):
    """
    Student AI Chatbot message handler.
    Maintains conversation context and applies Student System Prompt.
    """
    user_msg = body.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    conv = _resolve_or_create_conversation(
        db=db,
        user_id=student.id,
        user_role="STUDENT",
        conv_id=body.conversation_id,
        first_message=user_msg,
    )

    # Gather conversation history
    history: List[Dict[str, str]] = []
    if body.conversation_history:
        history = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in body.conversation_history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
    else:
        # Load from DB
        db_messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conv.id
        ).order_by(ChatMessage.created_at).all()
        history = [{"role": m.role, "content": m.content} for m in db_messages]

    # Save user message to DB
    user_chat_record = ChatMessage(
        conversation_id=conv.id,
        role="user",
        content=user_msg,
    )
    db.add(user_chat_record)
    db.commit()

    # Query Groq
    ai_result = generate_student_reply(history=history, user_message=user_msg)

    if not ai_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ai_result["error"] or "Groq AI service failed to respond.",
        )

    ai_text = ai_result["content"]

    # Save assistant response to DB
    asst_chat_record = ChatMessage(
        conversation_id=conv.id,
        role="assistant",
        content=ai_text,
    )
    db.add(asst_chat_record)
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "response": ai_text,
        "conversation_id": conv.id,
        "model": ai_result["model"],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────── Teacher Chat Endpoint ──────────────────────────

@router.post("/teacher/message")
def teacher_chat_message(
    body: ChatMessageRequest,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    """
    Teacher AI Copilot message handler.
    Maintains conversation context and applies Teacher System Prompt.
    """
    user_msg = body.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    conv = _resolve_or_create_conversation(
        db=db,
        user_id=teacher.id,
        user_role="TEACHER",
        conv_id=body.conversation_id,
        first_message=user_msg,
    )

    # Gather conversation history
    history: List[Dict[str, str]] = []
    if body.conversation_history:
        history = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in body.conversation_history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
    else:
        db_messages = db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conv.id
        ).order_by(ChatMessage.created_at).all()
        history = [{"role": m.role, "content": m.content} for m in db_messages]

    # Save user message to DB
    user_chat_record = ChatMessage(
        conversation_id=conv.id,
        role="user",
        content=user_msg,
    )
    db.add(user_chat_record)
    db.commit()

    # Query Groq
    ai_result = generate_teacher_reply(history=history, user_message=user_msg)

    if not ai_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=ai_result["error"] or "Groq AI service failed to respond.",
        )

    ai_text = ai_result["content"]

    # Save assistant response to DB
    asst_chat_record = ChatMessage(
        conversation_id=conv.id,
        role="assistant",
        content=ai_text,
    )
    db.add(asst_chat_record)
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "response": ai_text,
        "conversation_id": conv.id,
        "model": ai_result["model"],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─────────────────────────── Session Management ─────────────────────────────

@router.get("/conversations")
def list_conversations(
    auth: Dict[str, Any] = Depends(_get_current_user_and_role),
    db: Session = Depends(get_db),
):
    """Lists conversations for the authenticated user."""
    convs = db.query(ChatConversation).filter(
        ChatConversation.user_id == auth["user_id"],
        ChatConversation.user_role == auth["user_role"],
    ).order_by(desc(ChatConversation.updated_at)).all()

    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in convs
        ],
    }


@router.post("/conversations")
def create_new_conversation(
    body: Optional[CreateConversationRequest] = None,
    auth: Dict[str, Any] = Depends(_get_current_user_and_role),
    db: Session = Depends(get_db),
):
    """Explicitly initializes a new conversation session."""
    title = (body.title if body else "New Chat") or "New Chat"
    new_conv = ChatConversation(
        id=str(uuid.uuid4()),
        user_id=auth["user_id"],
        user_role=auth["user_role"],
        title=title,
    )
    db.add(new_conv)
    db.commit()
    db.refresh(new_conv)

    return {
        "success": True,
        "data": {
            "id": new_conv.id,
            "title": new_conv.title,
            "created_at": new_conv.created_at.isoformat(),
        },
    }


@router.get("/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: str,
    auth: Dict[str, Any] = Depends(_get_current_user_and_role),
    db: Session = Depends(get_db),
):
    """Retrieves all messages in a specific conversation for the owner."""
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == auth["user_id"],
        ChatConversation.user_role == auth["user_role"],
    ).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv.id
    ).order_by(ChatMessage.created_at).all()

    return {
        "success": True,
        "data": {
            "id": conv.id,
            "title": conv.title,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        },
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    auth: Dict[str, Any] = Depends(_get_current_user_and_role),
    db: Session = Depends(get_db),
):
    """Deletes / clears a conversation and all its messages."""
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id,
        ChatConversation.user_id == auth["user_id"],
        ChatConversation.user_role == auth["user_role"],
    ).first()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied.")

    db.delete(conv)
    db.commit()

    return {"success": True, "message": "Conversation deleted successfully."}
