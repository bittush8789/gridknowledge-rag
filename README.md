# GridKnowledge RAG — Developer Documentation

Welcome to the **GridKnowledge RAG** developer documentation. This guide covers the system architecture, component design, local development workflows, API specifications, and testing strategies for the electricity-grid enterprise knowledge assistant.

---

## 1. System Architecture & Request Lifecycle

> **Full System Design Document:** For the end-to-end C4 architecture diagrams, state machine flows, RBAC clearance matrix, multi-layer guardrails, and failover topologies, refer to [`system-design.md`](file:///d:/GridKnowledge/system-design.md).

GridKnowledge RAG implements a deterministic, non-agentic RAG pipeline. It avoids autonomous agent loops in favor of a reliable, high-assurance pipeline tailored for safety-critical utility operations.

```
Incoming Request
    │
    ▼
[1. Input Guardrails]
    ├── Prompt Injection Detector (Regex & Semantic Heuristics)
    ├── Jailbreak Classifier (Safe / Suspicious / Blocked)
    ├── PII Masking Engine (Emails, Phones, Employee IDs: EMP-XXXX)
    └── Toxicity & Sabotage Interceptor
    │
    ▼
[2. RBAC & Clearance Filter]
    └── Maps user role (Viewer ➔ Operations ➔ Maintenance ➔ Engineer ➔ Admin)
        and enforces pre-retrieval access boundaries on document metadata.
    │
    ▼
[3. Conversational Memory & Query Processor]
    ├── History Retrieval (SQLite `messages` table for active conversation)
    ├── Query Rewriting (Contextualizes pronouns: "its inspection checklist" ➔ "transformer inspection checklist")
    └── Query Expansion (Enriches domain acronyms: VCB, SF6, LOTO, DGA, DLRO)
    │
    ▼
[4. Hybrid Retrieval Engine]
    ├── Dense Retrieval: Pinecone Vector Database (Cosine Similarity)
    └── Sparse Retrieval: Local BM25Okapi (Tokenized with voltage ratings & technical terms)
    │
    ▼
[5. Reciprocal Rank Fusion (RRF)]
    └── Fuses Dense & Sparse ranks: RRF_score = Σ [ 1 / (60 + rank_i) ]
    │
    ▼
[6. Modular Reranker]
    └── Semantic cross-scorer reranks top 25 candidates down to top 5–6 chunks.
    │
    ▼
[7. Context Builder]
    └── Fences retrieved chunks in passive XML tags (<context_document>) to neutralize indirect injection.
    │
    ▼
[8. LLM Inference Layer]
    ├── Primary: Groq (openai/gpt-oss-120b or llama-3.3-70b-versatile)
    ├── Fallback: OpenAI (gpt-4o-mini or gpt-4o)
    └── Offline Fallback: Deterministic local grounded synthesis engine
    │
    ▼
[9. Output Guardrails & Grounding Check]
    ├── Data Leakage Prevention (Screening API keys, secrets, system prompt traces)
    ├── Output PII Redaction
    └── Insufficient Information Enforcer ("I couldn't find sufficient information...")
    │
    ▼
[10. Response & Citation Assembly]
    └── Generates structured citations with exact Document, Section, Page, and Version.
```

---

## 2. Codebase Organization

```
GridKnowledge/
├── backend/
│   ├── main.py                 # FastAPI application, route definitions, middleware, lifecycle
│   ├── database.py             # SQLAlchemy sessionmaker, SQLite connection pooling, password hashing
│   ├── models.py               # ORM entities (User, Document, Chunk, Conversation, Message, Citation, AuditLog, EvaluationResult)
│   ├── rag/
│   │   ├── pipeline.py         # End-to-end RAG orchestrator, LLM connector, output verification
│   │   ├── retriever.py        # HybridRetriever, QueryProcessor, RRF logic, ModularReranker
│   │   └── prompts.py          # Grounding system prompt, query rewriting prompt, expansion dictionary
│   ├── ingestion/
│   │   ├── loader.py           # Multi-format parser (Markdown, PDF via PyMuPDF, DOCX, HTML) with page preservation
│   │   └── indexer.py          # Semantic chunker, Pinecone index manager, BM25 builder, SQLite persistence
│   ├── guardrails/
│   │   └── guardrails.py       # Prompt injection, jailbreak classification, PII redaction, toxic filtering, leakage detection
│   └── evaluation/
│       └── evaluation.py       # RAG benchmark engine (Precision, Recall, Faithfulness, Relevance, Citations, Safety)
├── frontend/
│   ├── index.html              # Search homepage with quick-launch example queries
│   ├── chat.html               # Main conversational workspace, clickable citations, admin console
│   ├── css/
│   │   └── style.css           # Modular, responsive enterprise stylesheet (no frameworks)
│   └── js/
│       └── app.js              # State management, JWT session handling, streaming UI, modals, admin actions
├── data/
│   ├── documents/              # Approved knowledge base repository (categorized markdown/pdf/docx/html)
│   │   ├── equipment/          # Transformer, Circuit Breaker, Switchgear manuals
│   │   ├── grid_operations/    # Substation guide, Switching procedures
│   │   ├── maintenance/        # Preventive maintenance, Inspection guides
│   │   ├── safety/             # Electrical safety, PPE guidelines, LOTO SOP
│   │   └── standards/          # Grid operations standards, Inspection compliance
│   └── gridknowledge.db        # SQLite application database
├── tests/
│   └── test_rag.py             # Automated unit and integration test suite
├── .env                        # Active environment configuration
├── .env.example                # Configuration template
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container build specification
├── docker-compose.yml          # Container orchestration configuration
├── k8s/                        # Kubernetes manifests (kind-config, namespace, deployment, service, pvc, configmap, secrets)
├── deploy.sh                   # Production update and zero-downtime deployment script
├── DEPLOYMENT_AWS_EC2.md       # Complete step-by-step AWS EC2 production deployment handbook
├── DEPLOYMENT_K8S_KIND.md      # Local Kubernetes deployment guide using KinD
├── system-design.md            # Comprehensive enterprise C4 system design document
└── README.md                   # Developer documentation
```

---

## 3. Developer Environment Setup

### 3.1 Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13
- Git

### 3.2 Virtual Environment & Dependencies
```powershell
# 1. Clone repository
git clone https://github.com/organization/GridKnowledge.git
cd GridKnowledge

# 2. Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### 3.3 Configuration (`.env`)
Create `.env` from `.env.example`:
```ini
# Application
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
JWT_SECRET=your-secure-jwt-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Database
DATABASE_URL=sqlite:///data/gridknowledge.db

# LLM Inference (Groq primary, OpenAI fallback)
GROQ_API_KEY=gsk_your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Vector Search (Pinecone)
PINECONE_API_KEY=pcsk_your_pinecone_api_key_here
PINECONE_INDEX=gridknowledge-rag
PINECONE_ENVIRONMENT=us-east-1

# Observability (LangSmith)
LANGCHAIN_TRACING_V2=false
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=gridknowledge-rag
```

> **Zero-Dependency Fallback**: If `GROQ_API_KEY` or `PINECONE_API_KEY` are left blank, the application automatically falls back to an embedded in-memory vector store (Scikit-learn cosine similarity) and deterministic local grounded synthesis.

---

## 4. Database & Ingestion Workflow

### 4.1 Initialize Database & Seed Users
The database initializes automatically on application startup, but you can seed it manually:
```powershell
python -m backend.models
```

**Pre-seeded Developer Accounts:**
| Role | Email | Password | Access Clearance |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@gridknowledge.internal` | `AdminPass123!` | Full admin privileges, ingestion, re-indexing, evaluations |
| **Engineer** | `engineer@gridknowledge.internal` | `EngineerPass123!` | Engineering specifications, compliance standards, manuals |
| **Maintenance** | `maintenance@gridknowledge.internal` | `MaintPass123!` | Maintenance SOPs, LOTO procedures, equipment guides |
| **Operations** | `operations@gridknowledge.internal` | `OpsPass123!` | Grid switching procedures, busbar load transfer SOPs |
| **Viewer** | `viewer@gridknowledge.internal` | `ViewerPass123!` | General electrical safety and statutory grid standards |

### 4.2 Run Document Ingestion & Indexing
To parse all approved documents from `data/documents/` into SQLite, Pinecone, and BM25:
```powershell
python -c "from backend.ingestion.indexer import run_ingestion; print(run_ingestion())"
```

---

## 5. Running the Application

### 5.1 Development Server (Hot Reload)
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
- **Web Client**: `http://127.0.0.1:8000`
- **Chat Workspace**: `http://127.0.0.1:8000/chat`
- **Interactive OpenAPI Docs (Swagger)**: `http://127.0.0.1:8000/docs`
- **Redoc**: `http://127.0.0.1:8000/redoc`

---

## 6. Core Modules Deep Dive

### 6.1 Hybrid Retrieval & Reciprocal Rank Fusion (`retriever.py`)
Dense vector search retrieves semantic matches, while BM25 retrieves exact technical nomenclature (e.g. `33kV`, `SF6`, `0.60 MPa`, `VCB`, `DLRO`). Both candidate sets are merged via Reciprocal Rank Fusion:

$$RRF(d) = \sum_{m \in \{dense, sparse\}} \frac{1}{k + \text{rank}_m(d)}$$

Where $k = 60$. Candidates are then passed to `SemanticFusionReranker`, which evaluates exact technical token overlap, title match bonuses, and section header relevance before picking the top 5–6 chunks.

### 6.2 Pre-Retrieval RBAC Filtering
To satisfy enterprise data security, authorization occurs **before** any context reaches the LLM:
```python
# backend/rag/retriever.py
authorized_vector = [
    v for v in vector_results
    if is_role_authorized(user_role, v.get("access_level", "Viewer"))
]
```
If a `Viewer` queries an `Engineer`-level document (e.g. detailed circuit breaker timing tolerances), those chunks are filtered out before context assembly, ensuring zero unauthorized data leakage.

### 6.3 AI Guardrails Suite (`guardrails.py`)
- **Prompt Injection Defense**: Detects adversarial commands like `"ignore previous instructions"`, `"reveal system prompt"`, and instruction smuggling patterns.
- **Jailbreak Classifier**: Classifies incoming queries as `Safe`, `Suspicious`, or `Blocked`.
- **PII Engine**: Automatic regex and entity detection for emails, phone numbers, and employee ID formats (`EMP-[0-9]{4,8}`, `GRID-[0-9]{4,8}`).
- **Untrusted Context Fencing**: Retrieved chunks are wrapped inside `<context_document>` XML boundary tags so that adversarial text within indexed manuals cannot escape data context.

---

## 7. REST API Reference

### 7.1 Authentication

#### `POST /api/auth/login`
Authenticate user credentials and obtain a JWT bearer token.
- **Request Body:**
  ```json
  {
    "email": "engineer@gridknowledge.internal",
    "password": "EngineerPass123!"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": 2,
      "email": "engineer@gridknowledge.internal",
      "full_name": "Lead Electrical Engineer",
      "role": "Engineer"
    }
  }
  ```

#### `GET /api/auth/me`
Validate the current bearer token and return user profile details.

---

### 7.2 Chat & Retrieval

#### `POST /api/chat`
Execute the end-to-end RAG pipeline.
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:**
  ```json
  {
    "query": "What is the normal operating filling pressure for SF6 circuit breakers?",
    "conversation_id": "conv_1789826891_abcd1234"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "answer": "The normal operating filling pressure for SF6 circuit breakers is 0.60 MPa (6.0 bar absolute)...",
    "citations": [
      {
        "document_title": "Circuit Breaker Manual",
        "section": "SF6 Gas Pressure Monitoring and Density Limits",
        "page": 14,
        "version": "5.0",
        "excerpt": "Pressure Thresholds at 20°C Reference: 1. Normal Operating Filling Pressure: 0.60 MPa...",
        "match_score": 0.95
      }
    ],
    "conversation_id": "conv_1789826891_abcd1234",
    "rewritten_query": "What is the normal operating filling pressure for SF6 circuit breakers?",
    "latency_ms": 342.15,
    "is_safe": true,
    "guardrail_status": "Safe"
  }
  ```

#### `GET /api/conversations`
List all conversation sessions belonging to the authenticated user.

#### `GET /api/conversations/{id}`
Retrieve the full message transcript and citation records for a specific session.

#### `DELETE /api/conversations/{id}`
Permanently delete a conversation session and associated message history.

#### `GET /api/sources/{id}`
Retrieve verified document metadata, section outlines, and chunk excerpts.

#### `GET /api/health`
Inspect system health, active database connection, vector store status, and LLM model identifier.
```json
{
  "status": "healthy",
  "service": "GridKnowledge RAG",
  "database": "connected",
  "retrieval": {
    "bm25_indexed_chunks": 42,
    "vector_store": "pinecone"
  },
  "llm_inference": "groq",
  "active_model": "GPT-OSS 120B (Groq)",
  "model_id": "openai/gpt-oss-120b"
}
```

---

### 7.3 Administration Endpoints (Admin Role Required)

- `POST /api/admin/ingest` — Triggers fresh scanning and ingestion of `data/documents/`.
- `GET /api/admin/documents` — Returns inventory of all indexed documents and versions.
- `POST /api/admin/reindex` — Rebuilds BM25 and vector indices.
- `GET /api/admin/evaluation` — Retrieves historical RAG evaluation benchmark logs.
- `POST /api/admin/evaluation/run` — Executes automated evaluation benchmark suite.
- `GET /api/admin/users` — Returns user directory and role assignments.
- `GET /api/admin/audit-logs` — Retrieves security audit trail and guardrail trigger logs.

---

## 8. Testing & Quality Assurance

### 8.1 Automated Test Suite
The repository includes a comprehensive `pytest` suite testing models, RBAC, guardrails, retrieval, query rewriting, and API routes:
```powershell
python -m pytest tests/test_rag.py -v
```

**Coverage Breakdown:**
- `test_database_and_seeded_users`: Verifies user seeding and role constraints.
- `test_rbac_hierarchy`: Asserts role hierarchy and access level boundaries.
- `test_guardrails_input_validation`: Tests length, empty string, and malformed inputs.
- `test_guardrails_prompt_injection`: Tests adversarial prompt injection blocking.
- `test_guardrails_pii_masking`: Verifies masking of emails, phone numbers, and employee IDs.
- `test_query_rewriting_for_followup`: Verifies contextual pronoun resolution.
- `test_hybrid_retrieval_and_reranking`: Tests BM25 and vector search recall.
- `test_rag_pipeline_grounded_response`: End-to-end grounded answer assertion.
- `test_out_of_domain_insufficient_info`: Asserts fallback for out-of-scope questions.
- `test_api_health`: Verifies health check payload.
- `test_api_auth_login`: Tests JWT token issuance.
- `test_api_chat_flow`: Tests conversation lifecycle and follow-ups.

### 8.2 RAG Evaluation Benchmark Suite
Run the built-in automated benchmark evaluating Retrieval Precision, Recall, Faithfulness, Relevance, Citation Accuracy, and Safety:
```powershell
python -c "from backend.evaluation.evaluation import run_evaluation_benchmark; print(run_evaluation_benchmark())"
```

**Target Metrics:**
- **Context Precision**: 100.0%
- **Context Recall**: 83.3%
- **Faithfulness**: 85.7%
- **Answer Relevance**: 92.9%
- **Citation Accuracy**: 100.0%
- **Safety Defense Rate**: 100.0%
- **Overall Benchmark Score**: 92.4%

---

## 9. Production & Cloud Deployment

> 🚀 **Complete Step-by-Step AWS EC2 Guide:** For an end-to-end beginner-friendly production guide covering EC2 instance provisioning, Elastic IPs, Security Groups, Nginx reverse proxy, Let's Encrypt SSL, automated database backups, and zero-downtime updates, read [`DEPLOYMENT_AWS_EC2.md`](file:///d:/GridKnowledge/DEPLOYMENT_AWS_EC2.md).
>
> ☸️ **Local Kubernetes (KinD) Guide:** For running GridKnowledge RAG on a local Kubernetes cluster using KinD (Kubernetes IN Docker) with PersistentVolumeClaims, ConfigMaps, Secrets, health probes, and NodePort mapping, read [`DEPLOYMENT_K8S_KIND.md`](file:///d:/GridKnowledge/DEPLOYMENT_K8S_KIND.md).

### 9.1 Build and Run with Docker Compose
```bash
# Build image and start in background
docker-compose up --build -d

# View service logs
docker-compose logs -f

# Stop container
docker-compose down
```

### 9.2 Container Structure
- Base Image: `python:3.11-slim`
- Application Port: `8000`
- Volume Mount: `./data` is mounted to persist SQLite database and documents across container rebuilds.

### 9.3 Deploy on Local Kubernetes (KinD) Quickstart
```bash
# 1. Create KinD cluster with host port 8000 mapped to NodePort 30080
kind create cluster --config k8s/kind-config.yaml --name gridknowledge

# 2. Build and load local image
docker build -t gridknowledge-rag:latest .
kind load docker-image gridknowledge-rag:latest --name gridknowledge

# 3. Configure secrets and apply manifests
cp k8s/secret.example.yaml k8s/secret.yaml
# (Add your API keys to k8s/secret.yaml)
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/

# 4. Open in browser: http://localhost:8000
```

