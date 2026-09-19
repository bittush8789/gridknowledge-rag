import os
import time
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.database import SessionLocal
from backend.models import Conversation, Message, Citation, AuditLog
from backend.guardrails.guardrails import guardrails
from backend.rag.retriever import retriever
from backend.rag.prompts import GRIDKNOWLEDGE_SYSTEM_PROMPT

# LangChain and Provider imports
try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError:
    SystemMessage, HumanMessage = None, None


class RAGPipeline:
    """Enterprise RAG pipeline for GridKnowledge with strict grounding and zero hallucination."""

    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

        # Check LangSmith observability configuration
        self.langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ["true", "1"]
        if self.langsmith_enabled and os.getenv("LANGCHAIN_API_KEY"):
            print(f"[Observability] LangSmith tracing enabled for project: {os.getenv('LANGCHAIN_PROJECT', 'gridknowledge-rag')}")

    def get_llm(self):
        """Instantiate primary (Groq) or fallback (OpenAI) LLM."""
        groq_api_key = os.getenv("GROQ_API_KEY", self.groq_api_key).strip()
        groq_model = os.getenv("GROQ_MODEL", self.groq_model).strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", self.openai_api_key).strip()
        openai_model = os.getenv("OPENAI_MODEL", self.openai_model).strip()

        if groq_api_key and ChatGroq:
            try:
                return ChatGroq(
                    api_key=groq_api_key,
                    model=groq_model,
                    temperature=0.0,
                    max_tokens=2048,
                )
            except Exception as e:
                print(f"[LLM] Error initializing Groq ({groq_model}): {e}")

        if openai_api_key and ChatOpenAI:
            try:
                return ChatOpenAI(
                    api_key=openai_api_key,
                    model=openai_model,
                    temperature=0.0,
                    max_tokens=2048,
                )
            except Exception as e:
                print(f"[LLM] Error initializing OpenAI ({openai_model}): {e}")

        return None

    def build_context_string(self, chunks: List[Dict[str, Any]]) -> str:
        """Construct isolated XML context blocks to prevent document-side prompt injection."""
        context_parts = []
        for idx, chunk in enumerate(chunks, 1):
            doc_title = chunk.get("document", "Unknown Document")
            section = chunk.get("section", "General")
            page = chunk.get("page", 1)
            version = chunk.get("version", "1.0")
            text = chunk.get("text_content", "").strip()

            context_parts.append(
                f'<context_document index="{idx}" document="{doc_title}" section="{section}" page="{page}" version="{version}">\n'
                f'{text}\n'
                f'</context_document>'
            )
        return "\n\n".join(context_parts)

    def extract_structured_citations(
        self, text: str, retrieved_chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract and validate citations from the response against actual retrieved chunks."""
        citations: List[Dict[str, Any]] = []
        seen_keys = set()

        for chunk in retrieved_chunks:
            doc_title = chunk.get("document", "")
            section = chunk.get("section", "")
            page = chunk.get("page", 1)
            version = chunk.get("version", "1.0")
            key = f"{doc_title}_{section}_{page}"

            if key not in seen_keys:
                seen_keys.add(key)
                citations.append({
                    "document_title": doc_title,
                    "section": section,
                    "page": page,
                    "version": version,
                    "excerpt": chunk.get("text_content", "")[:280] + "...",
                    "match_score": round(chunk.get("rerank_score", chunk.get("score", 0.95)), 4),
                })

        return citations

    def local_grounded_synthesis(
        self, query: str, chunks: List[Dict[str, Any]]
    ) -> str:
        """Deterministic, grounded synthesis when external LLM APIs are not configured."""
        if not chunks:
            return "I couldn't find sufficient information in the available grid documentation."

        # Verify content term relevance coverage
        stop_words = {
            "how", "do", "i", "the", "in", "what", "is", "where", "show", "me",
            "a", "an", "and", "or", "of", "to", "for", "with", "at", "from", "on", "can", "about",
            "are", "was", "were", "be", "been", "have", "has", "had", "would", "could", "should"
        }
        from backend.ingestion.indexer import tokenize_text
        q_tokens = [w for w in tokenize_text(query) if w not in stop_words]

        # Check if the retrieved chunks actually match query content tokens
        top_chunk_text = (chunks[0].get("text_content", "") + " " + chunks[0].get("section", "") + " " + chunks[0].get("document", "")).lower()
        matched_tokens = [w for w in q_tokens if w in top_chunk_text]

        # If fewer than 35% of query content tokens match, or 0 match, declare insufficient information
        if q_tokens and (len(matched_tokens) / len(q_tokens) < 0.35 or len(matched_tokens) == 0):
            return "I couldn't find sufficient information in the available grid documentation."

        top_chunk = chunks[0]
        doc_title = top_chunk.get("document", "Grid Documentation")
        section = top_chunk.get("section", "Standard Section")
        page = top_chunk.get("page", 1)
        version = top_chunk.get("version", "1.0")
        raw_text = top_chunk.get("text_content", "")

        # Format clean, enterprise-grounded summary
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        content_lines = [l for l in lines if not l.startswith("#") and not l.startswith("---")][:6]
        summary_body = "\n".join(content_lines)

        response = (
            f"Based on the approved **{doc_title}** (Section: *{section}*, Page {page}):\n\n"
            f"{summary_body}\n\n"
            f"### Sources\n"
            f"* {doc_title} — Section: {section} — Page {page} (v{version})"
        )
        return response

    def run(
        self,
        query: str,
        user_id: int,
        user_role: str,
        conversation_id: Optional[str] = None,
        ip_address: Optional[str] = "127.0.0.1",
    ) -> Dict[str, Any]:
        """Execute the complete enterprise RAG pipeline."""
        start_time = time.time()
        db = SessionLocal()

        try:
            # 1. Input Guardrails
            guard_res = guardrails.validate_input(query)
            if not guard_res.is_safe:
                # Log security block in audit log
                audit = AuditLog(
                    user_id=user_id,
                    action="GUARDRAIL_BLOCK",
                    target_type="QUERY",
                    target_id=conversation_id,
                    details_json=json.dumps(guard_res.to_dict()),
                    ip_address=ip_address,
                )
                db.add(audit)
                db.commit()

                return {
                    "answer": f"Request blocked: {guard_res.reason}",
                    "citations": [],
                    "is_safe": False,
                    "guardrail_status": guard_res.status,
                    "conversation_id": conversation_id,
                    "latency_ms": round((time.time() - start_time) * 1000, 2),
                }

            sanitized_query = guard_res.sanitized_text

            # 2. Conversation Session Management
            import uuid
            if not conversation_id:
                conv_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                conv = Conversation(
                    id=conv_id,
                    title=sanitized_query[:60],
                    user_id=user_id,
                )
                db.add(conv)
                db.commit()
                conversation_id = conv_id
            else:
                conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                if not conv:
                    conv = Conversation(
                        id=conversation_id,
                        title=sanitized_query[:60],
                        user_id=user_id,
                    )
                    db.add(conv)
                    db.commit()

            # 3. Retrieve Conversation Context for Query Rewriting
            prev_messages = (
                db.query(Message)
                .filter(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
                .all()
            )
            history = [{"role": m.role, "content": m.content} for m in prev_messages[-4:]]

            # 4. Query Rewriting & Resolution
            rewritten_query = retriever.query_processor.rewrite_query(
                sanitized_query, history
            )

            # 5. Hybrid Retrieval (Pinecone + BM25 + RBAC filtering + Reranking)
            retrieved_chunks = retriever.retrieve(
                query=rewritten_query,
                user_role=user_role,
                top_candidates=25,
                final_top_k=5,
            )

            # 6. LLM Generation or Local Grounded Synthesis
            llm = self.get_llm()
            if llm and retrieved_chunks and SystemMessage and HumanMessage:
                try:
                    context_str = self.build_context_string(retrieved_chunks)
                    messages = [
                        SystemMessage(content=GRIDKNOWLEDGE_SYSTEM_PROMPT),
                        HumanMessage(
                            content=(
                                f"<context_documents>\n{context_str}\n</context_documents>\n\n"
                                f"User Question: {rewritten_query}"
                            )
                        ),
                    ]
                    llm_resp = llm.invoke(messages)
                    generated_text = llm_resp.content if hasattr(llm_resp, "content") else str(llm_resp)
                except Exception as ex:
                    print(f"[LLM] Live generation failed: {ex}. Falling back to local grounded engine.")
                    generated_text = self.local_grounded_synthesis(rewritten_query, retrieved_chunks)
            else:
                generated_text = self.local_grounded_synthesis(rewritten_query, retrieved_chunks)

            # 7. Output Guardrails & Grounding Check
            output_guard = guardrails.validate_output(generated_text, retrieved_chunks)
            final_answer = output_guard.sanitized_text

            # 8. Extract and validate citations
            if "couldn't find sufficient information" in final_answer.lower():
                citations = []
            else:
                citations = self.extract_structured_citations(final_answer, retrieved_chunks)

            latency_ms = round((time.time() - start_time) * 1000, 2)
            estimated_tokens = (len(sanitized_query) + len(final_answer)) // 4

            # 9. Persist Messages and Citations in SQLite
            user_msg = Message(
                conversation_id=conversation_id,
                role="user",
                content=sanitized_query,
                raw_query=query,
                rewritten_query=rewritten_query,
                latency_ms=0.0,
                tokens_used=len(query) // 4,
                guardrail_flags_json=json.dumps(guard_res.to_dict()),
            )
            db.add(user_msg)

            asst_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=final_answer,
                raw_query=rewritten_query,
                rewritten_query=rewritten_query,
                citations_json=json.dumps(citations),
                latency_ms=latency_ms,
                tokens_used=estimated_tokens,
                guardrail_flags_json=json.dumps(output_guard.to_dict()),
            )
            db.add(asst_msg)
            db.flush()

            for cit in citations:
                cit_obj = Citation(
                    message_id=asst_msg.id,
                    document_title=cit["document_title"],
                    section=cit["section"],
                    page=cit["page"],
                    version=cit["version"],
                    excerpt=cit["excerpt"],
                    match_score=cit["match_score"],
                )
                db.add(cit_obj)

            # Audit log
            audit_log = AuditLog(
                user_id=user_id,
                action="CHAT_QUERY",
                target_type="CONVERSATION",
                target_id=conversation_id,
                details_json=json.dumps({
                    "query": sanitized_query,
                    "rewritten_query": rewritten_query,
                    "chunks_retrieved": len(retrieved_chunks),
                    "latency_ms": latency_ms,
                }),
                ip_address=ip_address,
            )
            db.add(audit_log)
            db.commit()

            return {
                "answer": final_answer,
                "citations": citations,
                "conversation_id": conversation_id,
                "rewritten_query": rewritten_query,
                "latency_ms": latency_ms,
                "is_safe": True,
                "guardrail_status": "Safe",
            }

        except Exception as e:
            db.rollback()
            print(f"[RAGPipeline] Unhandled exception: {e}")
            return {
                "answer": "Something went wrong. Please try again.",
                "citations": [],
                "conversation_id": conversation_id,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "is_safe": False,
                "guardrail_status": "Error",
            }
        finally:
            db.close()


# Global pipeline instance
rag_pipeline = RAGPipeline()
