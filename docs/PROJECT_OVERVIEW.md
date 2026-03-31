# Project Overview

## Project Summary
This repository contains an AI-assisted crypto protocol analysis product called the **On-Chain Fundamentals & Risk Analyzer**. Based on the current code and READMEs, the system ingests unstructured materials such as whitepapers, audit reports, PDFs, and URLs, extracts a structured protocol profile with Gemini, scores risk with deterministic rules, stores the result in PostgreSQL, and presents the output through a Streamlit dashboard.

The codebase is organized around a clear split between analysis services in `Backend/` and operator-facing UI in `Frontend/`. That separation is a strength: the API, persistence layer, evaluation assets, and dashboard concerns are not heavily mixed together.

## Product Purpose
The product appears to help users evaluate whether a blockchain project or smart-contract-based protocol is safe to interact with.

Observed capabilities:
- Parse protocol documentation into a `ProjectProfile`.
- Assess risk across audit status, admin control, tokenomics, vulnerabilities, and limited on-chain verification.
- Return a scored `RiskAssessment` with flagged issues and recommended action.
- Support follow-up Q&A against the analyzed documents.
- Export the latest assessment as a PDF report.

Important scope note: the implementation is document-driven first. It is not a full autonomous on-chain scanner. Live chain checks are currently limited to basic EVM contract-code presence checks.

## Repository Structure
Top-level code is split into two subprojects:

- `Backend/`: FastAPI service, SQLAlchemy models, Alembic migrations, deterministic risk engine, Gemini integration, RAG utilities, tests, eval assets, and developer verification scripts.
- `Frontend/`: Streamlit application for document intake, analysis submission, result display, chat, and PDF download.
- `docs/`: Documentation folder. This file is the first project-level architecture overview in the root workspace.

Important backend support assets:
- `Backend/alembic/versions/`: database schema history for profiles, assessments, chat logs, session IDs, and pgvector embeddings.
- `Backend/test_cases/`: sample protocol payloads such as `case_01_safe_dex.json`.
- `Backend/examples/sample_analysis_request.json`: example API payload.
- `Backend/eval/`: dataset-driven LLM extraction evaluation framework.
- `Backend/devtools/verify_api.py`: simple script to post test cases to the local API.

## Backend Overview
The backend is the system of record and the main source of business logic.

Core responsibilities:
- Expose HTTP endpoints through FastAPI.
- Convert raw protocol text into structured data with Gemini.
- Persist profiles, risk assessments, chat logs, LLM usage events, and document embeddings.
- Run deterministic scoring rules.
- Retrieve document chunks for follow-up chat.
- Generate downloadable PDF reports.

Main API surface in `Backend/main.py`:
- `GET /health`
- `POST /api/v1/analyze`
- `POST /api/v1/chat`
- `GET /api/v1/report/{session_id}`

Main technical components:
- `app/agent.py`: Gemini-powered extraction into the `ProjectProfile` schema.
- `app/engine.py`: deterministic risk scoring and limited on-chain verification.
- `app/rag.py`: document chunking, embedding generation, and vector retrieval.
- `app/chat.py`: follow-up Q&A using prior findings plus retrieved document context.
- `app/db/models.py`: SQLAlchemy models for `project_profiles`, `risk_assessments`, `document_embeddings`, `llm_usage_events`, and `chat_logs`.
- `app/reporting.py`: PDF generation.
- `app/llm_tracker.py`: token and estimated cost tracking per request/session.

## Frontend Overview
The frontend is a Streamlit dashboard in `Frontend/Home.py`. It is a thin client over the backend rather than an independent application layer.

Observed responsibilities:
- Collect protocol materials from pasted text, uploaded PDFs, or fetched URLs.
- Keep a per-session document set in Streamlit session state.
- Submit analysis jobs to the backend.
- Render profile details, score, issues, and vulnerabilities.
- Support follow-up chat using the same session ID.
- Download a PDF report from the backend.

The helper modules are small and focused:
- `Frontend/utils/api.py`: HTTP calls to the backend.
- `Frontend/utils/document_processor.py`: PDF text extraction and URL scraping.

## Main Workflows
### 1. Protocol analysis
1. A user loads one or more documents in the Streamlit UI.
2. The frontend sends `session_id` plus document text to `POST /api/v1/analyze`.
3. The backend creates a placeholder project record.
4. Documents are chunked and embedded into `document_embeddings`.
5. Gemini extracts a structured profile.
6. The deterministic engine computes a final score and risk level.
7. Results are stored and returned to the frontend for display.

### 2. Follow-up investigation
1. After analysis, the user asks a question in the chat UI.
2. The frontend sends the message and current documents to `POST /api/v1/chat`.
3. The backend loads the latest project and assessment for the session.
4. Relevant chunks are retrieved from the embedding store.
5. Gemini answers using both raw context and prior findings.
6. Chat messages are saved to `chat_logs`.

### 3. Report export
1. The frontend requests `GET /api/v1/report/{session_id}`.
2. The backend loads the latest stored profile and assessment.
3. A PDF summary is generated and returned for download.

## Key Integrations and Dependencies
Observed integrations:
- **Google Gemini** via `google-genai` for extraction, chat, and embeddings.
- **PostgreSQL / Supabase** through SQLAlchemy + `asyncpg`.
- **pgvector** for document similarity search.
- **web3.py** plus public RPC endpoints for Ethereum, Base, and Arbitrum contract-code checks.

Key runtime libraries:
- Backend: FastAPI, Uvicorn, SQLAlchemy, Alembic, `google-genai`, `pgvector`, `web3`, `fpdf2`.
- Frontend: Streamlit, `requests`, plus document parsing helpers.

Inference: the intended production model is two separately deployed services, one for FastAPI and one for Streamlit, each with its own `Procfile`, backed by a shared Postgres instance and external Gemini access.

## Local Development Setup
The local development flow is straightforward:
- Create Python environments separately in `Backend/` and `Frontend/`.
- Install each side’s `requirements.txt`.
- Provide backend environment variables, especially `DATABASE_URL` and Gemini credentials.
- Run Alembic migrations before using persistent features.
- Start the backend first, then run the Streamlit UI and point it at the backend URL.

The backend requires a PostgreSQL database with the `vector` extension enabled by migration. The frontend assumes a reachable backend and defaults to a local URL.

## Testing and Quality
Current quality assets are concentrated in the backend:
- `Backend/tests/` contains tests for models, the health endpoint, and the risk engine.
- `Backend/pytest.ini` defines an `integration` marker for service-dependent tests.
- `Backend/eval/` provides a simple evaluation harness for extraction accuracy.
The overall quality story is present but still lightweight. There is no evidence of automated frontend testing. The backend tests cover core concepts, but not the full document-to-analysis-to-chat lifecycle with mocked external services.

## Current Gaps / Open Questions
- The product messaging emphasizes Hedera, Solana, and Stellar, but the current live verification path only checks EVM networks (`Ethereum`, `Base`, `Arbitrum`). This is an implementation-to-positioning gap.
- Alembic history includes both an empty `d1faedc8bb4d_add_chat_logs_table.py` migration and a later `9f94f7d47fc0_add_chat_logs.py` migration that actually creates the table. The migration story is functional but slightly confusing.
- Environment examples are not clearly documented in the workspace root. The presence of local `.env` files suggests configuration exists, but the sanitized setup path is not fully documented.

## Suggested Next Documentation Files
- `docs/ARCHITECTURE.md`: sequence diagrams, data flow, and component boundaries.
- `docs/API_REFERENCE.md`: endpoint contracts, example requests/responses, and error behavior.
- `docs/CONFIGURATION.md`: required environment variables, secrets handling, and local database setup.
- `docs/DEPLOYMENT.md`: separate backend/frontend deployment instructions and infrastructure assumptions.
- `docs/EVALUATION.md`: how to run `Backend/eval/`, interpret results, and expand datasets.
