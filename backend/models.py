import datetime
import json
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Float
)
from sqlalchemy.orm import relationship
from backend.database import Base, engine, SessionLocal, hash_password


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="Viewer")  # Admin, Engineer, Maintenance, Operations, Viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    category = Column(String(100), index=True, nullable=False)  # Grid Operations, Equipment, Maintenance, Safety, Standards
    equipment = Column(String(100), nullable=True)  # Power Transformer, Circuit Breaker, Switchgear, etc.
    section = Column(String(255), nullable=True)
    page_count = Column(Integer, default=1)
    version = Column(String(50), default="1.0")
    effective_date = Column(String(50), nullable=True)
    status = Column(String(50), default="active")  # active, archived, draft
    access_level = Column(String(50), default="Viewer")  # Viewer, Operations, Maintenance, Engineer, Admin
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "filename": self.filename,
            "category": self.category,
            "equipment": self.equipment,
            "section": self.section,
            "page_count": self.page_count,
            "version": self.version,
            "effective_date": self.effective_date,
            "status": self.status,
            "access_level": self.access_level,
            "file_path": self.file_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    page_number = Column(Integer, default=1)
    section = Column(String(255), nullable=True)
    text_content = Column(Text, nullable=False)
    embedding_id = Column(String(255), nullable=True)  # ID in Pinecone/vector store
    metadata_json = Column(Text, nullable=True)  # Serialized JSON

    document = relationship("Document", back_populates="chunks")

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section,
            "text_content": self.text_content,
            "embedding_id": self.embedding_id,
            "metadata": json.loads(self.metadata_json) if self.metadata_json else {},
        }


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, index=True)  # UUID or timestamp key
    title = Column(String(255), default="New Grid Conversation")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0,
        }


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    raw_query = Column(Text, nullable=True)
    rewritten_query = Column(Text, nullable=True)
    citations_json = Column(Text, nullable=True)
    latency_ms = Column(Float, default=0.0)
    tokens_used = Column(Integer, default=0)
    guardrail_flags_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    citations = relationship("Citation", back_populates="message", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "raw_query": self.raw_query,
            "rewritten_query": self.rewritten_query,
            "citations": json.loads(self.citations_json) if self.citations_json else [],
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "guardrail_flags": json.loads(self.guardrail_flags_json) if self.guardrail_flags_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True)
    document_title = Column(String(255), nullable=False)
    section = Column(String(255), nullable=True)
    page = Column(Integer, default=1)
    version = Column(String(50), default="1.0")
    excerpt = Column(Text, nullable=True)
    match_score = Column(Float, default=0.0)

    message = relationship("Message", back_populates="citations")

    def to_dict(self):
        return {
            "id": self.id,
            "document_title": self.document_title,
            "section": self.section,
            "page": self.page,
            "version": self.version,
            "excerpt": self.excerpt,
            "match_score": self.match_score,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)  # CHAT_QUERY, ADMIN_INGEST, GUARDRAIL_TRIGGER, AUTH_LOGIN
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(100), nullable=True)
    details_json = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    user = relationship("User", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "details": json.loads(self.details_json) if self.details_json else {},
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    metrics_json = Column(Text, nullable=False)
    sample_count = Column(Integer, default=0)
    overall_score = Column(Float, default=0.0)
    test_dataset_name = Column(String(100), default="grid_standard_benchmark")
    triggered_by = Column(String(100), default="system")

    def to_dict(self):
        return {
            "id": self.id,
            "run_timestamp": self.run_timestamp.isoformat() if self.run_timestamp else None,
            "metrics": json.loads(self.metrics_json) if self.metrics_json else {},
            "sample_count": self.sample_count,
            "overall_score": self.overall_score,
            "test_dataset_name": self.test_dataset_name,
            "triggered_by": self.triggered_by,
        }


# Role Access Hierarchy: Viewer (lowest) -> Operations -> Maintenance -> Engineer -> Admin (highest)
ROLE_HIERARCHY = {
    "Viewer": 1,
    "Operations": 2,
    "Maintenance": 3,
    "Engineer": 4,
    "Admin": 5,
}


def is_role_authorized(user_role: str, document_access_level: str) -> bool:
    """Determine if a user's role grants access to a document's required access level."""
    user_rank = ROLE_HIERARCHY.get(user_role, 1)
    required_rank = ROLE_HIERARCHY.get(document_access_level, 1)
    return user_rank >= required_rank


def init_db_and_seed():
    """Create tables and seed initial default users."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed users if empty
        if db.query(User).count() == 0:
            seed_users = [
                {
                    "email": "admin@gridknowledge.internal",
                    "full_name": "Grid System Administrator",
                    "password": "AdminPass123!",
                    "role": "Admin",
                },
                {
                    "email": "engineer@gridknowledge.internal",
                    "full_name": "Lead Electrical Engineer",
                    "password": "EngineerPass123!",
                    "role": "Engineer",
                },
                {
                    "email": "maintenance@gridknowledge.internal",
                    "full_name": "Substation Maintenance Tech",
                    "password": "MaintPass123!",
                    "role": "Maintenance",
                },
                {
                    "email": "operations@gridknowledge.internal",
                    "full_name": "Grid Operations Controller",
                    "password": "OpsPass123!",
                    "role": "Operations",
                },
                {
                    "email": "viewer@gridknowledge.internal",
                    "full_name": "Compliance Viewer",
                    "password": "ViewerPass123!",
                    "role": "Viewer",
                },
            ]

            for u in seed_users:
                user_obj = User(
                    email=u["email"],
                    full_name=u["full_name"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True,
                )
                db.add(user_obj)
            db.commit()
            print("[Database] Default users successfully seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db_and_seed()
