import os
import re
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from backend.models import is_role_authorized
from backend.ingestion.indexer import indexer, tokenize_text
from backend.rag.prompts import QUERY_EXPANSION_DICTIONARY


class QueryProcessor:
    """Handles query contextualization, pronoun resolution, and technical expansion."""

    def rewrite_query(
        self, query: str, conversation_history: List[Dict[str, str]], llm_caller=None
    ) -> str:
        """Contextualize follow-up questions using preceding dialogue."""
        if not conversation_history:
            return query.strip()

        # Check if query needs pronoun/context resolution
        followup_cues = [
            r"\b(it|its|they|their|this|that|these|those)\b",
            r"\b(what about|how about|what of|where is)\b",
            r"\b(and the|and its|also)\b",
        ]
        is_followup = any(re.search(cue, query, re.IGNORECASE) for cue in followup_cues)
        is_short = len(query.strip().split()) <= 6

        if not (is_followup or is_short):
            return query.strip()

        # Extract last user query and assistant answer for context
        last_turn = conversation_history[-1] if conversation_history else None
        if not last_turn:
            return query.strip()

        context_subject = ""
        prev_user_q = ""
        for turn in reversed(conversation_history):
            if turn.get("role") == "user":
                prev_user_q = turn.get("content", "")
                break

        # Extract key entities from previous question (e.g. transformer, circuit breaker, switchgear, busbar)
        grid_entities = [
            "transformer", "power transformer", "circuit breaker", "vcb", "sf6",
            "switchgear", "busbar", "disconnector", "isolator", "ppe", "loto",
            "protective relay", "earthing", "substation"
        ]
        for ent in grid_entities:
            if ent in prev_user_q.lower():
                context_subject = ent
                break

        if context_subject:
            # Deterministic rule-based rewriting
            clean_q = re.sub(r"(?i)\b(what about|how about)\b", "", query).strip()
            clean_q = re.sub(r"(?i)\b(its|it|this|that)\b", context_subject, clean_q)
            if context_subject not in clean_q.lower():
                rewritten = f"{clean_q} for {context_subject}".strip()
            else:
                rewritten = clean_q.strip()
            return rewritten

        return query.strip()

    def expand_query(self, query: str) -> str:
        """Enrich query with domain-specific technical synonyms without losing original intent."""
        lowered = query.lower()
        expansions = []

        for term, expansion in QUERY_EXPANSION_DICTIONARY.items():
            pattern = rf"\b{re.escape(term)}\b"
            if re.search(pattern, lowered):
                expansions.append(expansion)

        if expansions:
            # Combine original query with key expansion terms
            expanded = query + " " + " ".join(expansions[:2])
            return expanded.strip()
        return query


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        pass


class SemanticFusionReranker(BaseReranker):
    """High-accuracy fallback cross-scorer leveraging exact term matching and technical token relevance."""

    def rerank(self, query: str, chunks: List[Dict[str, Any]], top_n: int = 5) -> List[Dict[str, Any]]:
        if not chunks:
            return []

        query_tokens = set(tokenize_text(query))
        ranked = []

        for item in chunks:
            text = item.get("text_content", "").lower()
            section = item.get("section", "").lower()
            doc_title = item.get("document", "").lower()

            # Technical term overlap
            text_tokens = set(tokenize_text(text))
            overlap = len(query_tokens.intersection(text_tokens))

            # Bonus for section or title match
            section_bonus = 1.5 if any(qt in section for qt in query_tokens) else 0.0
            title_bonus = 1.0 if any(qt in doc_title for qt in query_tokens) else 0.0

            # Base fusion rank score
            base_score = item.get("rrf_score", 0.0)

            # Combined reranking score
            rerank_score = base_score * 2.0 + (overlap * 0.1) + section_bonus + title_bonus
            item_copy = dict(item)
            item_copy["rerank_score"] = float(rerank_score)
            ranked.append(item_copy)

        ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_n]


class HybridRetriever:
    """Combines Dense Vector Search + Sparse BM25 Keyword Search with RRF and RBAC filtering."""

    def __init__(self, reranker: Optional[BaseReranker] = None):
        self.query_processor = QueryProcessor()
        self.reranker = reranker or SemanticFusionReranker()

    def retrieve(
        self,
        query: str,
        user_role: str = "Viewer",
        top_candidates: int = 25,
        final_top_k: int = 6,
    ) -> List[Dict[str, Any]]:
        """Run complete hybrid retrieval, RBAC authorization, RRF fusion, and reranking."""
        # 1. Expand query for technical coverage
        expanded_query = self.query_processor.expand_query(query)

        # 2. Vector search (Pinecone / local fallback)
        vector_results = indexer.search_vector(expanded_query, top_k=top_candidates)

        # 3. BM25 keyword search
        bm25_results = indexer.search_bm25(expanded_query, top_k=top_candidates)

        # 4. Pre-retrieval RBAC filtering (only authorized documents reach downstream pipeline)
        authorized_vector = [
            v for v in vector_results
            if is_role_authorized(user_role, v.get("access_level", "Viewer"))
        ]
        authorized_bm25 = [
            b for b in bm25_results
            if is_role_authorized(user_role, b.get("access_level", "Viewer"))
        ]

        # 5. Reciprocal Rank Fusion (RRF)
        # RRF formula: Score(d) = sum( 1 / (k + rank_i(d)) ) with standard constant k = 60
        fused_candidates: Dict[str, Dict[str, Any]] = {}
        k_const = 60.0

        for rank, item in enumerate(authorized_vector):
            key = f"{item['document']}__p{item['page']}__c{item.get('chunk_index', 0)}"
            score = 1.0 / (k_const + rank + 1)
            if key not in fused_candidates:
                fused_candidates[key] = dict(item)
                fused_candidates[key]["rrf_score"] = score
            else:
                fused_candidates[key]["rrf_score"] += score

        for rank, item in enumerate(authorized_bm25):
            key = f"{item['document']}__p{item['page']}__c{item.get('chunk_index', 0)}"
            score = 1.0 / (k_const + rank + 1)
            if key not in fused_candidates:
                fused_candidates[key] = dict(item)
                fused_candidates[key]["rrf_score"] = score
            else:
                fused_candidates[key]["rrf_score"] += score

        sorted_fused = sorted(
            fused_candidates.values(), key=lambda x: x.get("rrf_score", 0.0), reverse=True
        )[:top_candidates]

        # 6. Reranker
        top_chunks = self.reranker.rerank(query, sorted_fused, top_n=final_top_k)
        return top_chunks


# Global retriever instance
retriever = HybridRetriever()
