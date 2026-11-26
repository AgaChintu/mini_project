"""
Groq-powered conversational AI service for ClariQ Chatbot (Student + Teacher).
Direct integration with Groq API — clean, lightweight, no RAG.
"""
import os
import logging
from typing import List, Dict, Any, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("clariq.chatbot")

STUDENT_SYSTEM_PROMPT = """You are ClariQ AI, an academic assistant for college students.

Your purpose is to help students understand academic concepts, solve educational problems, learn programming, understand mathematics and prepare for examinations.

Explain concepts clearly and in a student-friendly manner.

Use step-by-step explanations whenever necessary.

Provide examples when useful.

For programming questions, provide readable code and explain its logic.

Maintain conversational context and understand follow-up questions.

Do not unnecessarily complicate simple explanations.

If a question is outside your knowledge, acknowledge the limitation instead of inventing information."""

TEACHER_SYSTEM_PROMPT = """You are ClariQ AI Copilot, an academic teaching assistant for college faculty.

Your purpose is to help teachers prepare lectures, create assignments, generate MCQs, develop practice questions, explain technical concepts and prepare educational content.

Provide accurate, structured and professional academic responses.

Generate classroom-ready explanations and examples.

For MCQs, provide four options and clearly identify the correct answer with an explanation.

For lesson plans, organize the content into logical teaching sections.

Maintain conversational context and understand follow-up instructions.

Do not invent facts or pretend to access institutional data that has not been provided."""

FALLBACK_MODELS = ["qwen/qwen3.8-27b", "allam-2-7b"]


def call_groq_chat(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    max_tokens: int = 1500,
    temperature: float = 0.5,
) -> Dict[str, Any]:
    """
    Sends chat completion request to Groq API via HTTPX.
    Returns dict: {"success": bool, "content": str, "model": str, "error": Optional[str]}
    """
    api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        logger.error("GROQ_API_KEY is not configured.")
        return {
            "success": False,
            "content": "",
            "model": "",
            "error": "Groq API key is not configured on the server.",
        }

    target_model = model or settings.GROQ_MODEL or "openai/gpt-oss-120b"
    models_to_try = [target_model] + [m for m in FALLBACK_MODELS if m != target_model]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error = None
    timeout_sec = float(settings.GROQ_TIMEOUT_SECONDS or 30)

    for m in models_to_try:
        try:
            payload = {
                "model": m,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            with httpx.Client(timeout=timeout_sec) as client:
                res = client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )

            if res.status_code == 200:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return {
                    "success": True,
                    "content": content,
                    "model": m,
                    "error": None,
                }
            elif res.status_code == 429:
                err_msg = "Groq API rate limit exceeded. Please wait a moment and try again."
                logger.warning("Groq rate limit (429) for model %s", m)
                last_error = err_msg
            else:
                err_data = res.json().get("error", {})
                err_msg = err_data.get("message", f"Groq API returned HTTP {res.status_code}")
                logger.warning("Groq call failed for model %s (%s): %s", m, res.status_code, err_msg)
                last_error = err_msg

        except httpx.TimeoutException:
            logger.warning("Groq request timed out for model %s", m)
            last_error = "The AI service timed out while generating a response. Please try again."
        except Exception as exc:
            logger.error("Unexpected error connecting to Groq for model %s: %s", m, exc)
            last_error = f"Error communicating with AI service: {str(exc)}"

    return {
        "success": False,
        "content": "",
        "model": target_model,
        "error": last_error or "Unable to generate an AI response at this time.",
    }


def generate_student_reply(
    history: List[Dict[str, str]],
    user_message: str,
) -> Dict[str, Any]:
    """Prepares student context and queries Groq."""
    messages = [{"role": "system", "content": STUDENT_SYSTEM_PROMPT}]
    # Append past history (max last 10 turns to stay within context budget)
    for h in history[-10:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    return call_groq_chat(messages=messages, temperature=0.6)


def generate_teacher_reply(
    history: List[Dict[str, str]],
    user_message: str,
) -> Dict[str, Any]:
    """Prepares teacher context and queries Groq."""
    messages = [{"role": "system", "content": TEACHER_SYSTEM_PROMPT}]
    # Append past history (max last 10 turns)
    for h in history[-10:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    return call_groq_chat(messages=messages, temperature=0.4)
