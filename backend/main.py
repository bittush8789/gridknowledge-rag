import os
import json
import time
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import jwt
from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database import get_db, verify_password, SessionLocal, ROOT_DIR, DOCS_DIR
from backend.models import (
    User, Document, DocumentChunk, Conversation, Message, Citation, AuditLog,
    EvaluationResult, init_db_and_seed
)
from backend.rag.pipeline import rag_pipeline
from backend.ingestion.indexer import indexer, run_ingestion
from backend.evaluation.evaluation import run_evaluation_benchmark

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "gridknowledge-jwt-signing-secret-key-super-secure")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# Initialize FastAPI application
app = FastAPI(
    title="GridKnowledge RAG API",
    description="Enterprise Knowledge Assistant for Electricity-Grid Operations",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = ROOT_DIR / "frontend"


# Pydantic Request & Response Schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None


def create_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_EXPIRE_MINUTES),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    authorization: Optional[str] = Header(None), db: Session = Depends(get_db)
) -> User:
    """Verify Bearer token and return current User object."""
    if not authorization or not authorization.startswith("Bearer "):
        # Default to Viewer guest if unauthenticated for reading
        viewer_user = db.query(User).filter(User.role == "Viewer").first()
        if viewer_user:
            return viewer_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
        )

    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid user account.")
        return user
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session token.")


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """RBAC gate: Only Admin role is permitted."""
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authorization required for this action.",
        )
    return current_user


# Startup event: initialize DB and check indices
@app.on_event("startup")
def startup_event():
    init_db_and_seed()


# --- Authentication Endpoints ---
@app.post("/api/auth/login")
def login(creds: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not verify_password(creds.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your email and password.",
        )

    token = create_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user.to_dict(),
    }


@app.get("/api/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {"user": current_user.to_dict()}


# --- Chat & RAG Endpoints ---
@app.post("/api/chat")
def chat(
    payload: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    ip_addr = request.client.host if request.client else "127.0.0.1"
    response = rag_pipeline.run(
        query=payload.query,
        user_id=current_user.id,
        user_role=current_user.role,
        conversation_id=payload.conversation_id,
        ip_address=ip_addr,
    )
    return response


@app.get("/api/conversations")
def list_conversations(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    convs = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [c.to_dict() for c in convs]


@app.get("/api/conversations/{conv_id}")
def get_conversation_history(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return {
        "conversation": conv.to_dict(),
        "messages": [m.to_dict() for m in messages],
    }


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conv_id, Conversation.user_id == current_user.id)
        .first()
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conv)
    db.commit()
    return {"status": "deleted", "id": conv_id}


@app.get("/api/sources/{doc_id}")
def get_source_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Access check
    from backend.models import is_role_authorized
    if not is_role_authorized(current_user.role, doc.access_level):
        raise HTTPException(
            status_code=403,
            detail="This information is not available to your account level.",
        )

    # Return document overview and chunk excerpts
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
    return {
        "document": doc.to_dict(),
        "chunks": [
            {
                "page": c.page_number,
                "section": c.section,
                "text": c.text_content,
            }
            for c in chunks
        ],
    }


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    db_status = "connected"
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Health DB check error: {e}")
        db_status = "degraded"

    bm25_count = len(indexer.bm25_chunks)
    vector_status = "pinecone" if indexer.pinecone_index else "local_vector_engine"
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    if groq_key:
        llm_provider = "groq"
        active_model = f"GPT-OSS 120B (Groq)" if "120b" in groq_model.lower() else f"Groq ({groq_model})"
    elif openai_key:
        llm_provider = "openai"
        active_model = f"OpenAI ({openai_model})"
    else:
        llm_provider = "local_grounded_engine"
        active_model = "Local Grounded Engine"

    return {
        "status": "healthy",
        "service": "GridKnowledge RAG",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "database": db_status,
        "retrieval": {
            "bm25_indexed_chunks": bm25_count,
            "vector_store": vector_status,
        },
        "llm_inference": llm_provider,
        "active_model": active_model,
        "model_id": groq_model if groq_key else (openai_model if openai_key else "local"),
        "observability": {
            "langsmith_enabled": rag_pipeline.langsmith_enabled,
        },
    }


# --- Admin Endpoints ---
@app.post("/api/admin/ingest")
def admin_ingest(admin_user: User = Depends(get_admin_user)):
    res = run_ingestion()
    return res


@app.get("/api/admin/documents")
def admin_list_documents(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
):
    docs = db.query(Document).order_by(Document.category, Document.title).all()
    return [d.to_dict() for d in docs]


@app.post("/api/admin/reindex")
def admin_reindex(admin_user: User = Depends(get_admin_user)):
    res = run_ingestion()
    return {"status": "reindexed", "details": res}


@app.get("/api/admin/evaluation")
def admin_get_evaluation(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
):
    latest = db.query(EvaluationResult).order_by(EvaluationResult.run_timestamp.desc()).all()
    return [e.to_dict() for e in latest]


@app.post("/api/admin/evaluation/run")
def admin_run_evaluation(admin_user: User = Depends(get_admin_user)):
    result = run_evaluation_benchmark()
    return result


@app.get("/api/admin/users")
def admin_get_users(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return [u.to_dict() for u in users]


@app.get("/api/admin/audit-logs")
def admin_get_audit_logs(
    admin_user: User = Depends(get_admin_user), db: Session = Depends(get_db)
):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(100).all()
    return [l.to_dict() for l in logs]


# --- Static Frontend Delivery ---
if FRONTEND_DIR.exists():
    app.mount("/css", StaticFiles(directory=str(FRONTEND_DIR / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(FRONTEND_DIR / "js")), name="js")

    @app.get("/")
    def serve_home():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/chat")
    def serve_chat():
        return FileResponse(FRONTEND_DIR / "chat.html")

    @app.get("/chat.html")
    def serve_chat_html():
        return FileResponse(FRONTEND_DIR / "chat.html")

    @app.get("/index.html")
    def serve_index_html():
        return FileResponse(FRONTEND_DIR / "index.html")
