"""
Groq-powered AI service for ClariQ (Clean, lightweight, no RAG).
Provides:
  - LLM-based doubt summarisation, keyword/topic extraction, priority detection
  - AI answer drafting (pure Groq inference — never auto-publishes)
  - Similar doubt clustering via lightweight TF-IDF cosine similarity
  - Spam / moderation detection

Falls back gracefully to heuristic processing if GROQ_API_KEY is not configured.
"""
import json
import logging
import math
import re
import os
from collections import defaultdict, Counter
from typing import Dict, Any, List, Optional

logger = logging.getLogger("clariq.ai")

# ---------------------------------------------------------------------------
# Groq client (lazy-initialised)
# ---------------------------------------------------------------------------
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is not None:
        return _groq_client
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from groq import Groq  # type: ignore
        _groq_client = Groq(api_key=api_key)
        logger.info("Groq client initialised successfully.")
    except Exception as exc:
        logger.warning("Could not initialise Groq client: %s", exc)
        _groq_client = None
    return _groq_client


GROQ_MODEL = os.getenv("GROQ_MODEL", "llama3-8b-8192")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT_SECONDS", "30"))


def _groq_chat(messages: List[Dict], max_tokens: int = 1024, temperature: float = 0.3) -> Optional[str]:
    """Sends a chat request to Groq. Returns assistant text or None on failure."""
    client = _get_groq_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=GROQ_TIMEOUT,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        logger.error("Groq API call failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# TF-IDF cosine similarity for grouping similar doubts (pure Python)
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> List[str]:
    return re.findall(r"\b[a-z]{2,}\b", text.lower())


def _tfidf_vector(tokens: List[str], idf: Dict[str, float]) -> Dict[str, float]:
    tf = Counter(tokens)
    total = max(len(tokens), 1)
    return {w: (c / total) * idf.get(w, 1.0) for w, c in tf.items()}


def _cosine(v1: Dict[str, float], v2: Dict[str, float]) -> float:
    keys = set(v1) & set(v2)
    if not keys:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in keys)
    mag1 = math.sqrt(sum(x * x for x in v1.values()))
    mag2 = math.sqrt(sum(x * x for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def compute_similarity(text_a: str, text_b: str) -> float:
    """Returns cosine similarity [0, 1] between two doubt texts via TF-IDF."""
    tokens_a = _tokenise(text_a)
    tokens_b = _tokenise(text_b)
    all_tokens = set(tokens_a) | set(tokens_b)
    idf = {w: 1.0 for w in all_tokens}
    return _cosine(_tfidf_vector(tokens_a, idf), _tfidf_vector(tokens_b, idf))


# ---------------------------------------------------------------------------
# Keyword / topic extraction (heuristics + Groq)
# ---------------------------------------------------------------------------

STOPWORDS = {
    "i", "me", "my", "we", "our", "you", "he", "she", "it", "they",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "have",
    "has", "had", "do", "does", "did", "can", "could", "will", "would",
    "should", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "about", "into", "how", "what", "why", "when", "where", "which",
    "not", "no", "or", "and", "so", "then", "than", "that", "this",
    "help", "please", "doubt", "sir", "maam", "understand", "explain",
    "question", "getting", "error", "facing", "issue", "difference",
    "between", "just", "out", "up", "down", "over", "under",
}

DOMAIN_KEYWORDS = {
    "backpropagation": "Backpropagation",
    "neural network": "Neural Networks",
    "deep learning": "Deep Learning",
    "machine learning": "Machine Learning",
    "decision tree": "Decision Trees",
    "random forest": "Random Forest",
    "linear regression": "Linear Regression",
    "logistic regression": "Logistic Regression",
    "pointer": "Pointers",
    "array": "Arrays",
    "linked list": "Linked Lists",
    "stack": "Stacks",
    "queue": "Queues",
    "tree": "Trees",
    "graph": "Graphs",
    "recursion": "Recursion",
    "dynamic programming": "Dynamic Programming",
    "sorting": "Sorting Algorithms",
    "binary search": "Binary Search",
    "sql": "SQL",
    "join": "Joins",
    "normalization": "Normalization",
    "transaction": "ACID Transactions",
    "deadlock": "Deadlocks",
    "process": "Process Scheduling",
    "thread": "Multithreading",
    "memory management": "Memory Management",
    "paging": "Paging",
    "semaphore": "Semaphores",
    "tcp": "TCP/IP",
    "socket": "Sockets",
    "inheritance": "Inheritance",
    "polymorphism": "Polymorphism",
    "encapsulation": "Encapsulation",
    "class": "OOP Classes",
    "complexity": "Time Complexity",
    "big o": "Big-O Notation",
    "hash": "Hashing",
    "heap": "Heap",
    "dbms": "DBMS",
    "operating system": "Operating Systems",
    "compiler": "Compilers",
    "automata": "Automata Theory",
    "turing": "Turing Machines",
    "fourier": "Fourier Transform",
    "differential": "Differential Equations",
    "integral": "Integration",
    "probability": "Probability",
    "statistics": "Statistics",
}


def extract_keywords_heuristic(text: str, max_kw: int = 5) -> List[str]:
    lowered = text.lower()
    found = []
    for phrase, label in DOMAIN_KEYWORDS.items():
        if phrase in lowered and label not in found:
            found.append(label)
    if len(found) >= max_kw:
        return found[:max_kw]
    words = re.findall(r"\b[a-zA-Z]{4,}\b", lowered)
    for w in words:
        cap = w.capitalize()
        if w not in STOPWORDS and cap not in found:
            found.append(cap)
        if len(found) >= max_kw:
            break
    return found or ["General"]


def extract_keywords_groq(text: str, subject: str = "") -> Optional[List[str]]:
    prompt = (
        f"Extract up to 5 concise academic keywords from this student doubt about {subject or 'academics'}.\n"
        f"Doubt: {text[:800]}\n"
        "Return ONLY a JSON array of strings, e.g. [\"Backpropagation\", \"Chain Rule\"]. No explanation."
    )
    result = _groq_chat([{"role": "user", "content": prompt}], max_tokens=100)
    if result:
        try:
            m = re.search(r"\[.*?\]", result, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception:
            pass
    return None


def extract_topic_groq(text: str, subject: str = "") -> Optional[str]:
    prompt = (
        f"Identify the single main academic topic of this student doubt about {subject or 'academics'}.\n"
        f"Doubt: {text[:600]}\n"
        "Return ONLY the topic name (2-5 words), nothing else."
    )
    result = _groq_chat([{"role": "user", "content": prompt}], max_tokens=30)
    return result.strip('"\'') if result else None


def summarise_doubt_groq(title: str, description: str, subject: str = "") -> Optional[str]:
    prompt = (
        f"Summarise this student academic doubt in 1-2 sentences. Preserve technical terms.\n"
        f"Subject: {subject or 'Unknown'}\nTitle: {title}\nDescription: {description[:600]}\n"
        "Summary (1-2 sentences):"
    )
    return _groq_chat([{"role": "user", "content": prompt}], max_tokens=120)


def detect_priority_groq(cluster_title: str, keywords: str, doubt_count: int, subject: str = "") -> Dict:
    prompt = (
        f"Classify the academic urgency of a doubt cluster.\n"
        f"Subject: {subject}\nCluster: {cluster_title}\nKeywords: {keywords}\n"
        f"Number of students who asked: {doubt_count}\n"
        "Return JSON: {\"priority\": \"high|medium|low\", \"reason\": \"<brief explanation>\"}"
    )
    result = _groq_chat([{"role": "user", "content": prompt}], max_tokens=100)
    if result:
        try:
            m = re.search(r"\{.*?\}", result, re.DOTALL)
            if m:
                data = json.loads(m.group())
                p = data.get("priority", "medium").lower()
                if p not in ("high", "medium", "low"):
                    p = "medium"
                return {"priority": p, "reason": data.get("reason", "")}
        except Exception:
            pass
    # Heuristic fallback
    if doubt_count >= 10:
        return {"priority": "high", "reason": f"{doubt_count} students reported this topic."}
    if doubt_count >= 4:
        return {"priority": "medium", "reason": "Multiple students asked about this topic."}
    return {"priority": "low", "reason": "Single or few submissions."}


def check_spam_groq(title: str, description: str) -> Dict[str, Any]:
    """Returns {is_spam: bool, confidence: float, reason: str}"""
    text = f"{title}: {description}"
    if len(text.strip()) < 10:
        return {"is_spam": True, "confidence": 0.95, "reason": "Too short to be a valid academic doubt."}
    if re.match(r"^(.)\1{4,}$", text.strip()):
        return {"is_spam": True, "confidence": 0.98, "reason": "Repeated characters detected."}

    prompt = (
        "Is this an academic doubt or spam/abusive content?\n"
        f"Text: {text[:500]}\n"
        "Return JSON: {\"is_spam\": true|false, \"confidence\": 0.0-1.0, \"reason\": \"<brief>\"}"
    )
    result = _groq_chat([{"role": "user", "content": prompt}], max_tokens=100)
    if result:
        try:
            m = re.search(r"\{.*?\}", result, re.DOTALL)
            if m:
                data = json.loads(m.group())
                return {
                    "is_spam": bool(data.get("is_spam", False)),
                    "confidence": float(data.get("confidence", 0.5)),
                    "reason": data.get("reason", ""),
                }
        except Exception:
            pass
    return {"is_spam": False, "confidence": 0.0, "reason": "Could not evaluate."}


def generate_ai_answer_groq(
    cluster_title: str,
    summary: str,
    keywords: str,
    individual_doubts: List[str],
    subject: str = "",
) -> Dict[str, Any]:
    """
    Generates an AI answer draft directly from the Master Doubt summary and questions using Groq.
    NO RAG, NO fake citations.
    NEVER auto-publishes — returns draft for teacher review only.
    """
    doubt_examples = "\n".join(f"- {d}" for d in individual_doubts[:5]) if individual_doubts else "General inquiry"

    prompt = (
        f"You are an academic expert helping a university faculty member prepare an answer to student doubts.\n"
        f"Subject: {subject or 'General'}\n"
        f"Topic: {cluster_title}\n"
        f"Summary of student confusion: {summary}\n"
        f"Keywords: {keywords}\n"
        f"Sample student questions:\n{doubt_examples}\n\n"
        "Write a comprehensive, clear, and academically rigorous explanation answering this doubt directly. "
        "Explain the underlying core concept, step-by-step reasoning, and provide a concrete example where appropriate.\n"
        "Answer:"
    )

    draft = _groq_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.3,
    )

    used_groq = bool(draft)

    if not draft:
        # Fallback when Groq is unavailable
        draft = (
            f"**Conceptual Explanation for {cluster_title}** ({subject})\n\n"
            f"This topic focuses on: {summary or 'core curriculum concepts'}.\n\n"
            f"Key terms and concepts involved: {keywords or 'Refer to syllabus'}.\n\n"
            "Please review the standard lecture notes and textbooks for formal mathematical derivations. "
            "Faculty verification and custom response recommended."
        )

    return {
        "draft": draft,
        "used_groq": used_groq,
    }


# ---------------------------------------------------------------------------
# AcademicAIService class (backward-compatible)
# ---------------------------------------------------------------------------

class AcademicAIService:
    COMMON_STOPWORDS = STOPWORDS

    def extract_keywords(self, text: str) -> List[str]:
        return extract_keywords_heuristic(text)

    def generate_summary(self, title: str, description: str, subject_name: str = "") -> str:
        groq_summary = summarise_doubt_groq(title, description, subject_name)
        if groq_summary:
            return groq_summary
        text = f"{title}. {description}".strip()
        clean_text = " ".join(text.split())
        if len(clean_text) <= 120:
            return clean_text
        sentences = re.split(r"[.!?]\s+", clean_text)
        first = sentences[0] if sentences else title
        if len(first) > 140:
            first = first[:137] + "..."
        return f"Query in {subject_name}: {first}" if subject_name else first

    def determine_cluster_title(self, title: str, keywords: List[str]) -> str:
        if keywords and keywords[0] not in ("General", "Conceptual"):
            return f"{keywords[0]} & Related Concepts"
        words = title.strip().split()
        return " ".join(words[:4]) if words else "General Academic Inquiries"

    def process_new_doubt(self, title: str, description: str, subject_name: str = "") -> Dict[str, Any]:
        keywords = extract_keywords_groq(f"{title} {description}", subject_name) or \
                   extract_keywords_heuristic(f"{title} {description}")
        summary = self.generate_summary(title, description, subject_name)
        cluster_title = self.determine_cluster_title(title, keywords)
        topic = extract_topic_groq(f"{title} {description}", subject_name) or (keywords[0] if keywords else "General")
        return {
            "keywords": ", ".join(keywords),
            "ai_summary": summary,
            "cluster_title": cluster_title,
            "topic": topic,
        }

    def cluster_doubts_for_teacher(self, doubts: List[Any]) -> List[Dict[str, Any]]:
        clusters_map = defaultdict(lambda: {
            "cluster_title": "",
            "description": "",
            "doubt_count": 0,
            "student_ids_set": set(),
            "keywords_set": set(),
            "doubts": [],
        })

        for d in doubts:
            cluster_name = getattr(d, "cluster_title", None) or "General Queries"
            group = clusters_map[cluster_name]
            group["cluster_title"] = cluster_name
            group["doubt_count"] += 1
            group["student_ids_set"].add(getattr(d, "student_id", None))

            raw_kw = getattr(d, "keywords", "") or ""
            for k in raw_kw.split(", "):
                if k.strip():
                    group["keywords_set"].add(k.strip())

            answers_list = []
            for ans in getattr(d, "answers", []):
                answers_list.append({
                    "id": ans.id,
                    "answer_text": ans.answer_text,
                    "teacher_name": ans.teacher.full_name if ans.teacher else "Teacher",
                    "resource_url": ans.resource_url,
                    "answer_attachment_name": getattr(ans, "answer_attachment_name", None),
                    "answer_attachment_mime": getattr(ans, "answer_attachment_mime", None),
                    "created_at": ans.created_at.isoformat() if ans.created_at else None,
                })

            attachments_list = []
            for att in getattr(d, "attachments", []):
                attachments_list.append({
                    "id": att.id,
                    "original_filename": att.original_filename,
                    "mime_type": att.mime_type,
                    "file_size": att.file_size,
                })

            group["doubts"].append({
                "id": d.id,
                "doubt_code": getattr(d, "doubt_code", str(d.id)),
                "title": d.title or d.question[:60],
                "description": d.description or d.question,
                "question": d.question,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "ai_summary": getattr(d, "ai_summary", None) or d.title or d.question,
                "keywords": [k.strip() for k in (getattr(d, "keywords", "") or "").split(", ") if k.strip()],
                "attachments": attachments_list,
                "answers": answers_list,
                "is_resolved": d.status == "resolved" or len(answers_list) > 0,
            })

        output_clusters = []
        for idx, (c_name, data) in enumerate(clusters_map.items()):
            doubt_count = data["doubt_count"]
            student_count = len(data["student_ids_set"])
            output_clusters.append({
                "cluster_id": f"cluster-{idx + 1}",
                "cluster_title": c_name,
                "description": f"{student_count} student{'s' if student_count != 1 else ''} asked about this topic.",
                "doubt_count": doubt_count,
                "student_count": student_count,
                "keywords": sorted(list(data["keywords_set"])),
                "doubts": data["doubts"],
                "has_pending": any(not d["is_resolved"] for d in data["doubts"]),
            })

        return output_clusters


ai_service = AcademicAIService()
