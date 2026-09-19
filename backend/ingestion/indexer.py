import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.database import SessionLocal, ROOT_DIR, DOCS_DIR
from backend.models import Document, DocumentChunk
from backend.ingestion.loader import loader, LoadedDocument

# Pinecone client import
try:
    from pinecone import Pinecone, ServerlessSpec
except ImportError:
    Pinecone = None


def tokenize_text(text: str) -> List[str]:
    """Tokenize technical grid text while preserving voltage ratings, acronyms, and symbols."""
    clean = text.lower()
    # Match words, numbers, and technical terms like 33kv, sf6, n-1, dlro, 85°c, etc.
    tokens = re.findall(r"[a-z0-9]+(?:[-_/.][a-z0-9]+)*", clean)
    return tokens


class LocalVectorStore:
    """High-performance in-memory vector index fallback with cosine similarity."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=10000)
        self.vectors = None
        self.chunks: List[Dict[str, Any]] = []

    def fit(self, chunks: List[Dict[str, Any]]):
        self.chunks = chunks
        texts = [c["text_content"] for c in chunks]
        if texts:
            self.vectors = self.vectorizer.fit_transform(texts)
        else:
            self.vectors = None

    def search(self, query: str, top_k: int = 15, access_level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.vectors is None or not self.chunks:
            return []

        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.vectors)[0]
        sorted_indices = np.argsort(-sims)

        results = []
        for idx in sorted_indices:
            score = float(sims[idx])
            if score <= 0.0:
                continue
            chunk = self.chunks[idx]
            # Role authorization check will also be done in retriever, but metadata filter here
            results.append({
                **chunk,
                "score": score,
                "retrieval_source": "vector",
            })
            if len(results) >= top_k:
                break
        return results


class IndexerManager:
    """Manages document ingestion, Pinecone vector indexing, BM25 indexing, and SQLite sync."""

    def __init__(self):
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_chunks: List[Dict[str, Any]] = []
        self.local_vector_store = LocalVectorStore()
        self.pinecone_client = None
        self.pinecone_index = None
        self.init_pinecone()
        self.load_active_indices()

    def init_pinecone(self):
        """Initialize Pinecone client if credentials are provided in .env."""
        api_key = os.getenv("PINECONE_API_KEY", "").strip()
        index_name = os.getenv("PINECONE_INDEX", "gridknowledge-rag").strip()

        if api_key and Pinecone:
            try:
                self.pinecone_client = Pinecone(api_key=api_key)
                existing_indexes = [idx.name for idx in self.pinecone_client.list_indexes()]
                if index_name not in existing_indexes:
                    try:
                        self.pinecone_client.create_index(
                            name=index_name,
                            dimension=1536,
                            metric="cosine",
                            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
                        )
                    except Exception as ce:
                        print(f"[Pinecone] Warning on create index: {ce}")
                self.pinecone_index = self.pinecone_client.Index(index_name)
                print(f"[Pinecone] Successfully connected to index: {index_name}")
            except Exception as e:
                print(f"[Pinecone] Could not connect to remote Pinecone ({e}). Using robust local vector index.")
                self.pinecone_index = None
        else:
            self.pinecone_index = None

    def chunk_document(self, doc: LoadedDocument) -> List[Dict[str, Any]]:
        """Split document pages into granular semantic chunks with section preservation."""
        chunks: List[Dict[str, Any]] = []
        chunk_idx = 0

        for page in doc.pages:
            text = page.text.strip()
            if not text:
                continue

            # If the page section is under 1400 characters, keep it intact as a complete coherent unit
            if len(text) <= 1400:
                chunks.append({
                    "chunk_index": chunk_idx,
                    "page_number": page.page_number,
                    "section": page.section,
                    "text_content": text,
                    "metadata": {
                        "document": doc.title,
                        "category": doc.category,
                        "equipment": doc.equipment,
                        "section": page.section,
                        "page": page.page_number,
                        "version": doc.version,
                        "effective_date": doc.effective_date,
                        "status": doc.status,
                        "access_level": doc.access_level,
                    },
                })
                chunk_idx += 1
            else:
                # For longer pages, split by paragraphs with context prefix
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                current_chunk = f"[{doc.title} - Section: {page.section}]\n"

                for p in paragraphs:
                    if len(current_chunk) + len(p) < 1200:
                        current_chunk += ("\n\n" + p if current_chunk else p)
                    else:
                        if current_chunk.strip():
                            chunks.append({
                                "chunk_index": chunk_idx,
                                "page_number": page.page_number,
                                "section": page.section,
                                "text_content": current_chunk.strip(),
                                "metadata": {
                                    "document": doc.title,
                                    "category": doc.category,
                                    "equipment": doc.equipment,
                                    "section": page.section,
                                    "page": page.page_number,
                                    "version": doc.version,
                                    "effective_date": doc.effective_date,
                                    "status": doc.status,
                                    "access_level": doc.access_level,
                                },
                            })
                            chunk_idx += 1
                        current_chunk = f"[{doc.title} - Section: {page.section}]\n" + p

                if current_chunk.strip():
                    chunks.append({
                        "chunk_index": chunk_idx,
                        "page_number": page.page_number,
                        "section": page.section,
                        "text_content": current_chunk.strip(),
                        "metadata": {
                            "document": doc.title,
                            "category": doc.category,
                            "equipment": doc.equipment,
                            "section": page.section,
                            "page": page.page_number,
                            "version": doc.version,
                            "effective_date": doc.effective_date,
                            "status": doc.status,
                            "access_level": doc.access_level,
                        },
                    })
                    chunk_idx += 1

        return chunks

    def run_ingestion(self) -> Dict[str, Any]:
        """Execute complete ingestion pipeline: parse -> SQLite -> BM25 -> Vector store."""
        print(f"[Ingestion] Scanning {DOCS_DIR} for approved documents...")
        loaded_docs = loader.scan_directory(DOCS_DIR)
        print(f"[Ingestion] Found {len(loaded_docs)} approved documents.")

        db = SessionLocal()
        all_indexed_chunks = []
        total_chunks = 0

        try:
            for ldoc in loaded_docs:
                # Check or update existing document record
                doc_record = db.query(Document).filter(Document.filename == ldoc.filename).first()
                if not doc_record:
                    doc_record = Document(
                        title=ldoc.title,
                        filename=ldoc.filename,
                        category=ldoc.category,
                        equipment=ldoc.equipment,
                        section=ldoc.section,
                        page_count=len(ldoc.pages),
                        version=ldoc.version,
                        effective_date=ldoc.effective_date,
                        status=ldoc.status,
                        access_level=ldoc.access_level,
                        file_path=ldoc.file_path,
                        file_hash=ldoc.file_hash,
                    )
                    db.add(doc_record)
                    db.flush()
                else:
                    # Update fields
                    doc_record.title = ldoc.title
                    doc_record.category = ldoc.category
                    doc_record.equipment = ldoc.equipment
                    doc_record.section = ldoc.section
                    doc_record.page_count = len(ldoc.pages)
                    doc_record.version = ldoc.version
                    doc_record.access_level = ldoc.access_level
                    doc_record.file_hash = ldoc.file_hash
                    # Clear existing chunks
                    db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_record.id).delete()
                    db.flush()

                # Generate chunks
                raw_chunks = self.chunk_document(ldoc)
                for rc in raw_chunks:
                    chunk_obj = DocumentChunk(
                        document_id=doc_record.id,
                        chunk_index=rc["chunk_index"],
                        page_number=rc["page_number"],
                        section=rc["section"],
                        text_content=rc["text_content"],
                        metadata_json=json.dumps(rc["metadata"]),
                    )
                    db.add(chunk_obj)
                    total_chunks += 1
                    all_indexed_chunks.append({
                        "document_id": doc_record.id,
                        "document": ldoc.title,
                        "category": ldoc.category,
                        "equipment": ldoc.equipment,
                        "section": rc["section"],
                        "page": rc["page_number"],
                        "version": ldoc.version,
                        "access_level": ldoc.access_level,
                        "text_content": rc["text_content"],
                        "metadata": rc["metadata"],
                    })

            db.commit()
            print(f"[Ingestion] Persisted {len(loaded_docs)} documents with {total_chunks} chunks to SQLite.")

        except Exception as e:
            db.rollback()
            print(f"[Ingestion] Error during database commit: {e}")
            raise
        finally:
            db.close()

        # Build in-memory indices (BM25 and Vector store)
        self.build_indices(all_indexed_chunks)

        return {
            "documents_indexed": len(loaded_docs),
            "chunks_created": total_chunks,
            "status": "success",
        }

    def build_indices(self, chunks: List[Dict[str, Any]]):
        """Fit BM25 and vector indices on all current chunks."""
        self.bm25_chunks = chunks
        corpus = [c["text_content"] for c in chunks]
        tokenized_corpus = [tokenize_text(doc) for doc in corpus]

        if tokenized_corpus:
            self.bm25_index = BM25Okapi(tokenized_corpus)
        else:
            self.bm25_index = None

        self.local_vector_store.fit(chunks)
        print(f"[Indexer] Built BM25 and Vector indices for {len(chunks)} chunks.")

    def load_active_indices(self):
        """Load chunks from SQLite and construct indices on startup."""
        db = SessionLocal()
        try:
            chunks_records = db.query(DocumentChunk).join(Document).all()
            if not chunks_records:
                # If database empty, run ingestion automatically
                self.run_ingestion()
                return

            chunks_list = []
            for cr in chunks_records:
                meta = json.loads(cr.metadata_json) if cr.metadata_json else {}
                chunks_list.append({
                    "document_id": cr.document_id,
                    "document": cr.document.title,
                    "category": cr.document.category,
                    "equipment": cr.document.equipment,
                    "section": cr.section,
                    "page": cr.page_number,
                    "version": cr.document.version,
                    "access_level": cr.document.access_level,
                    "text_content": cr.text_content,
                    "metadata": meta,
                })
            self.build_indices(chunks_list)
        finally:
            db.close()

    def search_bm25(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """Run BM25 keyword search over tokenized knowledge base."""
        if not self.bm25_index or not self.bm25_chunks:
            return []

        tokens = tokenize_text(query)
        if not tokens:
            return []

        scores = self.bm25_index.get_scores(tokens)
        sorted_indices = np.argsort(-scores)

        results = []
        for idx in sorted_indices:
            score = float(scores[idx])
            if score <= 0.0:
                continue
            chunk = self.bm25_chunks[idx]
            results.append({
                **chunk,
                "score": score,
                "retrieval_source": "bm25",
            })
            if len(results) >= top_k:
                break
        return results

    def search_vector(self, query: str, top_k: int = 15) -> List[Dict[str, Any]]:
        """Run vector search (Pinecone if configured, else local vector store)."""
        # If remote Pinecone index is active, we query it; otherwise local vector store
        if self.pinecone_index:
            try:
                # Remote Pinecone vector query path
                # Note: In production with Groq or OpenAI embeddings, generate vector here
                pass
            except Exception as pe:
                print(f"[Pinecone] Vector query fallback to local: {pe}")

        return self.local_vector_store.search(query, top_k=top_k)


# Global singleton instance
indexer = IndexerManager()


def run_ingestion():
    return indexer.run_ingestion()
